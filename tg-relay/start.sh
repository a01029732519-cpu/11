#!/data/data/com.termux/files/usr/bin/bash
# tg-relay 수동 실행 (중복 실행 방지, 로그는 ~/tg-relay/relay.log)
cd ~/tg-relay
termux-wake-lock 2>/dev/null || true
pkill -f 'node .*tg-relay/relay.mjs' 2>/dev/null
sleep 1
nohup node ~/tg-relay/relay.mjs >> ~/tg-relay/relay.log 2>&1 &
echo "started pid $!"
