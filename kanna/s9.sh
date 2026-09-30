# 헤비 그림을 APK 안(assets/hebi2)에 포함한 자체 완결형 수정본 빌드 + 덮어쓰기 설치(-r, 같은 서명키)
set -e
R=https://raw.githubusercontent.com/a01029732519-cpu/11/963e59d58ffb7ea3e9122ed6d566c4ead36615ec/kanna
cd ~/kanna
[ -f chars2/hebi/idle.png ] || { echo NO_HEBI; exit 1; }
rm -rf m; mkdir m; cd m
for f in classes.dex classes2.dex classes3.dex; do curl -sfLo $f $R/dex/$f; done
sha256sum classes3.dex | cut -c1-16; echo want 66b158c74967118d
cp ../kanna-2.2.apk u.apk
zip -dq u.apk 'META-INF/*.SF' 'META-INF/*.RSA' 'META-INF/*.DSA' 'META-INF/*.EC' 'META-INF/MANIFEST.MF' 'classes*.dex' || true
zip -q u.apk classes.dex classes2.dex classes3.dex
mkdir -p a/assets/hebi2
cp ../chars2/hebi/*.png ../chars2/hebi/*.txt a/assets/hebi2/
rm -f a/assets/hebi2/name.txt
(cd a && zip -qr ../u.apk assets/hebi2)
unzip -l u.apk | grep -c 'assets/hebi2/'
zipalign -f -p 4 u.apk al.apk
apksigner sign --ks ../key.jks --ks-pass pass:kanna123 --out ../kanna-mod.apk al.apk
apksigner verify ../kanna-mod.apk && ls -la ../kanna-mod.apk
cp ../kanna-mod.apk /sdcard/Download/kanna-mod.apk
A="adb -s 127.0.0.1:5555"
$A install -r ../kanna-mod.apk
$A shell appops set com.pastel.aipet.kanna SYSTEM_ALERT_WINDOW allow
$A shell am start -n com.pastel.aipet.kanna/com.local.mcpcontroller.MainActivity >/dev/null
echo STEP9_OK
