# 칸나 MCP 원본 -> 수정본 교체 (사용자 승인 후 실행). 실패하면 원본 APK 자동 재설치.
A="adb -s 127.0.0.1:5555"
PKG=com.pastel.aipet.kanna
cd ~/kanna
[ -s kanna-mod.apk ] && [ -s kanna-2.2.apk ] && [ -d chars ] || { echo MISSING; exit 1; }
$A uninstall $PKG
if $A install kanna-mod.apk; then echo INSTALL_MOD_OK; else echo MOD_FAIL_RESTORE; $A install kanna-2.2.apk; exit 1; fi
$A shell appops set $PKG SYSTEM_ALERT_WINDOW allow
$A shell pm grant $PKG android.permission.POST_NOTIFICATIONS
$A shell pm grant $PKG com.termux.permission.RUN_COMMAND
D=/sdcard/Android/data/$PKG/files/chars
$A shell mkdir -p $D
for d in chars/*/; do $A push "$d" $D/ >/dev/null && echo "pushed $d"; done
$A shell ls $D
$A shell am start -n $PKG/com.local.mcpcontroller.MainActivity >/dev/null
echo STEP6_OK
