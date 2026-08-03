import unittest

from api.notify import valid_cron_authorization


class NotifyApiTest(unittest.TestCase):
    def test_cron_authorization(self):
        self.assertTrue(valid_cron_authorization("Bearer example-value", "example-value"))
        self.assertFalse(valid_cron_authorization("", "example-value"))
        self.assertFalse(valid_cron_authorization("Bearer wrong", "example-value"))
        self.assertFalse(valid_cron_authorization("Bearer example-value", ""))


if __name__ == "__main__":
    unittest.main()
