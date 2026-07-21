import unittest
from datetime import datetime, timedelta, timezone

from bus_logic import decide, slack_reply, wants_to_go_home


KST = timezone(timedelta(hours=9))


class BusLogicTest(unittest.TestCase):
    def test_trigger_phrase(self):
        self.assertTrue(wants_to_go_home("나 이제 집에 가고 싶다"))
        self.assertTrue(wants_to_go_home("집 가자"))
        self.assertFalse(wants_to_go_home("오늘 점심 먹고 싶다"))

    def test_wait_for_yeonsu01(self):
        result = decide(datetime(2026, 7, 22, 15, 5, tzinfo=KST), None)
        self.assertEqual(result["title"], "15분 뒤 출발")

    def test_4401_option(self):
        result = decide(datetime(2026, 7, 22, 17, 10, tzinfo=KST), 20)
        self.assertEqual(result["title"], "4401 확인")
        self.assertIn("7분 뒤", result["message"])

    def test_slack_format(self):
        text = slack_reply(datetime(2026, 7, 22, 15, 5, tzinfo=KST), None)
        self.assertIn("*학교 → 집 버스", text)
        self.assertIn("_15:05 기준_", text)


if __name__ == "__main__":
    unittest.main()
