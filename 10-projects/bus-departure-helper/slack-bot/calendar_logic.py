"""Read-only Google Calendar iCal parsing for the Slack bot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


KST = timezone(timedelta(hours=9))
WEEKDAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


@dataclass(frozen=True)
class CalendarEvent:
    summary: str
    start: datetime
    end: datetime
    all_day: bool = False


def wants_schedule(text: str) -> bool:
    compact = "".join(text.lower().split())
    phrases = (
        "오늘일정",
        "오늘스케줄",
        "내일일정",
        "내일스케줄",
        "이번주일정",
        "이번주스케줄",
        "다음주일정",
        "다음주스케줄",
        "일정알려",
        "일정보여",
        "스케줄알려",
        "스케줄보여",
    )
    return any(phrase in compact for phrase in phrases)


def schedule_period(text: str, today: date) -> tuple[str, date, date]:
    compact = "".join(text.lower().split())
    monday = today - timedelta(days=today.weekday())
    if "다음주" in compact:
        start = monday + timedelta(days=7)
        return "다음 주", start, start + timedelta(days=6)
    if "이번주" in compact:
        return "이번 주", monday, monday + timedelta(days=6)
    if "내일" in compact:
        target = today + timedelta(days=1)
        return "내일", target, target
    return "오늘", today, today


def validate_calendar_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "calendar.google.com":
        raise ValueError("Google Calendar의 HTTPS iCal 주소만 사용할 수 있습니다.")


def fetch_calendar_text(url: str, timeout: int = 8) -> str:
    validate_calendar_url(url)
    request = Request(url, headers={"User-Agent": "bai-slack-calendar/0.1"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _unfold_ical(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line)
    return lines


def _parse_properties(text: str) -> list[dict[str, tuple[dict[str, str], str]]]:
    events: list[dict[str, tuple[dict[str, str], str]]] = []
    current: dict[str, tuple[dict[str, str], str]] | None = None
    for line in _unfold_ical(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key_part, value = line.split(":", 1)
        parts = key_part.split(";")
        name = parts[0].upper()
        params = {}
        for part in parts[1:]:
            if "=" in part:
                param_name, param_value = part.split("=", 1)
                params[param_name.upper()] = param_value
        current[name] = (params, value)
    return events


def _timezone(tzid: str | None) -> timezone | ZoneInfo:
    if not tzid:
        return KST
    try:
        return ZoneInfo(tzid)
    except ZoneInfoNotFoundError:
        return KST


def _parse_datetime(params: dict[str, str], value: str) -> tuple[datetime, bool]:
    if params.get("VALUE") == "DATE" or (len(value) == 8 and "T" not in value):
        parsed_date = datetime.strptime(value[:8], "%Y%m%d").date()
        return datetime.combine(parsed_date, time.min, KST), True
    if value.endswith("Z"):
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return parsed.astimezone(KST), False
    parsed = datetime.strptime(value, "%Y%m%dT%H%M%S")
    return parsed.replace(tzinfo=_timezone(params.get("TZID"))).astimezone(KST), False


def _unescape_text(value: str) -> str:
    return (
        value.replace("\\n", " ")
        .replace("\\N", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _parse_rrule(value: str) -> dict[str, str]:
    rule = {}
    for part in value.split(";"):
        if "=" in part:
            key, item = part.split("=", 1)
            rule[key.upper()] = item
    return rule


def _parse_until(value: str) -> date:
    return datetime.strptime(value[:8], "%Y%m%d").date()


def _recurs_on(start: datetime, target: date, rule: dict[str, str]) -> bool:
    if target < start.date():
        return False
    if rule.get("UNTIL") and target > _parse_until(rule["UNTIL"]):
        return False

    interval = max(int(rule.get("INTERVAL", "1")), 1)
    elapsed_days = (target - start.date()).days
    frequency = rule.get("FREQ")
    if frequency == "DAILY":
        occurrence_index = elapsed_days // interval
        occurs = elapsed_days % interval == 0
    elif frequency == "WEEKLY":
        weekdays = rule.get("BYDAY", WEEKDAYS[start.weekday()]).split(",")
        occurs = WEEKDAYS[target.weekday()] in weekdays and elapsed_days // 7 % interval == 0
        occurrence_index = sum(
            1
            for offset in range(elapsed_days + 1)
            if WEEKDAYS[(start.weekday() + offset) % 7] in weekdays
            and offset // 7 % interval == 0
        ) - 1
    else:
        return target == start.date()

    if rule.get("COUNT") and occurrence_index >= int(rule["COUNT"]):
        return False
    return occurs


def parse_today_events(text: str, target: date) -> list[CalendarEvent]:
    parsed_events = []
    for properties in _parse_properties(text):
        if properties.get("STATUS", ({}, ""))[1].upper() == "CANCELLED":
            continue
        if "DTSTART" not in properties:
            continue

        start, all_day = _parse_datetime(*properties["DTSTART"])
        if "DTEND" in properties:
            end, _ = _parse_datetime(*properties["DTEND"])
        else:
            end = start + (timedelta(days=1) if all_day else timedelta(hours=1))

        rule_value = properties.get("RRULE", ({}, ""))[1]
        if rule_value:
            if not _recurs_on(start, target, _parse_rrule(rule_value)):
                continue
            duration = end - start
            start = datetime.combine(target, start.timetz()).astimezone(KST)
            end = start + duration
        elif not (start.date() <= target < end.date() or start.date() == target):
            continue

        summary = _unescape_text(properties.get("SUMMARY", ({}, "제목 없는 일정"))[1])
        parsed_events.append(CalendarEvent(summary, start, end, all_day))
    return sorted(parsed_events, key=lambda event: (not event.all_day, event.start))


def parse_period_events(text: str, start: date, end: date) -> list[CalendarEvent]:
    events: set[CalendarEvent] = set()
    target = start
    while target <= end:
        events.update(parse_today_events(text, target))
        target += timedelta(days=1)
    return sorted(events, key=lambda event: (event.start, not event.all_day, event.summary))


def format_schedule(events: list[CalendarEvent], label: str, start: date, end: date) -> str:
    if start == end:
        heading = f"*{label} 일정 · {start.month}월 {start.day}일*"
    else:
        heading = f"*{label} 일정 · {start.month}월 {start.day}일~{end.month}월 {end.day}일*"
    if not events:
        return f"{heading}\n등록된 일정이 없습니다."

    lines = [heading, ""]
    for event in events:
        if start == end and event.all_day:
            lines.append(f"• 종일 · {event.summary}")
        elif start == end:
            lines.append(f"• {event.start:%H:%M} · {event.summary}")
        elif event.all_day:
            lines.append(f"• {event.start.month}/{event.start.day} 종일 · {event.summary}")
        else:
            lines.append(f"• {event.start.month}/{event.start.day} {event.start:%H:%M} · {event.summary}")
    lines.extend(["", f"총 {len(events)}개의 일정이 있습니다."])
    return "\n".join(lines)


def schedule_reply(url: str, request_text: str, now: datetime | None = None) -> str:
    checked_at = now or datetime.now(KST)
    label, start, end = schedule_period(request_text, checked_at.date())
    calendar_text = fetch_calendar_text(url)
    events = parse_period_events(calendar_text, start, end)
    return format_schedule(events, label, start, end)
