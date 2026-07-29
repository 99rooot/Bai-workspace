import unittest
from datetime import date

from calendar_logic import format_today_schedule, parse_today_events, validate_calendar_url, wants_today_schedule


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
END:VCALENDAR
"""


class CalendarLogicTest(unittest.TestCase):
    def test_trigger_phrase(self):
        self.assertTrue(wants_today_schedule("오늘 일정 알려줘"))
        self.assertTrue(wants_today_schedule("오늘 스케줄 보여줘"))
        self.assertFalse(wants_today_schedule("집에 가고 싶다"))

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
        text = format_today_schedule(events, date(2026, 7, 29))
        self.assertIn("*오늘 일정 · 7월 29일*", text)
        self.assertIn("• 종일 · 과제 제출일", text)
        self.assertIn("• 09:00 · 수업", text)
        self.assertIn("총 3개의 일정", text)

    def test_empty_schedule(self):
        events = parse_today_events(SAMPLE_ICAL, date(2026, 7, 31))
        self.assertEqual(events, [])
        self.assertIn("등록된 일정이 없습니다", format_today_schedule(events, date(2026, 7, 31)))


if __name__ == "__main__":
    unittest.main()
