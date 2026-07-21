"""School-to-home bus decision logic for the Slack bot."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


KST = timezone(timedelta(hours=9))
ARRIVAL_URL = "https://bus.incheon.go.kr/inq/selectArrivalInfoList.do"
BUS_4401_STOP_ID = "164000809"
BUS_4401_ROUTE_ID = "161000027"
YEONSU01_STOP_ID = "164000811"
YEONSU01_ROUTE_ID = "161000034"
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


def fetch_route_minutes(stop_id: str, route_no: str, route_id: str, timeout: int = 8) -> int | None:
    body = urlencode({"bstopid": stop_id}).encode("utf-8")
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
        if str(item.get("routeno") or "") != route_no:
            continue
        if str(item.get("routeid") or "") != route_id:
            continue
        value = str(item.get("arrplantm") or "").strip()
        if value.isdigit():
            arrivals.append(int(value))
    return min(arrivals) if arrivals else None


def fetch_4401_minutes(timeout: int = 8) -> int | None:
    return fetch_route_minutes(BUS_4401_STOP_ID, "4401", BUS_4401_ROUTE_ID, timeout)


def fetch_yeonsu01_minutes(timeout: int = 8) -> int | None:
    return fetch_route_minutes(YEONSU01_STOP_ID, "연수01", YEONSU01_ROUTE_ID, timeout)


def decide(now: datetime, arrival_4401: int | None, arrival_yeonsu01: int | None = None) -> dict[str, str]:
    now_minutes = now.hour * 60 + now.minute
    schedule = [minutes(value) for value in YEONSU01_SCHEDULE]
    lead = WALK_MINUTES + BUFFER_MINUTES
    next_yeonsu = next((value for value in schedule if value >= now_minutes + lead), None)

    if arrival_yeonsu01 is not None:
        if arrival_yeonsu01 >= lead:
            leave_in = arrival_yeonsu01 - lead
            title = "지금 출발" if leave_in == 0 else f"{leave_in}분 뒤 출발"
            return {
                "title": title,
                "message": f"연수01이 {arrival_yeonsu01}분 뒤 도착 예정입니다. 실시간 정보를 기준으로 안내했습니다.",
            }
        return {
            "title": "연수01은 빠듯",
            "message": f"연수01이 {arrival_yeonsu01}분 뒤라 학교 출발 기준 {lead}분보다 빠릅니다. 4401 정보도 함께 확인하세요.",
        }

    if now_minutes < 13 * 60 + 13:
        if now_minutes < 6 * 60 + 30:
            if arrival_4401 is not None and arrival_4401 >= lead:
                leave_4401 = arrival_4401 - lead
                return {
                    "title": "4401 추천",
                    "message": f"연수01 운행 전입니다. 4401은 {arrival_4401}분 뒤라 {leave_4401}분 뒤 출발하면 됩니다.",
                }
            if arrival_4401 is not None:
                return {
                    "title": "4401은 빠듯",
                    "message": f"연수01 운행 전이고 4401은 {arrival_4401}분 뒤라 학교 출발 기준 {lead}분보다 빠릅니다.",
                }
            return {
                "title": "오전 첫차 안내",
                "message": "오늘 연수01 첫차는 06:30이며 평일 약 30분 간격으로 운행합니다. 운행 시작 후 다시 물어보면 실시간 도착 정보를 확인합니다.",
            }
        if arrival_4401 is not None and arrival_4401 >= lead:
            leave_4401 = arrival_4401 - lead
            return {
                "title": "4401 확인",
                "message": f"연수01은 오전에도 운행하지만 현재 실시간 도착 분이 없습니다. 4401은 {arrival_4401}분 뒤라 {leave_4401}분 뒤 출발하면 됩니다.",
            }
        return {
            "title": "연수01 운행 확인",
            "message": "연수01은 06:30 첫차이며 평일 약 30분 간격으로 운행합니다. 현재 실시간 도착 분은 확인되지 않아 버스 앱을 함께 확인하세요.",
        }

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


def slack_reply(
    now: datetime | None = None,
    arrival_4401: int | None = None,
    arrival_yeonsu01: int | None = None,
) -> str:
    checked_at = now or datetime.now(KST)
    result = decide(checked_at, arrival_4401, arrival_yeonsu01)
    time_text = checked_at.strftime("%H:%M")
    now_minutes = checked_at.hour * 60 + checked_at.minute
    if arrival_yeonsu01 is not None:
        yeonsu_status = f"{arrival_yeonsu01}분 뒤 (실시간 조회)"
    elif now_minutes < 6 * 60 + 30:
        yeonsu_status = "첫차 06:30 (운행 전 첫차 기준)"
    elif now_minutes < 13 * 60 + 13:
        yeonsu_status = "실시간 정보 없음 · 평일 약 30분 간격"
    else:
        schedule = [minutes(value) for value in YEONSU01_SCHEDULE]
        lead = WALK_MINUTES + BUFFER_MINUTES
        next_yeonsu = next((value for value in schedule if value >= now_minutes + lead), None)
        yeonsu_status = (
            f"{next_yeonsu // 60:02d}:{next_yeonsu % 60:02d} 예상"
            if next_yeonsu is not None
            else "오늘 예상표 종료"
        )
    bus_4401_status = (
        f"{arrival_4401}분 뒤 (실시간 조회)"
        if arrival_4401 is not None
        else "도착 예정 정보 없음 (실시간 조회 결과)"
    )
    return (
        f"*학교 → 집 버스 · {result['title']}*\n"
        f"{result['message']}\n"
        f"• 연수01: {yeonsu_status}\n"
        f"• 4401: {bus_4401_status}\n"
        f"_연수01은 운행 전에는 첫차 기준, 4401은 정류장 실시간 도착정보 기준_\n"
        f"_{time_text} 기준_"
    )
