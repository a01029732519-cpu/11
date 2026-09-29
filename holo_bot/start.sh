#!/data/data/com.termux/files/usr/bin/bash
# holo_bot 을 백그라운드로 실행 (이미 실행 중이면 그대로 둠)
DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$DIR/holo_bot.pid"
LOG="$DIR/holo_bot.log"

if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE")"
  if [ -n "$PID" ] && grep -q holo_bot.py "/proc/$PID/cmdline" 2>/dev/null; then
    echo "holo_bot 이미 실행 중 (PID $PID)"
    exit 0
  fi
fi

# 로그가 1MB 넘으면 한 번 돌려둠
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 1048576 ]; then
  mv -f "$LOG" "$LOG.old"
fi

# 화면이 꺼져도 안드로이드가 Termux 를 재우지 않게
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

cd "$DIR" || exit 1
nohup python -u "$DIR/holo_bot.py" >> "$LOG" 2>&1 &
echo $! > "$PIDFILE"
echo "holo_bot 시작 (PID $!) — 로그 보기: tail -f $LOG"
