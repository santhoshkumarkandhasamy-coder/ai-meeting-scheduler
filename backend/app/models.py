import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    google_sub: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(200), default="")
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    language: Mapped[str] = mapped_column(String(16), default="auto")  # auto | ta-IN | en-IN

    # Preferences
    reminder_minutes: Mapped[list] = mapped_column(JSON, default=lambda: [30, 10])
    work_start: Mapped[str] = mapped_column(String(5), default="09:00")
    work_end: Mapped[str] = mapped_column(String(5), default="18:00")
    work_days: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4])  # Mon=0
    morning_briefing_time: Mapped[str | None] = mapped_column(String(5), default="08:00")

    expo_push_token: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Full Claude message history (append-only), including tool_use / tool_result blocks.
    messages: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class SentReminder(Base):
    """One row per (user, event, offset) so the same reminder is never pushed twice."""

    __tablename__ = "sent_reminders"
    __table_args__ = (UniqueConstraint("user_id", "event_key", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # event id + start time, so a rescheduled meeting gets fresh reminders
    event_key: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(32))  # e.g. "before:10" or "briefing"
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
