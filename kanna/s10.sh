# 새 GIF 시트(gif2chars.py 출력 ~/kanna/chars_new)를 APK 안에 넣어 그림 교체 + 덮어쓰기 설치(-r, 같은 서명키라 설정 유지)
#   칸나(기본) = assets/hebi  <- chars_new/kanna_normal
#   헤비       = assets/hebi2 <- chars_new/hebi_normal
# 지금 설치본(kanna-mod.apk)은 kanna-mod.before-gif.apk 로 남겨둠 (되돌릴 때 adb install -r 로 다시 설치)
set -e
cd ~/kanna
N=chars_new
for d in hebi_normal kanna_normal; do
  for s in idle think talk point type look wait ask done error sleep; do
    [ -s $N/$d/$s.png ] && [ -s $N/$d/$s.txt ] || { echo "MISSING $d/$s"; exit 1; }
  done
done
[ -s kanna-mod.apk ] && unzip -l kanna-mod.apk | grep -q 'assets/hebi2/idle.png' || { echo NO_BASE; exit 1; }
[ -s kanna-mod.before-gif.apk ] || cp kanna-mod.apk kanna-mod.before-gif.apk
W=build_$(date +%s)
mkdir $W
cd $W
cp ../kanna-mod.apk u.apk
zip -dq u.apk 'META-INF/*.SF' 'META-INF/*.RSA' 'META-INF/*.DSA' 'META-INF/*.EC' 'META-INF/MANIFEST.MF' 'assets/hebi/*' 'assets/hebi2/*' || true
mkdir -p a/assets/hebi a/assets/hebi2
cp ../$N/kanna_normal/*.png ../$N/kanna_normal/*.txt a/assets/hebi/
cp ../$N/hebi_normal/*.png ../$N/hebi_normal/*.txt a/assets/hebi2/
python -c "import os; [os.remove(p) for p in ('a/assets/hebi/name.txt', 'a/assets/hebi2/name.txt') if os.path.exists(p)]"
(cd a && zip -qr0 ../u.apk assets/hebi assets/hebi2)
echo "assets: hebi $(unzip -l u.apk | grep -c 'assets/hebi/') hebi2 $(unzip -l u.apk | grep -c 'assets/hebi2/')"
zipalign -f -p 4 u.apk al.apk
apksigner sign --ks ../key.jks --ks-pass pass:kanna123 --out ../kanna-mod-gif.apk al.apk
apksigner verify ../kanna-mod-gif.apk && ls -la ../kanna-mod-gif.apk
A="adb -s $(cat ~/.adb_last 2>/dev/null || echo 127.0.0.1:5555)"
$A install -r ../kanna-mod-gif.apk
$A shell appops set com.pastel.aipet.kanna SYSTEM_ALERT_WINDOW allow
$A shell am start -n com.pastel.aipet.kanna/com.local.mcpcontroller.MainActivity >/dev/null
echo STEP10_OK
