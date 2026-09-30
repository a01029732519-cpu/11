# tg-mcp 수정본 적용: Claude 활동 전체 미러링 규칙 + 긴 글 분할 + 비밀값 가리기
# 사용: bash s10.sh <BOT_TOKEN>   (토큰은 저장소에 올리지 않음)
set -e
[ -n "$1" ] || { echo "usage: bash s10.sh <BOT_TOKEN>"; exit 1; }
SHA=__SHA__
R=https://raw.githubusercontent.com/a01029732519-cpu/11/$SHA/tgmcp/src
cd ~/tg-mcp
rm -rf src.bak && cp -r src src.bak
for f in mcp format tools; do curl -sfLo src/$f.js $R/$f.js; done
grep -c "미러링" src/mcp.js src/tools.js
CF=$(grep ^CF_API_TOKEN= ~/rbx/.env | cut -d= -f2-)
printf '%s\n%s\n\n' "$CF" "$1" | bash setup.sh 2>&1 | tail -12
echo STEP10_OK
