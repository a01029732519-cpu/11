set -e
cd ~/kanna
curl -sfLo conv2.py https://raw.githubusercontent.com/a01029732519-cpu/11/claude/awesome-carson-wta984/kanna/conv2.py
rm -rf chars2; python conv2.py > conv2.log 2>&1 || { tail -15 conv2.log; exit 1; }
cat conv2.log | tail -16
du -sh chars2/hebi
echo STEP7_OK
