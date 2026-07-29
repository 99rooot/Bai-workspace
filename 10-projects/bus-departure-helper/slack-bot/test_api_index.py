import unittest
from urllib.error import HTTPError, URLError

from api.index import safe_error_code


class ApiIndexTest(unittest.TestCase):
    def test_calendar_error_codes_do_not_include_secret_values(self):
        http_error = HTTPError("https://calendar.google.com/private", 404, "missing", {}, None)
        self.assertEqual(safe_error_code(http_error, True), "calendar_http_404")
        self.assertEqual(
            safe_error_code(URLError("private calendar address"), True),
            "calendar_connection_error",
        )
        self.assertEqual(
            safe_error_code(ValueError("private event contents"), True),
            "calendar_format_error",
        )

    def test_bus_error_is_generic(self):
        self.assertEqual(safe_error_code(RuntimeError("internal detail"), False), "bus_request_error")


if __name__ == "__main__":
    unittest.main()
