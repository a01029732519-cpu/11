#!/usr/bin/env sh
# 알림 프로그램을 백그라운드로 실행 (Termux). 다시 실행하면 재시작됨.
cd "$(dirname "$0")" || exit 1
command -v termux-wake-lock >/dev/null && termux-wake-lock
pkill -f "node alert.mjs" 2>/dev/null
nohup node alert.mjs >> alert.log 2>&1 &
echo "실행됨 (pid $!) — 로그: $(pwd)/alert.log"
