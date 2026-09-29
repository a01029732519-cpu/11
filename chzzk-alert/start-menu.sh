#!/usr/bin/env sh
# 스텔라 멤버 메뉴를 백그라운드로 실행 (Termux). 다시 실행하면 재시작됨.
cd "$(dirname "$0")" || exit 1
command -v termux-wake-lock >/dev/null && termux-wake-lock
pkill -f "stella_menu.py" 2>/dev/null
nohup python -u stella_menu.py >> menu.log 2>&1 &
echo "메뉴 실행됨 (pid $!) — 로그: $(pwd)/menu.log"
