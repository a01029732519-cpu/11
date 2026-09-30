# tg-relay 설치: 코드 받기 + .env 만들기(봇 토큰은 클립보드에서 읽음) + 지금 한 번 실행
set -e
SHA=__SHA__
R=https://raw.githubusercontent.com/a01029732519-cpu/11/$SHA/tg-relay
mkdir -p ~/tg-relay
cd ~/tg-relay
curl -sfLo relay.mjs $R/relay.mjs
curl -sfLo start.sh $R/start.sh && chmod +x start.sh
if [ ! -s .env ]; then
  T=$(termux-clipboard-get | tr -d '[:space:]')
  echo "$T" | grep -Eq '^[0-9]+:[A-Za-z0-9_-]{30,}$' || { echo "CLIPBOARD_NOT_TOKEN"; exit 1; }
  (umask 077; printf 'BOT_TOKEN=%s\nCHAT_ID=8891258606\n' "$T" > .env)
  termux-clipboard-set " "
  echo "env written"
fi
bash start.sh
sleep 6
tail -5 relay.log
echo RELAY_SETUP_OK
