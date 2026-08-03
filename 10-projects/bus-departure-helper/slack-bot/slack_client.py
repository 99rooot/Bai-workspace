"""Minimal Slack Web API client shared by event and cron functions."""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen


def post_slack_message(channel: str, text: str, thread_ts: str | None = None) -> None:
    slack_token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not slack_token:
        raise RuntimeError("SLACK_BOT_TOKEN이 설정되지 않았습니다.")
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    request = Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {slack_token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urlopen(request, timeout=8) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"Slack 답장 실패: {result.get('error', 'unknown_error')}")
