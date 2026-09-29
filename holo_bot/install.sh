#!/data/data/com.termux/files/usr/bin/bash
# Termux 에 holo_bot 설치: 파일 복사(또는 받기) → 토큰 저장 → 부팅 시 자동 실행 등록 → 실행
#   파일만 받아서 실행:  curl -fsSLO https://raw.githubusercontent.com/a01029732519-cpu/11/ccr-94b2240a-qx71ec/holo_bot/install.sh && bash install.sh
#   git clone 한 폴더에서 실행:  bash holo_bot/install.sh
set -eu
REF="${HOLO_BOT_REF:-ccr-94b2240a-qx71ec}"
RAW="https://raw.githubusercontent.com/a01029732519-cpu/11/$REF/holo_bot"
SRC="$(cd "$(dirname "$0")" && pwd)"
DIR="$HOME/holo_bot"

command -v python >/dev/null 2>&1 || pkg install -y python
mkdir -p "$DIR"
for f in holo_bot.py start.sh stop.sh; do
  if [ -f "$SRC/$f" ]; then
    [ "$SRC" = "$DIR" ] || cp -f "$SRC/$f" "$DIR/$f"
  elif [ -n "${GITHUB_TOKEN:-}" ]; then
    curl -fsSL -H "Authorization: token $GITHUB_TOKEN" "$RAW/$f" -o "$DIR/$f.new"
    mv -f "$DIR/$f.new" "$DIR/$f"
  else
    curl -fsSL "$RAW/$f" -o "$DIR/$f.new"
    mv -f "$DIR/$f.new" "$DIR/$f"
  fi
done
chmod 700 "$DIR/start.sh" "$DIR/stop.sh"

if [ ! -s "$DIR/token.txt" ]; then
  printf 'BotFather 에서 받은 봇 토큰을 붙여넣고 Enter: '
  read -r TOKEN < /dev/tty
  printf '%s\n' "$TOKEN" > "$DIR/token.txt"
fi
chmod 600 "$DIR/token.txt"

# 방송 알림용 Holodex API 키 (holodex.net/login → 새 API 키 얻기). 없으면 Enter
if [ ! -s "$DIR/holodex_key.txt" ]; then
  printf 'Holodex API 키 (없으면 그냥 Enter): '
  read -r HKEY < /dev/tty
  [ -n "$HKEY" ] && printf '%s\n' "$HKEY" > "$DIR/holodex_key.txt" && chmod 600 "$DIR/holodex_key.txt"
fi

# Termux:Boot 앱이 있으면 폰 재부팅 후에도 자동 실행
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/holo_bot" <<BOOT
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
"$DIR/start.sh"
BOOT
chmod 700 "$HOME/.termux/boot/holo_bot"

"$DIR/stop.sh" >/dev/null 2>&1 || true
"$DIR/start.sh"
