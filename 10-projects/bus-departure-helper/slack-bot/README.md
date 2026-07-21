# Slack 학교→집 버스 봇

## 목표

휴대폰 Slack에서 봇에게 `집에 가고 싶다`라고 보내면 맥이나 같은 Wi-Fi 없이 학교→집 버스 판단을 답장받는다.

## 동작

1. Slack이 메시지 이벤트를 Vercel 함수로 보낸다.
2. 함수가 `집에 가고 싶다`, `집 가자`, `집에 갈래` 같은 문구를 감지한다.
3. 인천버스정보시스템에서 송도국제도서관 방향별 정류장의 연수01과 4401 정보를 각각 조회한다.
4. 연수01 실시간 정보가 있으면 우선 사용하고, 없으면 예상표와 비교해 Slack 대화에 답장한다.

연수01은 `164000811`, 4401은 `164000809` 정류장을 사용한다. 오전에 연수01 실시간 도착 분이 없으면 첫차 06:30, 평일 약 30분 간격이라는 운행 참고 정보와 직접 확인 안내를 보여준다.

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
```

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

## 보안

- 실제 Slack 토큰과 Signing Secret은 저장소 파일에 쓰지 않는다.
- Slack 요청 서명을 검증하고 5분이 지난 요청은 거부한다.
- 봇은 DM에서 필요한 메시지만 읽도록 최소 권한으로 시작한다.
