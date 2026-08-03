"""Vercel Cron endpoint that sends tomorrow's calendar schedule to Slack."""

from __future__ import annotations

import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calendar_logic import fetch_calendar_text  # noqa: E402
from notification_logic import tomorrow_notification  # noqa: E402
from slack_client import post_slack_message  # noqa: E402


def valid_cron_authorization(header: str, cron_secret: str) -> bool:
    if not header or not cron_secret:
        return False
    return hmac.compare_digest(header, f"Bearer {cron_secret}")


class handler(BaseHTTPRequestHandler):
    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        cron_secret = os.environ.get("CRON_SECRET", "")
        authorization = self.headers.get("Authorization", "")
        if not valid_cron_authorization(authorization, cron_secret):
            self.send_json({"error": "invalid_cron_authorization"}, 401)
            return

        calendar_url = os.environ.get("GOOGLE_CALENDAR_ICAL_URL", "")
        slack_channel = os.environ.get("SLACK_DM_CHANNEL_ID", "")
        if not calendar_url or not slack_channel:
            self.send_json({"error": "notification_configuration_missing"}, 500)
            return

        try:
            calendar_text = fetch_calendar_text(calendar_url)
            message = tomorrow_notification(calendar_text)
            if message is None:
                self.send_json({"ok": True, "sent": False, "reason": "no_events"})
                return
            post_slack_message(slack_channel, message)
            self.send_json({"ok": True, "sent": True})
        except (OSError, RuntimeError, TimeoutError, ValueError):
            print("notification_failed code=tomorrow_schedule_error", file=sys.stderr)
            self.send_json({"error": "tomorrow_schedule_error"}, 500)
