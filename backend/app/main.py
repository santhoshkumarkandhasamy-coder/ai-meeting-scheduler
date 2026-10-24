import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import anthropic
import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.runner import run_turn
from app.agent.tools import ToolContext
from app.config import get_settings
from app.db import get_db, init_db
from app.google_calendar import CalendarClient, exchange_server_auth_code
from app.models import Conversation, User
from app.reminders import run_reminder_cycle
from app.security import current_user, decrypt, encrypt, issue_session_token
from app.slots import WorkingHours

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    scheduler = None
    settings = get_settings()
    if settings.scheduler_enabled:
        scheduler = BackgroundScheduler()
        scheduler.add_job(run_reminder_cycle, "interval", seconds=settings.reminder_poll_seconds, max_instances=1)
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Meeting Assistant API", lifespan=lifespan)


def _valid_tz(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Unknown timezone: {value}")
    return value


# ---------- Schemas ----------


class GoogleAuthIn(BaseModel):
    server_auth_code: str
    timezone: str = "Asia/Kolkata"

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        return _valid_tz(v)


class SettingsIn(BaseModel):
    timezone: str | None = None
    language: str | None = Field(default=None, pattern="^(auto|ta-IN|en-IN)$")
    reminder_minutes: list[int] | None = None
    work_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    work_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    work_days: list[int] | None = None
    morning_briefing_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    disable_morning_briefing: bool = False

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        return v if v is None else _valid_tz(v)


class PushTokenIn(BaseModel):
    token: str


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None


def user_out(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "timezone": user.timezone,
        "language": user.language,
        "reminder_minutes": user.reminder_minutes,
        "work_start": user.work_start,
        "work_end": user.work_end,
        "work_days": user.work_days,
        "morning_briefing_time": user.morning_briefing_time,
    }


def calendar_for(user: User) -> CalendarClient:
    return CalendarClient(decrypt(user.encrypted_refresh_token), user.timezone)


# ---------- Routes ----------


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/auth/google")
def auth_google(body: GoogleAuthIn, db: Session = Depends(get_db)) -> dict:
    try:
        result = exchange_server_auth_code(body.server_auth_code)
    except (httpx.HTTPError, ValueError) as e:
        raise HTTPException(401, f"Google sign-in failed: {e}")
    claims, tokens = result["claims"], result["tokens"]

    user = db.scalar(select(User).where(User.google_sub == claims["sub"]))
    refresh_token = tokens.get("refresh_token")
    if user is None:
        if not refresh_token:
            raise HTTPException(400, "Google did not return a refresh token. Remove the app's access in your Google account and sign in again.")
        user = User(google_sub=claims["sub"], email=claims.get("email", ""), encrypted_refresh_token=encrypt(refresh_token))
        db.add(user)
    elif refresh_token:
        user.encrypted_refresh_token = encrypt(refresh_token)
    user.email = claims.get("email", user.email)
    user.name = claims.get("name", user.name or "")
    user.timezone = body.timezone
    db.commit()
    return {"token": issue_session_token(user.id), "user": user_out(user)}


@app.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return user_out(user)


@app.put("/me/settings")
def update_settings(body: SettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    data = body.model_dump(exclude_none=True, exclude={"disable_morning_briefing"})
    if "reminder_minutes" in data:
        data["reminder_minutes"] = sorted({m for m in data["reminder_minutes"] if 0 < m <= 1440}, reverse=True)
    if "work_days" in data:
        data["work_days"] = sorted({d for d in data["work_days"] if 0 <= d <= 6})
    for key, value in data.items():
        setattr(user, key, value)
    if body.disable_morning_briefing:
        user.morning_briefing_time = None
    db.commit()
    return user_out(user)


@app.post("/me/push-token")
def save_push_token(body: PushTokenIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    user.expo_push_token = body.token
    db.commit()
    return {"ok": True}


@app.get("/events/upcoming")
def upcoming(days: int = 7, user: User = Depends(current_user)) -> dict:
    days = max(1, min(days, 31))
    now = datetime.now(ZoneInfo(user.timezone))
    try:
        events = calendar_for(user).list_events(now, now + timedelta(days=days), max_results=100)
    except Exception as e:
        raise HTTPException(502, f"Could not read Google Calendar: {e}")
    return {"events": events}


@app.post("/agent/chat")
def chat(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    conversation = None
    if body.conversation_id:
        conversation = db.get(Conversation, body.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise HTTPException(404, "Conversation not found")
    if conversation is None:
        conversation = Conversation(user_id=user.id, messages=[])
        db.add(conversation)

    def save_preferences(updates: dict) -> None:
        for key, value in updates.items():
            setattr(user, key, value)
        db.commit()

    ctx = ToolContext(
        calendar=calendar_for(user),
        tz=ZoneInfo(user.timezone),
        hours=WorkingHours.parse(user.work_start, user.work_end, user.work_days),
        save_preferences=save_preferences,
    )
    profile = {
        "name": user.name,
        "email": user.email,
        "timezone": user.timezone,
        "language": user.language,
        "work_hours": f"{user.work_start}-{user.work_end}, days {user.work_days} (Mon=0)",
    }
    try:
        reply, history = run_turn(list(conversation.messages or []), body.message, ctx, profile)
    except anthropic.APIConnectionError:
        raise HTTPException(503, "The assistant is unreachable right now. Please try again.")
    except anthropic.APIStatusError as e:
        raise HTTPException(502, f"The assistant failed ({e.status_code}). Please try again.")
    conversation.messages = history
    db.commit()
    return {"conversation_id": conversation.id, "reply": reply}
