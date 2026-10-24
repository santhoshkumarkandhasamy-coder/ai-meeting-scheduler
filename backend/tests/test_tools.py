import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agent.tools import TOOLS, ToolContext, run_tool_block
from app.slots import WorkingHours

IST = ZoneInfo("Asia/Kolkata")


class FakeCalendar:
    def __init__(self):
        self.created = []
        self.cancelled = []

    def list_events(self, start, end, max_results=50):
        return [{"id": "e1", "title": "Review", "start": "2026-10-27T10:00:00+05:30"}]

    def busy_intervals(self, start, end):
        return [(datetime(2026, 10, 27, 10, tzinfo=IST), datetime(2026, 10, 27, 11, tzinfo=IST))]

    def create_event(self, title, start, end, attendees=None, description=None, add_meet_link=True):
        self.created.append((title, start, end, attendees, add_meet_link))
        return {"id": "new", "title": title, "start": start.isoformat()}

    def update_event(self, event_id, changes):
        return {"id": event_id, **{k: str(v) for k, v in changes.items()}}

    def cancel_event(self, event_id):
        self.cancelled.append(event_id)


def ctx(saved=None):
    return ToolContext(
        calendar=FakeCalendar(),
        tz=IST,
        hours=WorkingHours.parse("09:00", "18:00", [0, 1, 2, 3, 4]),
        save_preferences=(saved.update if saved is not None else lambda u: None),
    )


def test_tool_names_unique():
    names = [t["name"] for t in TOOLS]
    assert len(names) == len(set(names))


def test_find_free_slots():
    out, err = run_tool_block("find_free_slots", {"start": "2026-10-27T00:00:00+05:30", "end": "2026-10-27T23:00:00+05:30"}, ctx())
    assert not err
    day = json.loads(out)["working_days"][0]
    assert day["fully_free"] is False and len(day["free"]) == 2


def test_create_requires_confirmation():
    c = ctx()
    args = {"title": "Budget", "start": "2026-10-28T15:00:00+05:30", "end": "2026-10-28T15:30:00+05:30", "user_confirmed": False}
    out, err = run_tool_block("create_event", args, c)
    assert err and "Not confirmed" in out and c.calendar.created == []

    args["user_confirmed"] = True
    args["attendees"] = ["ravi@example.com"]
    out, err = run_tool_block("create_event", args, c)
    assert not err and c.calendar.created[0][3] == ["ravi@example.com"]


def test_naive_datetime_gets_user_timezone():
    c = ctx()
    run_tool_block("create_event", {"title": "X", "start": "2026-10-28T15:00:00", "end": "2026-10-28T16:00:00", "user_confirmed": True}, c)
    assert c.calendar.created[0][1].tzinfo == IST


def test_bad_inputs_return_errors():
    out, err = run_tool_block("list_events", {"start": "tomorrow", "end": "2026-10-28T00:00:00+05:30"}, ctx())
    assert err and "ISO 8601" in out
    out, err = run_tool_block("list_events", {"start": "2026-10-28T10:00:00+05:30", "end": "2026-10-28T09:00:00+05:30"}, ctx())
    assert err
    out, err = run_tool_block("nope", {}, ctx())
    assert err


def test_cancel_and_preferences():
    c = ctx()
    _, err = run_tool_block("cancel_event", {"event_id": "e1", "user_confirmed": True}, c)
    assert not err and c.calendar.cancelled == ["e1"]

    saved = {}
    _, err = run_tool_block("set_reminder_preference", {"minutes_before": [10, 60, 10], "morning_briefing_time": None}, ctx(saved))
    assert not err and saved == {"reminder_minutes": [60, 10], "morning_briefing_time": None}


def test_api_failure_is_reported_not_raised():
    c = ctx()
    c.calendar.list_events = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    out, err = run_tool_block("list_events", {"start": "2026-10-28T00:00:00+05:30", "end": "2026-10-29T00:00:00+05:30"}, c)
    assert err and "boom" in out
