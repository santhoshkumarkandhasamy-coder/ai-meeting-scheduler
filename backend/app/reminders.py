"""Background job that pushes meeting reminders and the morning briefing."""

import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.google_calendar import CalendarClient
from app.models import SentReminder, User
from app.push import send_push
from app.security import decrypt

log = logging.getLogger(__name__)

# A reminder is still sent if the job runs up to this many minutes late.
GRACE_MINUTES = 5
BRIEFING_WINDOW_MINUTES = 30


def event_key(event: dict) -> str:
    return f"{event['id']}@{event['start']}"


def due_reminders(
    events: list[dict], now: datetime, offsets: list[int], already_sent: set[tuple[str, str]]
) -> list[tuple[dict, str, int]]:
    """Return (event, kind, minutes_left) for every reminder that should go out now."""
    due = []
    for event in events:
        if event["all_day"] or event.get("my_response") == "declined":
            continue
        start = datetime.fromisoformat(event["start"])
        minutes_left = (start - now).total_seconds() / 60
        if minutes_left < 0:
            continue
        # Only the smallest offset that has been reached, so a late start doesn't send three pushes at once.
        reached = [o for o in sorted(offsets) if o - GRACE_MINUTES < minutes_left <= o]
        if not reached:
            continue
        kind = f"before:{reached[0]}"
        if (event_key(event), kind) not in already_sent:
            due.append((event, kind, round(minutes_left)))
    return due


def reminder_text(event: dict, minutes_left: int, language: str) -> tuple[str, str]:
    start = datetime.fromisoformat(event["start"]).strftime("%I:%M %p").lstrip("0")
    people = ", ".join(a["email"].split("@")[0] for a in event["attendees"][:3])
    if language == "ta-IN":
        body = f"இன்னும் {minutes_left} நிமிஷத்துல \"{event['title']}\" மீட்டிங் ({start})."
        if people:
            body += f" கலந்துகொள்பவர்கள்: {people}."
        return "மீட்டிங் நினைவூட்டல்", body
    body = f"\"{event['title']}\" starts in {minutes_left} minutes ({start})."
    if people:
        body += f" With {people}."
    return "Meeting reminder", body


def briefing_text(events: list[dict], language: str) -> tuple[str, str]:
    timed = [e for e in events if not e["all_day"] and e.get("my_response") != "declined"]
    parts = [
        f"{datetime.fromisoformat(e['start']).strftime('%I:%M %p').lstrip('0')} {e['title']}" for e in timed
    ]
    if language == "ta-IN":
        if not timed:
            return "இன்றைய மீட்டிங்குகள்", "இன்னைக்கு எந்த மீட்டிங்கும் இல்லை. நாள் முழுக்க ஃப்ரீ."
        return "இன்றைய மீட்டிங்குகள்", f"இன்னைக்கு {len(timed)} மீட்டிங்: " + "; ".join(parts)
    if not timed:
        return "Today's meetings", "You have no meetings today. Your day is free."
    return "Today's meetings", f"You have {len(timed)} meeting(s) today: " + "; ".join(parts)


def briefing_due(now_local: datetime, briefing_time: str | None) -> bool:
    if not briefing_time:
        return False
    at = datetime.combine(now_local.date(), time.fromisoformat(briefing_time), now_local.tzinfo)
    return at <= now_local < at + timedelta(minutes=BRIEFING_WINDOW_MINUTES)


def _record(db, user_id: str, key: str, kind: str) -> bool:
    """Insert a SentReminder row; False if it already existed (another worker sent it)."""
    db.add(SentReminder(user_id=user_id, event_key=key, kind=kind))
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def process_user(db, user: User, now: datetime) -> None:
    tz = ZoneInfo(user.timezone)
    now_local = now.astimezone(tz)
    calendar = CalendarClient(decrypt(user.encrypted_refresh_token), user.timezone)
    language = "ta-IN" if user.language == "ta-IN" else "en-IN"

    horizon = max(user.reminder_minutes or [10]) + 1
    events = calendar.list_events(now_local, now_local + timedelta(minutes=horizon))
    sent = {
        (r.event_key, r.kind)
        for r in db.scalars(select(SentReminder).where(SentReminder.user_id == user.id))
    }
    for event, kind, minutes_left in due_reminders(events, now_local, user.reminder_minutes or [], sent):
        if _record(db, user.id, event_key(event), kind):
            title, body = reminder_text(event, minutes_left, language)
            send_push(user.expo_push_token, title, body, {"type": "reminder", "event": event, "speak": body})

    if briefing_due(now_local, user.morning_briefing_time):
        key = f"briefing@{now_local.date().isoformat()}"
        if (key, "briefing") not in sent and _record(db, user.id, key, "briefing"):
            day_start = datetime.combine(now_local.date(), time.min, tz)
            today = calendar.list_events(day_start, day_start + timedelta(days=1))
            title, body = briefing_text(today, language)
            send_push(user.expo_push_token, title, body, {"type": "briefing", "speak": body})


def prune_old(db, now: datetime) -> None:
    cutoff = now - timedelta(days=3)
    db.query(SentReminder).filter(SentReminder.sent_at < cutoff).delete()
    db.commit()


def run_reminder_cycle() -> None:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        users = db.scalars(select(User).where(User.expo_push_token.is_not(None))).all()
        for user in users:
            try:
                process_user(db, user, now)
            except Exception:
                db.rollback()
                log.exception("Reminder cycle failed for user %s", user.id)
        prune_old(db, now)
