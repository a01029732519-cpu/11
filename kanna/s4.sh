# 칸나 MCP 수정본 빌드 (폰에서 실행): 원본 APK + 수정된 dex -> 서명된 kanna-mod.apk
set -e
cd ~/kanna
R=https://raw.githubusercontent.com/a01029732519-cpu/11/claude/awesome-carson-wta984/kanna
for p in aapt apksigner python python-pillow zip unzip; do
  dpkg -s $p >/dev/null 2>&1 || pkg install -y $p >/dev/null 2>&1 || echo "pkg fail $p"
done
command -v zipalign >/dev/null || { echo NO_ZIPALIGN; exit 1; }
command -v apksigner >/dev/null || { echo NO_APKSIGNER; exit 1; }
rm -rf m; mkdir m; cd m
for f in classes.dex classes2.dex classes3.dex; do curl -sfLo $f $R/dex/$f; done
sha256sum classes*.dex | cut -c1-16
cp ../kanna-2.2.apk u.apk
zip -dq u.apk 'META-INF/*.SF' 'META-INF/*.RSA' 'META-INF/*.DSA' 'META-INF/*.EC' 'META-INF/MANIFEST.MF' 'classes*.dex' || true
zip -q u.apk classes.dex classes2.dex classes3.dex
zipalign -f -p 4 u.apk a.apk
[ -f ../key.jks ] || keytool -genkeypair -keystore ../key.jks -storepass kanna123 -keypass kanna123 -alias k -keyalg RSA -keysize 2048 -validity 10000 -dname CN=kanna >/dev/null 2>&1
apksigner sign --ks ../key.jks --ks-pass pass:kanna123 --out ../kanna-mod.apk a.apk
apksigner verify ../kanna-mod.apk && ls -la ../kanna-mod.apk
cp ../kanna-mod.apk /sdcard/Download/
echo STEP4_OK
