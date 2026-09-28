#!/usr/bin/env bash
# 채팅 중계 Worker 배포 (wrangler 없이 Cloudflare API)
# 필요: ~/rbx/.env 의 CF_API_TOKEN (Roblox 중계 배포 때 만든 토큰)
# 결과: ../.env 에 RELAY_URL, RELAY_KEY 추가
set -euo pipefail
cd "$(dirname "$0")"
CF_API_TOKEN=$(grep '^CF_API_TOKEN=' ~/rbx/.env | cut -d= -f2-)
NAME=chzzk-chat-relay
API=https://api.cloudflare.com/client/v4
AUTH="Authorization: Bearer $CF_API_TOKEN"
ENVF=../.env

ACC=$(curl -s -H "$AUTH" "$API/accounts" | jq -r '.result[0].id')
KEY=$(grep '^RELAY_KEY=' $ENVF 2>/dev/null | cut -d= -f2- || true)
[ -n "$KEY" ] || KEY=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')

umask 077
jq -n --arg s "$KEY" '{main_module:"worker.js",compatibility_date:"2026-09-01",
  bindings:[{type:"secret_text",name:"SECRET",text:$s}]}' > meta.json
echo -n "업로드: "
curl -s -X PUT "$API/accounts/$ACC/workers/scripts/$NAME" -H "$AUTH" \
  -F "metadata=@meta.json;type=application/json" \
  -F "worker.js=@worker.js;type=application/javascript+module" | jq -c '{success, errors}'
rm -f meta.json
echo -n "workers.dev 켜기: "
curl -s -X POST "$API/accounts/$ACC/workers/scripts/$NAME/subdomain" -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"enabled":true,"previews_enabled":false}' | jq -c '{success, errors}'
SUB=$(curl -s -H "$AUTH" "$API/accounts/$ACC/workers/subdomain" | jq -r '.result.subdomain')
URL="https://$NAME.$SUB.workers.dev"

grep -v '^RELAY_URL=\|^RELAY_KEY=' $ENVF > $ENVF.tmp || true
{ cat $ENVF.tmp; echo "RELAY_URL=$URL"; echo "RELAY_KEY=$KEY"; } > $ENVF && rm -f $ENVF.tmp
chmod 600 $ENVF
echo "RELAY_URL=$URL"

for i in 1 2 3 4 5 6; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL/token?cid=x") || true
  [ "$code" = 401 ] && break
  echo "주소 활성화 대기... ($code)"; sleep 5
done
echo "키 없이 → HTTP $code (401 정상)"
