"""Build tomorrow's read-only calendar notification."""

from __future__ import annotations

from datetime import datetime, timedelta

from calendar_logic import KST, format_schedule, parse_today_events


def tomorrow_notification(calendar_text: str, now: datetime | None = None) -> str | None:
    checked_at = now or datetime.now(KST)
    tomorrow = checked_at.date() + timedelta(days=1)
    events = parse_today_events(calendar_text, tomorrow)
    if not events:
        return None
    return format_schedule(events, "내일", tomorrow, tomorrow)
