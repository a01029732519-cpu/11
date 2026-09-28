# 1단계: 설치된 칸나 앱 APK 꺼내기 → 다운로드 폴더
set -e
mkdir -p ~/kanna; cd ~/kanna
P=$(adb -s 127.0.0.1:5555 shell pm path com.pastel.aipet.kanna | sed 's/package://' | tr -d '\r')
adb -s 127.0.0.1:5555 pull "$P" kanna-2.2.apk >/dev/null
ls -la kanna-2.2.apk; sha256sum kanna-2.2.apk | cut -c1-16
cp kanna-2.2.apk /sdcard/Download/
echo STEP1_OK
