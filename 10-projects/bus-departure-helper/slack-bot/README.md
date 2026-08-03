# Slack 버스·일정 봇

## 목표

휴대폰 Slack에서 봇에게 메시지를 보내면 맥이나 같은 Wi-Fi 없이 학교→집 버스 정보 또는 오늘의 Google Calendar 일정을 답장받는다.

## 동작

1. Slack이 메시지 이벤트를 Vercel 함수로 보낸다.
2. 함수가 `집에 가고 싶다`, `집 가자`, `집에 갈래` 같은 문구를 감지한다.
3. 인천버스정보시스템에서 송도국제도서관 방향별 정류장의 연수01과 4401 정보를 각각 조회한다.
4. 연수01 실시간 정보가 있으면 우선 사용하고, 없으면 예상표와 비교해 Slack 대화에 답장한다.

일정 조회는 다음과 같이 동작한다.

1. Slack DM에서 `오늘 일정 알려줘`, `내일 일정 알려줘`, `이번 주 일정 알려줘`, `다음 주 일정 알려줘` 중 하나를 보낸다.
2. Vercel 함수가 Google Calendar의 비공개 iCal 주소를 읽는다.
3. 오늘의 종일 일정과 시간 일정을 정리해 같은 DM으로 답장한다.

첫 버전은 읽기 전용이다. 일정을 생성·수정·삭제하지 않는다.

매일 밤 11시(KST)에는 Vercel Cron이 다음 날 일정을 확인한다. 내일 일정이 있을 때만 기존 봇 DM으로 미리 알림을 보내고, 일정이 없으면 메시지를 보내지 않는다.

연수01은 `164000811`, 4401은 `164000809` 정류장을 사용한다. 오전에 연수01 실시간 도착 분이 없으면 인천대입구역 기점 첫차가 06:30에 출발한다는 참고 정보와 직접 확인 안내를 보여준다. 06:30은 송도국제도서관 도착 시각이 아니다.

- 연수01은 운행 전에는 인천대입구역 기점 출발 시각 06:30을 안내하고, 운행 중 API에 송도국제도서관 도착 예정 분이 있으면 실시간 값으로 바꾼다.
- 4401은 고정 예상표 대신 정류장 API의 실시간 도착 예정 분을 사용한다.
- Slack 답장에는 두 정보가 어떤 기준인지 함께 표시한다.

## 필요한 Slack 앱 설정

1. [Slack API 앱 페이지](https://api.slack.com/apps)에서 `Create New App`을 선택한다.
2. `From scratch`로 앱을 만들고 사용할 워크스페이스를 선택한다.
3. `OAuth & Permissions`의 Bot Token Scopes에 아래 권한을 추가한다.
   - `chat:write`
   - `im:history`
   - 채널 멘션도 사용할 경우 `channels:history`, `app_mentions:read`
4. 앱을 워크스페이스에 설치한다.
5. 설치 후 나오는 Bot User OAuth Token은 복사만 하고 파일에는 저장하지 않는다.

## Vercel 설정

Vercel에서 이 `slack-bot` 폴더를 프로젝트 루트로 배포한다. 환경변수는 Vercel 화면에서만 설정한다.

```text
SLACK_BOT_TOKEN=xoxb로 시작하는 Bot User OAuth Token
SLACK_SIGNING_SECRET=Slack 앱 Basic Information의 Signing Secret
GOOGLE_CALENDAR_ICAL_URL=Google Calendar의 비공개 iCal 주소
CRON_SECRET=Vercel 예약 주소를 보호할 임의의 긴 값
SLACK_DM_CHANNEL_ID=알림을 받을 기존 봇 DM의 D로 시작하는 채널 ID
```

`GOOGLE_CALENDAR_ICAL_URL`은 캘린더 내용을 읽을 수 있는 비밀정보다. 채팅, 코드, GitHub에 붙여넣지 않고 Vercel 환경 변수 화면에만 입력한다. 주소가 노출되면 Google Calendar 설정에서 비공개 주소를 재설정한다.

`CRON_SECRET`은 16자 이상의 임의 값으로 만들고 Sensitive Production 환경 변수로 저장한다. `SLACK_DM_CHANNEL_ID`는 기존 봇 DM의 Slack 웹 주소에서 `D`로 시작하는 마지막 값을 사용한다.

배포 후 주소가 `https://내프로젝트.vercel.app`이라면 Slack Request URL은 다음과 같다.

```text
https://내프로젝트.vercel.app/slack/events
```

## Event Subscriptions

1. Slack 앱 설정에서 `Event Subscriptions`를 켠다.
2. Request URL에 Vercel의 `/slack/events` 주소를 입력하고 Verified를 확인한다.
3. `Subscribe to bot events`에 `message.im`을 추가한다.
4. 채널 멘션도 사용하려면 `app_mention`을 추가한다.
5. 권한이 바뀌었다면 앱을 워크스페이스에 다시 설치한다.

## 확인

Slack 앱과의 DM에서 아래처럼 보낸다.

```text
나 이제 집에 가고 싶다
```

아래 형식의 답장이 오면 성공이다.

```text
학교 → 집 버스 · 15분 뒤 출발
연수01 15:33 기준입니다.
15:05 기준
```

일정 조회는 다음처럼 확인한다.

```text
오늘 일정 알려줘
내일 일정 알려줘
이번 주 일정 알려줘
다음 주 일정 알려줘
```

아래 형식의 답장이 오면 성공이다.

```text
오늘 일정 · 7월 29일

• 09:00 · 수업
• 18:30 · 운동

총 2개의 일정이 있습니다.
```

## 보안

- 실제 Slack 토큰과 Signing Secret은 저장소 파일에 쓰지 않는다.
- Google Calendar 비공개 iCal 주소를 저장소 파일에 쓰지 않는다.
- Slack 요청 서명을 검증하고 5분이 지난 요청은 거부한다.
- 봇은 DM에서 필요한 메시지만 읽도록 최소 권한으로 시작한다.
