# 칸나/헤비 2선택 수정본 빌드 + 덮어쓰기 설치(-r, 같은 서명키라 설정 유지) + 헤비 파일 복사
set -e
R=https://raw.githubusercontent.com/a01029732519-cpu/11/claude/awesome-carson-wta984/kanna
cd ~
curl -sfLo s4.sh $R/s4.sh && bash s4.sh 2>&1 | tail -4
A="adb -s 127.0.0.1:5555"
PKG=com.pastel.aipet.kanna
cd ~/kanna
[ -d chars2/hebi ] || { echo NO_HEBI; exit 1; }
$A install -r kanna-mod.apk
$A shell appops set $PKG SYSTEM_ALERT_WINDOW allow
D=/sdcard/Android/data/$PKG/files/chars
$A shell mkdir -p $D
$A push chars2/hebi $D/ >/dev/null
$A shell chmod -R 777 $D
$A shell ls $D/hebi | head -30
$A shell am start -n $PKG/com.local.mcpcontroller.MainActivity >/dev/null
echo STEP8_OK
