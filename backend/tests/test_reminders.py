from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.reminders import briefing_due, briefing_text, due_reminders, event_key, reminder_text

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 27, 9, 0, tzinfo=IST)


def event(minutes_from_now, **kw):
    start = NOW + timedelta(minutes=minutes_from_now)
    base = {
        "id": "e1",
        "title": "Standup",
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=30)).isoformat(),
        "all_day": False,
        "attendees": [{"email": "ravi@example.com", "response": "accepted"}],
        "my_response": "accepted",
    }
    base.update(kw)
    return base


def test_reminder_due_at_offset():
    due = due_reminders([event(10)], NOW, [30, 10], set())
    assert [(k, m) for _, k, m in due] == [("before:10", 10)]


def test_not_due_between_offsets():
    assert due_reminders([event(20)], NOW, [30, 10], set()) == []


def test_late_job_still_sends_within_grace():
    due = due_reminders([event(27)], NOW, [30, 10], set())
    assert [k for _, k, _ in due] == ["before:30"]


def test_no_duplicate_when_already_sent():
    e = event(10)
    assert due_reminders([e], NOW, [30, 10], {(event_key(e), "before:10")}) == []


def test_skips_declined_all_day_and_past():
    events = [event(10, my_response="declined"), event(10, all_day=True), event(-5)]
    assert due_reminders(events, NOW, [30, 10], set()) == []


def test_rescheduled_event_gets_new_key():
    assert event_key(event(10)) != event_key(event(40))


def test_texts_in_tamil_and_english():
    _, en = reminder_text(event(10), 10, "en-IN")
    assert "starts in 10 minutes" in en and "ravi" in en
    _, ta = reminder_text(event(10), 10, "ta-IN")
    assert "நிமிஷத்துல" in ta
    assert "free" in briefing_text([], "en-IN")[1]


def test_briefing_window():
    assert briefing_due(NOW.replace(hour=8, minute=5), "08:00")
    assert not briefing_due(NOW.replace(hour=7, minute=59), "08:00")
    assert not briefing_due(NOW.replace(hour=9, minute=0), "08:00")
    assert not briefing_due(NOW, None)
