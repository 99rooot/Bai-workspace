import unittest
from datetime import datetime, timedelta, timezone

from notification_logic import tomorrow_notification


KST = timezone(timedelta(hours=9))

TOMORROW_EVENT = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART;TZID=Asia/Seoul:20260730T100000
DTEND;TZID=Asia/Seoul:20260730T110000
SUMMARY:내일 수업
END:VEVENT
END:VCALENDAR
"""

NO_TOMORROW_EVENT = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART;TZID=Asia/Seoul:20260731T100000
DTEND;TZID=Asia/Seoul:20260731T110000
SUMMARY:모레 수업
END:VEVENT
END:VCALENDAR
"""


class NotificationLogicTest(unittest.TestCase):
    def test_builds_tomorrow_notification_when_event_exists(self):
        message = tomorrow_notification(
            TOMORROW_EVENT,
            datetime(2026, 7, 29, 23, 0, tzinfo=KST),
        )
        self.assertIsNotNone(message)
        self.assertIn("*내일 일정 · 7월 30일*", message)
        self.assertIn("• 10:00 · 내일 수업", message)

    def test_skips_notification_when_tomorrow_is_empty(self):
        message = tomorrow_notification(
            NO_TOMORROW_EVENT,
            datetime(2026, 7, 29, 23, 0, tzinfo=KST),
        )
        self.assertIsNone(message)


if __name__ == "__main__":
    unittest.main()
