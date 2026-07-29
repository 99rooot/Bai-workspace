import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from calendar_logic import (
    format_schedule,
    parse_period_events,
    parse_today_events,
    schedule_period,
    schedule_reply,
    validate_calendar_url,
    wants_schedule,
)


SAMPLE_ICAL = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART;TZID=Asia/Seoul:20260729T090000
DTEND;TZID=Asia/Seoul:20260729T100000
SUMMARY:수업
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260729
DTEND;VALUE=DATE:20260730
SUMMARY:과제 제출일
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=Asia/Seoul:20260722T183000
DTEND;TZID=Asia/Seoul:20260722T193000
RRULE:FREQ=WEEKLY;BYDAY=WE
SUMMARY:운동
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=Asia/Seoul:20260730T130000
DTEND;TZID=Asia/Seoul:20260730T140000
SUMMARY:내일 회의
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=Asia/Seoul:20260805T110000
DTEND;TZID=Asia/Seoul:20260805T120000
SUMMARY:다음 주 약속
END:VEVENT
END:VCALENDAR
"""

KST = timezone(timedelta(hours=9))


class CalendarLogicTest(unittest.TestCase):
    def test_trigger_phrase(self):
        for text in ("오늘 일정 알려줘", "내일 일정", "이번 주 스케줄", "다음 주 일정 알려줘"):
            self.assertTrue(wants_schedule(text))
        self.assertFalse(wants_schedule("집에 가고 싶다"))

    def test_schedule_periods_start_on_monday(self):
        today = date(2026, 7, 29)
        self.assertEqual(schedule_period("내일 일정", today), ("내일", date(2026, 7, 30), date(2026, 7, 30)))
        self.assertEqual(
            schedule_period("이번 주 일정", today),
            ("이번 주", date(2026, 7, 27), date(2026, 8, 2)),
        )
        self.assertEqual(
            schedule_period("다음 주 일정", today),
            ("다음 주", date(2026, 8, 3), date(2026, 8, 9)),
        )

    def test_google_calendar_url_only(self):
        validate_calendar_url("https://calendar.google.com/calendar/ical/example/basic.ics")
        with self.assertRaises(ValueError):
            validate_calendar_url("http://calendar.google.com/calendar/ical/example/basic.ics")
        with self.assertRaises(ValueError):
            validate_calendar_url("https://example.com/calendar.ics")

    def test_parse_today_events(self):
        events = parse_today_events(SAMPLE_ICAL, date(2026, 7, 29))
        self.assertEqual([event.summary for event in events], ["과제 제출일", "수업", "운동"])
        self.assertTrue(events[0].all_day)
        self.assertEqual(events[1].start.strftime("%H:%M"), "09:00")
        self.assertEqual(events[2].start.strftime("%H:%M"), "18:30")

    def test_slack_format(self):
        events = parse_today_events(SAMPLE_ICAL, date(2026, 7, 29))
        text = format_schedule(events, "오늘", date(2026, 7, 29), date(2026, 7, 29))
        self.assertIn("*오늘 일정 · 7월 29일*", text)
        self.assertIn("• 종일 · 과제 제출일", text)
        self.assertIn("• 09:00 · 수업", text)
        self.assertIn("총 3개의 일정", text)

    def test_empty_schedule(self):
        events = parse_today_events(SAMPLE_ICAL, date(2026, 7, 31))
        self.assertEqual(events, [])
        self.assertIn(
            "등록된 일정이 없습니다",
            format_schedule(events, "오늘", date(2026, 7, 31), date(2026, 7, 31)),
        )

    def test_this_week_and_next_week(self):
        this_week = parse_period_events(SAMPLE_ICAL, date(2026, 7, 27), date(2026, 8, 2))
        this_week_text = format_schedule(
            this_week,
            "이번 주",
            date(2026, 7, 27),
            date(2026, 8, 2),
        )
        self.assertIn("*이번 주 일정 · 7월 27일~8월 2일*", this_week_text)
        self.assertIn("• 7/30 13:00 · 내일 회의", this_week_text)
        self.assertNotIn("다음 주 약속", this_week_text)

        next_week = parse_period_events(SAMPLE_ICAL, date(2026, 8, 3), date(2026, 8, 9))
        next_week_text = format_schedule(
            next_week,
            "다음 주",
            date(2026, 8, 3),
            date(2026, 8, 9),
        )
        self.assertIn("• 8/5 11:00 · 다음 주 약속", next_week_text)
        self.assertIn("• 8/5 18:30 · 운동", next_week_text)

    @patch("calendar_logic.fetch_calendar_text", return_value=SAMPLE_ICAL)
    def test_tomorrow_reply(self, _fetch):
        text = schedule_reply(
            "https://calendar.google.com/calendar/ical/example/basic.ics",
            "내일 일정 알려줘",
            datetime(2026, 7, 29, 12, 0, tzinfo=KST),
        )
        self.assertIn("*내일 일정 · 7월 30일*", text)
        self.assertIn("• 13:00 · 내일 회의", text)


if __name__ == "__main__":
    unittest.main()
