"""Pure free-time calculation, independent of Google APIs so it is easy to test."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class WorkingHours:
    start: time
    end: time
    days: frozenset[int]  # Monday=0 ... Sunday=6

    @classmethod
    def parse(cls, start: str, end: str, days: list[int]) -> "WorkingHours":
        return cls(time.fromisoformat(start), time.fromisoformat(end), frozenset(days))


def merge_intervals(intervals: list[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def free_slots_by_day(
    busy: list[Interval],
    range_start: datetime,
    range_end: datetime,
    tz: ZoneInfo,
    hours: WorkingHours,
    min_minutes: int = 30,
) -> list[dict]:
    """Return one entry per working day in the range with its free and busy windows."""
    busy = merge_intervals([(s.astimezone(tz), e.astimezone(tz)) for s, e in busy])
    min_len = timedelta(minutes=min_minutes)
    days: list[dict] = []

    day: date = range_start.astimezone(tz).date()
    last_day: date = range_end.astimezone(tz).date()
    while day <= last_day:
        if day.weekday() in hours.days:
            window_start = max(datetime.combine(day, hours.start, tz), range_start.astimezone(tz))
            window_end = min(datetime.combine(day, hours.end, tz), range_end.astimezone(tz))
            if window_start < window_end:
                days.append(_day_summary(day, window_start, window_end, busy, min_len))
        day += timedelta(days=1)
    return days


def _day_summary(
    day: date, window_start: datetime, window_end: datetime, busy: list[Interval], min_len: timedelta
) -> dict:
    day_busy = [(max(s, window_start), min(e, window_end)) for s, e in busy if s < window_end and e > window_start]
    free: list[Interval] = []
    cursor = window_start
    for s, e in day_busy:
        if s - cursor >= min_len:
            free.append((cursor, s))
        cursor = max(cursor, e)
    if window_end - cursor >= min_len:
        free.append((cursor, window_end))

    return {
        "date": day.isoformat(),
        "weekday": day.strftime("%A"),
        "fully_free": not day_busy,
        "free": [{"start": s.isoformat(), "end": e.isoformat()} for s, e in free],
        "busy": [{"start": s.isoformat(), "end": e.isoformat()} for s, e in day_busy],
    }
