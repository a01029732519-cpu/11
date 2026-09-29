#!/data/data/com.termux/files/usr/bin/bash
# 실행 중인 holo_bot 종료
DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$DIR/holo_bot.pid"

PID="$(cat "$PIDFILE" 2>/dev/null)"
if [ -n "$PID" ] && grep -q holo_bot.py "/proc/$PID/cmdline" 2>/dev/null; then
  kill "$PID" && echo "holo_bot 종료 (PID $PID)"
else
  echo "실행 중인 holo_bot 없음"
fi
rm -f "$PIDFILE"
