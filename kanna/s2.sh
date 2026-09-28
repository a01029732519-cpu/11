# 2단계: 그림(assets) 빼고 작은 APK 만들어 다운로드 폴더로
set -e
cd ~/kanna
command -v zip >/dev/null || pkg install -y zip >/dev/null 2>&1
cp kanna-2.2.apk small.apk
zip -dq small.apk 'assets/*'
ls -la small.apk
cp small.apk /sdcard/Download/kanna-small.apk
echo STEP2_OK
