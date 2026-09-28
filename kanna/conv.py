# 캐릭터전체_128프레임_44종.zip -> 칸나 펫 스프라이트 시트(chars/<폴더>/<state>.png/.txt)
import sys, os, io, zipfile
from PIL import Image

ZIP = sys.argv[1] if len(sys.argv) > 1 else '/sdcard/Download/캐릭터전체_128프레임_44종.zip'
OUT = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else '~/kanna/chars')
SC = 1.25      # 시트 해상도 배율 (1.0 = 원본 칸나와 같은 크기)
REFH = 218     # 원본 칸나 스프라이트 기준 높이
STEP = 4       # 128프레임 중 4장마다 1장 -> 32프레임
STATES = {'평소': 'idle', '생각중': 'think', '말하는중': 'talk', '탭': 'point', '입력': 'type',
          '화면확인': 'look', '기다림': 'wait', '완료': 'done', '오류': 'error', '질문': 'ask', '잠': 'sleep'}
STYLES = {'일반': 'normal', '픽셀': 'pixel'}

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
jobs = {}   # (char, style) -> {state: (zipinfo, ext)}
for info in z.infolist():
    n = fixname(info.filename, info)
    if info.is_dir():
        continue
    base, ext = os.path.splitext(n.split('/')[-1])
    ext = ext.lower()
    if ext not in ('.webp', '.gif'):
        continue
    parts = n.split('/')
    char = next((p for p in parts if p in ('기존캐릭터', '헤비')), None)
    if char is None:
        continue
    toks = base.split('_')
    st = next((STATES[t] for t in toks if t in STATES), None)
    sy = next((t for t in toks if t in STYLES), None)
    if not st or not sy:
        print('skip', n); continue
    d = jobs.setdefault((char, sy), {})
    # WebP 우선 (알파 품질이 GIF보다 좋음)
    if st not in d or (d[st][1] == '.gif' and ext == '.webp'):
        d[st] = (info, ext)

def frames(info):
    im = Image.open(io.BytesIO(z.read(info)))
    n = getattr(im, 'n_frames', 1)
    out = []
    for i in range(n):
        im.seek(i)
        out.append((im.convert('RGBA'), int(im.info.get('duration', 40) or 40)))
    return out

for (char, sy), d in sorted(jobs.items()):
    folder = ('kanna' if char == '기존캐릭터' else 'hebi') + '_' + STYLES[sy]
    title = char.replace('기존캐릭터', '기존 캐릭터') + ' (' + sy + ')'
    print('==', folder, title, len(d), 'states')
    data = {}
    box = None
    for st, (info, ext) in d.items():
        fr = frames(info)
        pick = []
        for i in range(0, len(fr), STEP):
            grp = fr[i:i + STEP]
            pick.append((grp[0][0], sum(g[1] for g in grp)))
        pick = pick[:32]
        data[st] = pick
        for im, _ in pick:
            b = im.getchannel('A').getbbox()
            if b:
                box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        print(' ', st, len(fr), '->', len(pick))
    bw, bh = box[2] - box[0], box[3] - box[1]
    fh = round(REFH * SC)
    k = fh / bh
    fw = round(bw * k)
    refw = round(fw / SC)
    rs = Image.NEAREST if sy == '픽셀' else Image.LANCZOS
    od = os.path.join(OUT, folder)
    os.makedirs(od, exist_ok=True)
    for st, pick in data.items():
        cnt = len(pick)
        cols = 8
        rows = (cnt + cols - 1) // cols
        sheet = Image.new('RGBA', (fw * cols, fh * rows), (0, 0, 0, 0))
        for i, (im, _) in enumerate(pick):
            f = im.crop(box).resize((fw, fh), rs)
            sheet.paste(f, ((i % cols) * fw, (i // cols) * fh))
        sheet.save(os.path.join(od, st + '.png'), optimize=False, compress_level=6)
        durs = [max(20, d_) for _, d_ in pick]
        with open(os.path.join(od, st + '.txt'), 'w') as fo:
            fo.write('%d %d %d %d %d %d\n' % (cols, cnt, round(sum(durs) / cnt), refw, REFH, refw // 2))
            fo.write(' '.join(str(x) for x in durs) + '\n')
    with open(os.path.join(od, 'name.txt'), 'w', encoding='utf-8') as fo:
        fo.write(title + '\n')
    print('  box', box, 'frame', fw, 'x', fh)
print('CONV_OK')
