# tg-mcp 원래 코드로 되돌리기 (수정 전 백업 tgmcp.tgz 사용, 시크릿 유지)
set -e
cd ~/tg-mcp
tar xzf /sdcard/Download/tgmcp.tgz src/mcp.js src/format.js src/tools.js
grep -c "미러링" src/mcp.js src/tools.js || true
md5sum src/mcp.js src/format.js src/tools.js | cut -c1-12
export CF_API_TOKEN=$(grep ^CF_API_TOKEN= ~/rbx/.env | cut -d= -f2-)
node scripts/redeploy.mjs
U=$(grep '^테스트' .connector-urls | sed 's/^[^:]*: *//')
curl -s -o /dev/null -w 'test_http=%{http_code}\n' "$U"
echo STEP12_OK
