#!/usr/bin/env bash
# Termux / 리눅스에서 wrangler 없이 Cloudflare API 로 Worker 배포 + 동작 테스트
# 같은 폴더의 .env 필요: BOT_TOKEN, CHAT_ID, CF_API_TOKEN  (SECRET 은 없으면 자동 생성)
set -euo pipefail
cd "$(dirname "$0")"
. ./.env
: "${BOT_TOKEN:?}" "${CHAT_ID:?}" "${CF_API_TOKEN:?}"

NAME=roblox-telegram-relay
API=https://api.cloudflare.com/client/v4
AUTH="Authorization: Bearer $CF_API_TOKEN"

command -v jq >/dev/null || pkg install -y jq

step() { echo; echo "== $* =="; }

step "1. 토큰 확인"
curl -s -H "$AUTH" "$API/user/tokens/verify" | jq -c '{success, status: .result.status}'

step "2. 계정 ID"
ACC=$(curl -s -H "$AUTH" "$API/accounts" | jq -r '.result[0].id')
echo "account_id=$ACC"

if [ -z "${SECRET:-}" ]; then
  SECRET=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
  echo "SECRET=$SECRET" >> .env
  echo "SECRET 새로 생성 → .env 에 저장"
fi

step "3. Worker 업로드"
umask 077
jq -n --arg c "$CHAT_ID" --arg t "$BOT_TOKEN" --arg s "$SECRET" '{
  main_module: "worker.js",
  compatibility_date: "2026-09-01",
  bindings: [
    {type: "plain_text",  name: "CHAT_ID",   text: $c},
    {type: "secret_text", name: "BOT_TOKEN", text: $t},
    {type: "secret_text", name: "SECRET",    text: $s}
  ]}' > meta.json
curl -s -X PUT "$API/accounts/$ACC/workers/scripts/$NAME" -H "$AUTH" \
  -F "metadata=@meta.json;type=application/json" \
  -F "worker.js=@worker.js;type=application/javascript+module" \
  | jq -c '{success, errors}'
rm -f meta.json

step "4. workers.dev 주소 켜기"
SUB=$(curl -s -H "$AUTH" "$API/accounts/$ACC/workers/subdomain" | jq -r '.result.subdomain // empty')
if [ -z "$SUB" ]; then echo "workers.dev 서브도메인이 없음 (대시보드 Workers 메뉴에서 한 번 만들어야 함)"; exit 1; fi
curl -s -X POST "$API/accounts/$ACC/workers/scripts/$NAME/subdomain" -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"enabled":true,"previews_enabled":false}' \
  | jq -c '{success, errors}'
URL="https://$NAME.$SUB.workers.dev"
grep -q '^RELAY_URL=' .env || echo "RELAY_URL=$URL" >> .env
echo "RELAY_URL=$URL"

step "5. 동작 테스트 (Roblox 흉내)"
for i in 1 2 3 4 5 6; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL/poll") || true
  [ "$code" = 401 ] && break
  echo "주소 활성화 대기... ($code)"; sleep 5
done
echo "비밀키 없이 /poll → HTTP $code (401 이어야 정상)"
echo -n "/poll → "; curl -s -H "X-Secret: $SECRET" "$URL/poll?offset=0"; echo
echo -n "/send → "; curl -s -X POST -H "X-Secret: $SECRET" -H 'Content-Type: application/json' \
  -d '{"text":"✅ 중계 서버 배포 완료 (Termux 테스트)"}' "$URL/send"; echo

step "6. Roblox 스크립트 만들기 (주소·비밀키 채움)"
sed -e "s#https://roblox-telegram-relay.<내계정>.workers.dev#$URL#" \
    -e "s#여기에_SECRET_값#$SECRET#" TelegramBridge.server.lua > TelegramBridge.ready.lua
curl -s -F chat_id="$CHAT_ID" -F document=@TelegramBridge.ready.lua \
  -F caption="Roblox Studio → ServerScriptService 에 Script 로 붙여넣기" \
  "https://api.telegram.org/bot$BOT_TOKEN/sendDocument" | jq -c '{ok, description}'
echo "완료: 텔레그램으로 TelegramBridge.ready.lua 보냄"
