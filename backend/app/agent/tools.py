"""Tool definitions given to Claude, and the code that executes them."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from app.slots import WorkingHours, free_slots_by_day


class Calendar(Protocol):
    def list_events(self, start: datetime, end: datetime, max_results: int = 50) -> list[dict]: ...
    def busy_intervals(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]: ...
    def create_event(self, title, start, end, attendees=None, description=None, add_meet_link=True) -> dict: ...
    def update_event(self, event_id: str, changes: dict) -> dict: ...
    def cancel_event(self, event_id: str) -> None: ...


@dataclass
class ToolContext:
    calendar: Calendar
    tz: ZoneInfo
    hours: WorkingHours
    # Callback that persists reminder preferences for the user.
    save_preferences: Any


class ToolInputError(ValueError):
    pass


_DATETIME = {"type": "string", "description": "ISO 8601 datetime with UTC offset, e.g. 2026-10-27T15:00:00+05:30"}
_CONFIRMED = {
    "type": "boolean",
    "description": "True only if the user explicitly agreed to these exact details in their latest message.",
}

TOOLS: list[dict] = [
    {
        "name": "list_events",
        "description": (
            "List the user's calendar events between two datetimes. Use it for questions like "
            "'what meetings do I have tomorrow', and to find an event's id before updating or cancelling it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"start": _DATETIME, "end": _DATETIME},
            "required": ["start", "end"],
        },
    },
    {
        "name": "find_free_slots",
        "description": (
            "Find free time within the user's working hours between two datetimes. Returns each working day "
            "with fully_free, free windows and busy windows. Use it for availability questions and to check "
            "for clashes before proposing a meeting time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start": _DATETIME,
                "end": _DATETIME,
                "min_duration_minutes": {"type": "integer", "description": "Shortest free window to report. Default 30."},
            },
            "required": ["start", "end"],
        },
    },
    {
        "name": "create_event",
        "description": "Create a calendar event and email invites to attendees. Call only after the user confirmed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start": _DATETIME,
                "end": _DATETIME,
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "Attendee email addresses"},
                "description": {"type": "string"},
                "add_meet_link": {"type": "boolean", "description": "Attach a Google Meet link. Default true."},
                "user_confirmed": _CONFIRMED,
            },
            "required": ["title", "start", "end", "user_confirmed"],
        },
    },
    {
        "name": "update_event",
        "description": "Reschedule or edit an existing event and notify attendees. Call only after the user confirmed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "title": {"type": "string"},
                "start": _DATETIME,
                "end": _DATETIME,
                "attendees": {"type": "array", "items": {"type": "string"}},
                "user_confirmed": _CONFIRMED,
            },
            "required": ["event_id", "user_confirmed"],
        },
    },
    {
        "name": "cancel_event",
        "description": "Cancel an event and notify attendees. Call only after the user confirmed.",
        "input_schema": {
            "type": "object",
            "properties": {"event_id": {"type": "string"}, "user_confirmed": _CONFIRMED},
            "required": ["event_id", "user_confirmed"],
        },
    },
    {
        "name": "set_reminder_preference",
        "description": (
            "Change how many minutes before each meeting the user is reminded, and/or the daily morning "
            "briefing time. Use when the user asks to change their reminders."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "minutes_before": {"type": "array", "items": {"type": "integer"}, "description": "e.g. [30, 10]"},
                "morning_briefing_time": {
                    "type": ["string", "null"],
                    "description": "HH:MM in 24-hour local time, or null to turn the briefing off",
                },
            },
        },
    },
]


def parse_dt(value: Any, tz: ZoneInfo, field: str) -> datetime:
    if not isinstance(value, str):
        raise ToolInputError(f"'{field}' must be an ISO 8601 datetime string")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise ToolInputError(f"'{field}' is not a valid ISO 8601 datetime: {value!r}")
    return dt if dt.tzinfo else dt.replace(tzinfo=tz)


def _require_confirmation(args: dict) -> None:
    if args.get("user_confirmed") is not True:
        raise ToolInputError(
            "Not confirmed. Read the details back to the user and wait for them to say yes before calling this tool."
        )


def _time_range(args: dict, ctx: ToolContext) -> tuple[datetime, datetime]:
    start = parse_dt(args.get("start"), ctx.tz, "start")
    end = parse_dt(args.get("end"), ctx.tz, "end")
    if end <= start:
        raise ToolInputError("'end' must be after 'start'")
    if end - start > timedelta(days=62):
        raise ToolInputError("Range too large; ask about at most two months at a time")
    return start, end


def execute_tool(name: str, args: dict, ctx: ToolContext) -> dict:
    """Run one tool call. Raises ToolInputError for bad input; other exceptions are API failures."""
    if name == "list_events":
        start, end = _time_range(args, ctx)
        events = ctx.calendar.list_events(start, end)
        return {"count": len(events), "events": events}

    if name == "find_free_slots":
        start, end = _time_range(args, ctx)
        busy = ctx.calendar.busy_intervals(start, end)
        days = free_slots_by_day(busy, start, end, ctx.tz, ctx.hours, int(args.get("min_duration_minutes") or 30))
        return {"working_days": days}

    if name == "create_event":
        _require_confirmation(args)
        start, end = _time_range(args, ctx)
        title = str(args.get("title") or "Meeting")
        event = ctx.calendar.create_event(
            title,
            start,
            end,
            attendees=list(args.get("attendees") or []),
            description=args.get("description"),
            add_meet_link=args.get("add_meet_link", True) is not False,
        )
        return {"created": event}

    if name == "update_event":
        _require_confirmation(args)
        changes: dict = {}
        if "title" in args:
            changes["title"] = str(args["title"])
        if "start" in args:
            changes["start"] = parse_dt(args["start"], ctx.tz, "start")
        if "end" in args:
            changes["end"] = parse_dt(args["end"], ctx.tz, "end")
        if "attendees" in args:
            changes["attendees"] = list(args["attendees"])
        if not changes:
            raise ToolInputError("Nothing to change")
        return {"updated": ctx.calendar.update_event(str(args["event_id"]), changes)}

    if name == "cancel_event":
        _require_confirmation(args)
        ctx.calendar.cancel_event(str(args["event_id"]))
        return {"cancelled": args["event_id"]}

    if name == "set_reminder_preference":
        updates: dict = {}
        if "minutes_before" in args:
            minutes = sorted({int(m) for m in args["minutes_before"] if 0 < int(m) <= 24 * 60}, reverse=True)
            if not minutes:
                raise ToolInputError("minutes_before must contain values between 1 and 1440")
            updates["reminder_minutes"] = minutes
        if "morning_briefing_time" in args:
            value = args["morning_briefing_time"]
            if value is not None:
                try:
                    datetime.strptime(value, "%H:%M")
                except (TypeError, ValueError):
                    raise ToolInputError("morning_briefing_time must be HH:MM")
            updates["morning_briefing_time"] = value
        if not updates:
            raise ToolInputError("Nothing to change")
        ctx.save_preferences(updates)
        return {"saved": updates}

    raise ToolInputError(f"Unknown tool: {name}")


def run_tool_block(name: str, args: dict, ctx: ToolContext) -> tuple[str, bool]:
    """Execute a tool and return (content, is_error) for a tool_result block."""
    try:
        return json.dumps(execute_tool(name, args, ctx), ensure_ascii=False), False
    except ToolInputError as e:
        return f"Error: {e}", True
    except Exception as e:  # Google API / network failure
        return f"Error: the calendar request failed ({type(e).__name__}: {e})", True
