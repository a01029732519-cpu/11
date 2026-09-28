# 캐릭터 zip -> 스프라이트 시트 변환 (~/kanna/chars)
set -e
cd ~/kanna
curl -sfLo conv.py https://raw.githubusercontent.com/a01029732519-cpu/11/claude/awesome-carson-wta984/kanna/conv.py
Z=$(ls /sdcard/Download/*128*44*.zip | head -1)
echo "zip: $Z"
rm -rf chars
python conv.py "$Z" ~/kanna/chars > conv.log 2>&1 || { tail -20 conv.log; exit 1; }
grep -E '^==|box|skip' conv.log
du -sh chars/*
echo STEP5_OK
