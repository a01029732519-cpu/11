# GPT가 만든 11종 GIF zip -> 칸나 펫 스프라이트 시트 (chars/hebi/<state>.png/.txt, name.txt=헤비)
import sys, os, io, zipfile, glob
from PIL import Image

ZIP = sys.argv[1] if len(sys.argv) > 1 else glob.glob('/sdcard/Download/*11종*GIF-2.zip')[0]
OUT = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else '~/kanna/chars2/hebi')
SC = 1.25
REFH = 218
STEP = 2
STATES = {'평소': 'idle', '생각중': 'think', '말하는중': 'talk', '탭': 'point', '입력': 'type',
          '화면확인': 'look', '기다림': 'wait', '완료': 'done', '오류': 'error', '질문': 'ask', '잠': 'sleep'}

def fixname(n, info):
    if info.flag_bits & 0x800:
        return n
    raw = n.encode('cp437', 'replace')
    for enc in ('utf-8', 'cp949'):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return n

z = zipfile.ZipFile(ZIP)
files = {}
for info in z.infolist():
    n = fixname(info.filename, info)
    base, ext = os.path.splitext(os.path.basename(n))
    if ext.lower() != '.gif':
        continue
    st = next((STATES[t] for t in base.split('_') if t in STATES), None)
    if st:
        files[st] = info
print('states', sorted(files), len(files))
assert len(files) == 11, 'need 11 gifs'

def frames(info):
    im = Image.open(io.BytesIO(z.read(info)))
    out = []
    for i in range(getattr(im, 'n_frames', 1)):
        im.seek(i)
        out.append((im.convert('RGBA'), int(im.info.get('duration', 50) or 50)))
    return out

data, box = {}, None
for st, info in files.items():
    fr = frames(info)
    pick = []
    for i in range(0, len(fr), STEP):
        grp = fr[i:i + STEP]
        pick.append((grp[0][0], sum(g[1] for g in grp)))
    data[st] = pick
    a0 = fr[0][0]
    ext = a0.getchannel('A').getextrema()
    for im, _ in pick:
        b = im.getchannel('A').getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    print(' ', st, len(fr), '->', len(pick), 'size', a0.size, 'alpha', ext)
bw, bh = box[2] - box[0], box[3] - box[1]
fh = round(REFH * SC)
k = fh / bh
fw = round(bw * k)
refw = round(fw / SC)
os.makedirs(OUT, exist_ok=True)
for st, pick in data.items():
    cnt, cols = len(pick), 8
    rows = (cnt + cols - 1) // cols
    sheet = Image.new('RGBA', (fw * cols, fh * rows), (0, 0, 0, 0))
    for i, (im, _) in enumerate(pick):
        sheet.paste(im.crop(box).resize((fw, fh), Image.LANCZOS), ((i % cols) * fw, (i // cols) * fh))
    sheet.save(os.path.join(OUT, st + '.png'), compress_level=6)
    durs = [max(20, d) for _, d in pick]
    with open(os.path.join(OUT, st + '.txt'), 'w') as f:
        f.write('%d %d %d %d %d %d\n' % (cols, cnt, round(sum(durs) / cnt), refw, REFH, refw // 2))
        f.write(' '.join(str(x) for x in durs) + '\n')
with open(os.path.join(OUT, 'name.txt'), 'w', encoding='utf-8') as f:
    f.write('헤비\n')
print('box', box, 'frame', fw, 'x', fh)
print('CONV2_OK')
