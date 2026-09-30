# tg-mcp 코드만 교체 (봇 토큰 등 시크릿은 서버 것을 유지) + 연결 테스트
set -e
SHA=__SHA__
R=https://raw.githubusercontent.com/a01029732519-cpu/11/$SHA/tgmcp
cd ~/tg-mcp
rm -rf src.bak && cp -r src src.bak
for f in mcp format tools; do curl -sfLo src/$f.js $R/src/$f.js; done
curl -sfLo scripts/redeploy.mjs $R/scripts/redeploy.mjs
grep -c "미러링" src/mcp.js src/tools.js
export CF_API_TOKEN=$(grep ^CF_API_TOKEN= ~/rbx/.env | cut -d= -f2-)
node scripts/redeploy.mjs
sleep 3
U=$(grep '^테스트' .connector-urls | sed 's/^[^:]*: *//')
curl -s -o /dev/null -w 'test_http=%{http_code}\n' "$U"
echo STEP11_OK
