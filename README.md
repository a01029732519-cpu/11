# Roblox ↔ Telegram 봇

```
텔레그램 앱 ──> Telegram 서버 <── Cloudflare Worker (중계) <── Roblox 서버 / Studio
```

Roblox는 텔레그램 서버에 직접 접속하지 않습니다. 중계 서버(Worker)만 거쳐서 통신합니다.
그래서 지금 쓰는 와이파이에서 텔레그램 IP가 막혀 있어도 `*.workers.dev`만 열려 있으면 동작합니다.
실제로 배포된 게임은 Roblox 서버에서 실행되므로 집 와이파이와 상관이 없습니다.

## 1. 봇 만들기
1. 텔레그램에서 `@BotFather` → `/newbot` → 토큰 받기
2. 만든 봇에게 아무 메시지나 한 번 보내기

## 2. 중계 서버 배포 (무료)
```bash
cd worker
npx wrangler login
npx wrangler secret put BOT_TOKEN   # BotFather 토큰
npx wrangler secret put SECRET      # 아무 긴 랜덤 문자열
npx wrangler deploy
```
내 채팅 ID 확인:
```bash
curl -H "X-Secret: <SECRET>" https://roblox-telegram-relay.<계정>.workers.dev/whoami
```
나온 `chat_id`를 `wrangler.toml`의 `CHAT_ID`에 넣고 다시 `npx wrangler deploy`.

### (대안) wrangler 없이 폰 Termux 에서 배포
`worker/` 폴더에 `.env` 를 만들고(`BOT_TOKEN=`, `CHAT_ID=`, `CF_API_TOKEN=` 각 한 줄) `bash deploy.sh` 를 실행합니다.
Cloudflare API 로 업로드하고, workers.dev 주소를 켜고, 동작 테스트까지 합니다.
마지막에는 주소와 비밀키를 채운 Roblox 스크립트를 텔레그램으로 보내줍니다.
`CF_API_TOKEN` 은 대시보드 → 내 프로필 → API 토큰 → "Cloudflare Workers 편집" 템플릿으로 만듭니다.

## 3. Roblox Studio
1. 홈 → 게임 설정 → 보안 → **HTTP 요청 허용** 켜기
2. `roblox/TelegramBridge.server.lua` 내용을 ServerScriptService 의 Script에 붙여넣기
3. `RELAY_URL`, `SECRET` 수정 → 플레이

## 명령어
| 명령 | 동작 |
|---|---|
| `/players` | 접속자 목록 |
| `/say 내용` | 게임 화면에 공지 |
| `/kick 이름` | 추방 |
| `/help` | 도움말 |

플레이어 접속/퇴장 알림도 자동으로 옵니다. 명령 추가는 스크립트의 `commands` 테이블에 함수를 넣으면 됩니다.

## 주의
- 명령을 가져가는 서버는 하나만 두는 것을 기준으로 만들었습니다. 게임 서버가 여러 개 켜져 있으면 명령이 그중 한 곳에만 전달됩니다.
- 와이파이에서 `workers.dev`까지 막혀 있으면 Studio 테스트는 휴대폰 핫스팟으로 하세요. 게임 서버에는 영향이 없습니다.

---

# 치지직 스텔라이브 알림 (`chzzk-alert/`)

스텔라이브 멤버가 방송을 켜거나, 방송 중인 멤버 채팅방에 다른 멤버가 채팅하면 텔레그램으로 알려줍니다.
알림에는 **📺 방송 보러가기** 인라인 버튼이 붙어서 바로 방송으로 들어갈 수 있습니다.
폰에 뜨는 **네이버 카페(스텔라이브) 새글 알림**과 **X 앱 알림(멤버 이름이 들어간 것)** 도 텔레그램으로 전달합니다.

- 치지직 공개 엔드포인트만 사용 → API 키 필요 없음
  (치지직 공식 Open API 는 다른 사람 채널의 채팅을 볼 수 없어서 이 용도에는 못 씀)
- 텔레그램은 보내기만 함(getUpdates 안 씀) → 같은 봇을 다른 프로그램이 써도 충돌 없음
- 의존성 없음 (Node 22 이상 내장 fetch/WebSocket)

## 설치 (Termux)
```sh
pkg install -y nodejs
cd ~/chzzk   # alert.mjs, members.json, start.sh 를 이 폴더에
printf 'BOT_TOKEN=...\nCHAT_ID=...\n' > .env && chmod 600 .env
node alert.mjs --test   # 테스트 알림 1개 + 채팅 서버 접속 확인
./start.sh              # 백그라운드 실행 (다시 실행하면 재시작)
```
폰 재부팅 후 자동 실행: `~/.termux/boot/chzzk-alert.sh` 에 `~/chzzk/start.sh` 한 줄 (Termux:Boot 앱 한 번 열어둬야 함).

## 설정 (`.env`)
| 키 | 기본값 | 설명 |
|---|---|---|
| `POLL_SEC` | 30 | 방송 상태 확인 간격(초) |
| `WATCH_CHAT` | 1 | 0 이면 채팅 알림 끔 |
| `ALERT_OWN_CHAT` | 0 | 1 이면 멤버가 자기 방송에서 치는 채팅도 알림 |
| `RELAY_URL` / `RELAY_KEY` | (없음) | 채팅 중계 Worker 주소/키. `relay/deploy.sh` 가 자동으로 채움 |
| `WATCH_NOTIF` | 1 | 0 이면 폰 알림 전달 끔 |
| `NOTIF_SEC` | 15 | 폰 알림 확인 간격(초) |
| `CAFE_NAMES` | 스텔라이브 | 전달할 네이버 카페 이름(쉼표로 여러 개) |
| `CAFE_ID` | tteokbokk1 | [📰 카페 열기] 버튼이 여는 카페 주소 (스텔라이브 공식 팬카페). 중계가 있으면 카페 앱으로 바로 열림 |
| `X_KEYWORDS` | (없음) | X 알림에서 멤버 이름 외에 찾을 키워드(영문 이름 등) |

### 폰 알림 전달 (카페 / X)
- 네이버 카페 앱의 새글 알림, X 앱의 알림을 `termux-notification-list` 로 읽어 전달합니다
  (카페 API 는 로그인이 필요하고 X 는 비로그인 조회를 막아서, 앱 알림을 쓰는 방식).
- 필요: `pkg install termux-api` + 설정 → 알림 접근 허용 → **Termux:API** 켜기.
- 카페는 해당 카페에서 멤버 새글 알림을 켜두고, X 는 멤버 계정 알림(🔔)을 켜두면 됩니다.
- 네이버 카페·X 이외 앱 알림은 읽기만 하고 버립니다.

### 채팅 중계 (채팅 서버가 막힌 와이파이)
`relay/deploy.sh` 를 실행하면 Cloudflare Worker(`chzzk-chat-relay`)를 배포하고 `.env` 에 주소/키를 넣습니다.
Worker 는 채팅 WebSocket 을 그대로 넘겨주기만 해서(패스스루) CPU 를 거의 안 씁니다.

멤버 추가/삭제는 `members.json` (치지직 채널 ID = 채널 주소의 32자리).
채팅 알림은 **방송 중인 멤버들의 채팅방**만 감시합니다 (멤버가 외부 스트리머 방송에서 치는 채팅은 못 봄).

> 일부 와이파이는 `*.game.naver.com` / `*.chat.naver.com` 을 IP 단위로 막습니다. 그런 곳에서는 방송 켜짐 알림만 오고,
> 채팅 알림은 모바일 데이터나 다른 네트워크로 바뀌면 자동으로 다시 붙습니다 (재시도 간격 15초 → 최대 5분).
