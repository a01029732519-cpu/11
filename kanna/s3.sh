set -e
cd ~/kanna
rm -f /sdcard/Download/kp_*
split -b 8000000 kanna-2.2.apk /sdcard/Download/kp_
ls -la /sdcard/Download/kp_*
echo STEP3_OK
