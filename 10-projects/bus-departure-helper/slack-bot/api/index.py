"""Vercel endpoint for Slack Events API."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bus_logic import fetch_4401_minutes, fetch_yeonsu01_minutes, slack_reply, wants_to_go_home  # noqa: E402
from calendar_logic import today_schedule_reply, wants_today_schedule  # noqa: E402


def safe_error_code(error: Exception, schedule_requested: bool) -> str:
    if not schedule_requested:
        return "bus_request_error"
    if isinstance(error, HTTPError):
        return f"calendar_http_{error.code}"
    if isinstance(error, URLError):
        return "calendar_connection_error"
    if isinstance(error, UnicodeDecodeError):
        return "calendar_encoding_error"
    if isinstance(error, ValueError):
        return "calendar_format_error"
    if isinstance(error, TimeoutError):
        return "calendar_timeout"
    if isinstance(error, RuntimeError):
        return "calendar_configuration_error"
    return "calendar_unknown_error"


def valid_slack_signature(timestamp: str, signature: str, body: bytes) -> bool:
    secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not secret or not timestamp or not signature:
        return False
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    base = b"v0:" + timestamp.encode("utf-8") + b":" + body
    expected = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def post_slack_message(channel: str, text: str, thread_ts: str | None = None) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN이 설정되지 않았습니다.")
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    request = Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urlopen(request, timeout=8) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"Slack 답장 실패: {result.get('error', 'unknown_error')}")


class handler(BaseHTTPRequestHandler):
    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        timestamp = self.headers.get("X-Slack-Request-Timestamp", "")
        signature = self.headers.get("X-Slack-Signature", "")
        if not valid_slack_signature(timestamp, signature, body):
            self.send_json({"error": "invalid_signature"}, 401)
            return

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({"error": "invalid_json"}, 400)
            return

        if payload.get("type") == "url_verification":
            self.send_json({"challenge": payload.get("challenge", "")})
            return

        event = payload.get("event") or {}
        if event.get("type") not in {"message", "app_mention"} or event.get("bot_id") or event.get("subtype"):
            self.send_json({"ok": True})
            return
        text = str(event.get("text") or "")
        schedule_requested = wants_today_schedule(text)
        bus_requested = wants_to_go_home(text)
        if not schedule_requested and not bus_requested:
            self.send_json({"ok": True})
            return

        try:
            if schedule_requested:
                calendar_url = os.environ.get("GOOGLE_CALENDAR_ICAL_URL", "")
                if not calendar_url:
                    raise RuntimeError("Google Calendar 읽기 설정이 필요합니다.")
                reply = today_schedule_reply(calendar_url)
            else:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    bus_4401 = executor.submit(fetch_4401_minutes)
                    yeonsu01 = executor.submit(fetch_yeonsu01_minutes)
                    arrival_4401 = bus_4401.result()
                    arrival_yeonsu01 = yeonsu01.result()
                reply = slack_reply(arrival_4401=arrival_4401, arrival_yeonsu01=arrival_yeonsu01)
            post_slack_message(str(event["channel"]), reply, event.get("thread_ts"))
            self.send_json({"ok": True})
        except (KeyError, OSError, RuntimeError, TimeoutError, ValueError) as error:
            error_code = safe_error_code(error, schedule_requested)
            print(f"request_failed code={error_code}", file=sys.stderr)
            self.send_json({"error": error_code}, 500)
