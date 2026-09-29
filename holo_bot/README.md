# holo_bot — 홀로라이브 멤버 정보 · 방송 · X 텔레그램 봇

홀로라이브 멤버의 **프로필 · 방송 상태 · X · YouTube** 를 알려주는 텔레그램 봇입니다.
안드로이드 **Termux** 에서 돌아가며, 파이썬 표준 라이브러리만 사용합니다 (pip 설치 불필요).

- 멤버 정보는 **홀로라이브 공식 사이트**(hololive.hololivepro.com)에서 직접 가져와 `members.json` 에 저장하고 24시간마다 자동 갱신합니다.
  → 새 멤버 데뷔 / 졸업이 있어도 코드 수정 없이 반영됩니다.
- **방송 상태**는 [Holodex](https://holodex.net) API 로 1분마다 확인합니다 (`holodex_key.txt` 필요).
  Holodex 가 안 되면 알림 켠 멤버만 유튜브 채널 페이지로 직접 확인합니다
  (유튜브 페이지가 커서 데이터를 아끼려고 5분마다 10채널씩 돌아가며, 필요한 부분까지만 읽음 → 알림이 늦을 수 있음).
- Holodex API 키는 기한이 없습니다. 계정 페이지에서 **새 API 키 얻기를 다시 누르면** 이전 키가 24시간 안에 끊기니 누르지 마세요.
- **X 새 글**은 폰의 X 앱 알림을 `termux-notification-list`(Termux:API)로 읽어서 전달합니다
  (X 는 비로그인 조회를 막아서, 스텔라 알림과 같은 방식). 폰 X 앱에서 그 멤버 알림 🔔 을 켜둬야 합니다.
- 최근 영상은 YouTube 공개 RSS 피드로 가져옵니다.

## 기능

| 명령어 | 설명 |
|--------|------|
| `/start`, `/menu` | 메뉴: 🔴 방송 중 · 📅 예정 방송 · 🔔 내 알림 · 그룹별 멤버 목록 |
| `/live` | 지금 방송 중인 멤버 (제목 · 시청자 수) |
| `/schedule` | 예정 방송 (24시간) |
| `/alerts` | 내 알림 설정 |
| `/search 이름` | 멤버 검색 (영어/일본어 이름, 일부만 입력 가능) |
| `/x 이름`, `/yt 이름` | X · YouTube 링크 |
| `/refresh` | 공식 사이트에서 정보 새로고침 (10분에 한 번) |
| `/help` | 도움말 |

- 멤버 카드: 사진 + 프로필 + **🔴 방송 중이면 방송 제목과 바로가기**, 예정 방송, YouTube / X / 공식 프로필 버튼, 📺 최근 영상, **🔔 알림 켜기/끄기**
- **🔔 알림**: 켠 멤버가 방송을 시작하거나 X 에 글을 올리면 텔레그램으로 알려줍니다.
  그룹 화면의 **🔔 전체 알림 켜기** 로 한 번에 켤 수 있습니다. (처음엔 전부 꺼져 있음)
- 개인 채팅에서는 명령어 없이 이름만 보내도 검색됩니다. 예: `pekora`, `ぺこら`, `marine`
- 표시: 🔴 방송 중 · 🔔 알림 켬 · 🎓 졸업 · 🤝 어필리에이트 · 💤 활동 종료

## Termux 설치

1. 텔레그램 **@BotFather** → `/newbot` → 이름 `holo_bot` → 토큰 복사
   (아이디 `@holo_bot` 은 이미 누가 쓰고 있어서 현재 봇은 **@hebist_holo_bot** 입니다)
2. Termux 에서:

```bash
curl -fsSLO https://raw.githubusercontent.com/a01029732519-cpu/11/ccr-94b2240a-qx71ec/holo_bot/install.sh
bash install.sh
```

봇 토큰과 Holodex 키를 물어보면 붙여넣고 Enter. `~/holo_bot` 에 설치되고 바로 백그라운드로 실행됩니다.
(첫 실행은 공식 사이트에서 멤버 정보를 받느라 1~2분 걸립니다.)

## 관리

```bash
~/holo_bot/start.sh          # 실행 (이미 실행 중이면 그대로)
~/holo_bot/stop.sh           # 종료
tail -f ~/holo_bot/holo_bot.log   # 로그 보기
python ~/holo_bot/holo_bot.py --scrape   # 멤버 데이터만 새로 받아서 그룹별 명단 출력
python ~/holo_bot/holo_bot.py --check    # Holodex · 유튜브 · 폰 알림 연결 점검
```

- Holodex API 키: holodex.net 로그인 → 계정 페이지(holodex.net/login) → **새 API 키 얻기** → `~/holo_bot/holodex_key.txt` 에 저장.

- `termux-wake-lock` 으로 화면이 꺼져도 계속 돌아갑니다.
- **Termux:Boot** 앱을 한 번 열어두면 폰을 재부팅해도 자동으로 다시 켜집니다 (`~/.termux/boot/holo_bot`).
- 봇 토큰(`token.txt`)과 Holodex 키(`holodex_key.txt`)는 폰에만 저장되고 저장소에는 올라가지 않습니다.
- 알림 설정은 `subs.json`, 알린 방송 기록은 `live_state.json` 에 저장됩니다.
