"""School-to-home bus decision logic for the Slack bot."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


KST = timezone(timedelta(hours=9))
ARRIVAL_URL = "https://bus.incheon.go.kr/inq/selectArrivalInfoList.do"
STOP_ID = "164000809"
ROUTE_ID = "161000027"
ROUTE_NO = "4401"
WALK_MINUTES = 10
BUFFER_MINUTES = 3
YEONSU01_SCHEDULE = [
    "13:13", "13:43", "14:23", "14:52", "15:13", "15:33", "15:53",
    "16:13", "16:23", "16:44", "17:03", "18:04", "18:14", "18:33",
    "18:53", "19:13", "19:33", "19:53", "20:14", "20:34",
]


def wants_to_go_home(text: str) -> bool:
    compact = "".join(text.lower().split())
    phrases = ("집에가고싶", "집에갈래", "집에가자", "집가고싶", "집갈래", "집가자")
    return any(phrase in compact for phrase in phrases)


def minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def fetch_4401_minutes(timeout: int = 8) -> int | None:
    body = urlencode({"bstopid": STOP_ID}).encode("utf-8")
    request = Request(
        ARRIVAL_URL,
        data=body,
        headers={
            "User-Agent": "bus-departure-helper-slack/0.1",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    arrivals = []
    for item in data.get("resultList") or []:
        if str(item.get("routeno") or "") != ROUTE_NO:
            continue
        if str(item.get("routeid") or "") != ROUTE_ID:
            continue
        value = str(item.get("arrplantm") or "").strip()
        if value.isdigit():
            arrivals.append(int(value))
    return min(arrivals) if arrivals else None


def decide(now: datetime, arrival_4401: int | None) -> dict[str, str]:
    now_minutes = now.hour * 60 + now.minute
    schedule = [minutes(value) for value in YEONSU01_SCHEDULE]
    lead = WALK_MINUTES + BUFFER_MINUTES
    next_yeonsu = next((value for value in schedule if value >= now_minutes + lead), None)

    if next_yeonsu is None:
        if arrival_4401 is not None and arrival_4401 >= lead:
            leave_in = arrival_4401 - lead
            return {
                "title": "4401 추천",
                "message": f"연수01 예상표가 끝났습니다. 4401은 {arrival_4401}분 뒤 도착 예정이라 {leave_in}분 뒤 출발하면 됩니다.",
            }
        return {
            "title": "직접 확인 필요",
            "message": "연수01 예상표가 끝났고 탈 수 있는 4401 정보가 없습니다. 버스 앱을 한 번 확인하세요.",
        }

    next_text = f"{next_yeonsu // 60:02d}:{next_yeonsu % 60:02d}"
    leave_in = next_yeonsu - lead - now_minutes
    if 0 <= leave_in <= 20:
        title = "지금 출발" if leave_in == 0 else f"{leave_in}분 뒤 출발"
        return {"title": title, "message": f"연수01 {next_text} 기준입니다."}

    if arrival_4401 is not None and arrival_4401 >= lead:
        leave_4401 = arrival_4401 - lead
        return {
            "title": "4401 확인",
            "message": f"4401은 {arrival_4401}분 뒤 도착 예정입니다. 학교에서 {leave_4401}분 뒤 출발하면 됩니다.",
        }

    if arrival_4401 is not None and arrival_4401 < lead:
        return {
            "title": "4401은 빠듯",
            "message": f"4401은 {arrival_4401}분 뒤라 학교 출발 기준 {lead}분보다 빠릅니다. 다음 연수01은 {next_text} 예정입니다.",
        }

    return {
        "title": "상황 확인",
        "message": f"다음 연수01은 {next_text} 예정입니다. 현재 4401 도착 예정 분은 확인되지 않습니다.",
    }


def slack_reply(now: datetime | None = None, arrival_4401: int | None = None) -> str:
    checked_at = now or datetime.now(KST)
    result = decide(checked_at, arrival_4401)
    time_text = checked_at.strftime("%H:%M")
    return f"*학교 → 집 버스 · {result['title']}*\n{result['message']}\n_{time_text} 기준_"
