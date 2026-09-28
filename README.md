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
