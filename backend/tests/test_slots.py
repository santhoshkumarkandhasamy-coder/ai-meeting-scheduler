from datetime import datetime
from zoneinfo import ZoneInfo

from app.slots import WorkingHours, free_slots_by_day, merge_intervals

IST = ZoneInfo("Asia/Kolkata")
HOURS = WorkingHours.parse("09:00", "18:00", [0, 1, 2, 3, 4])


def dt(day, h, m=0):
    return datetime(2026, 10, day, h, m, tzinfo=IST)


def test_merge_overlapping():
    merged = merge_intervals([(dt(27, 10), dt(27, 11)), (dt(27, 10, 30), dt(27, 12)), (dt(27, 14), dt(27, 15))])
    assert merged == [(dt(27, 10), dt(27, 12)), (dt(27, 14), dt(27, 15))]


def test_fully_free_day():
    days = free_slots_by_day([], dt(27, 0), dt(27, 23, 59), IST, HOURS)
    assert len(days) == 1
    assert days[0]["fully_free"] is True
    assert days[0]["free"] == [{"start": dt(27, 9).isoformat(), "end": dt(27, 18).isoformat()}]


def test_busy_splits_day_and_short_gaps_dropped():
    busy = [(dt(27, 10), dt(27, 12)), (dt(27, 12, 15), dt(27, 13))]
    days = free_slots_by_day(busy, dt(27, 0), dt(27, 23), IST, HOURS, min_minutes=30)
    free = [(f["start"], f["end"]) for f in days[0]["free"]]
    assert free == [(dt(27, 9).isoformat(), dt(27, 10).isoformat()), (dt(27, 13).isoformat(), dt(27, 18).isoformat())]
    assert days[0]["fully_free"] is False


def test_weekend_skipped_and_utc_busy_converted():
    # Sat 24 Oct and Sun 25 Oct are skipped; busy given in UTC (04:30Z = 10:00 IST Monday).
    busy = [(datetime.fromisoformat("2026-10-26T04:30:00+00:00"), datetime.fromisoformat("2026-10-26T05:30:00+00:00"))]
    days = free_slots_by_day(busy, dt(24, 0), dt(26, 23), IST, HOURS)
    assert [d["date"] for d in days] == ["2026-10-26"]
    assert days[0]["busy"] == [{"start": dt(26, 10).isoformat(), "end": dt(26, 11).isoformat()}]


def test_range_starting_mid_day_clips_window():
    days = free_slots_by_day([], dt(27, 15), dt(27, 23), IST, HOURS)
    assert days[0]["free"] == [{"start": dt(27, 15).isoformat(), "end": dt(27, 18).isoformat()}]
