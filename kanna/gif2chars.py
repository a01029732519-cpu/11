# 상태별 GIF(ChatGPT 등으로 만든 것) -> 칸나 펫 스프라이트 시트 (chars/<hebi|kanna>_normal/<state>.png/.txt)
#   python gif2chars.py <GIF들이 든 zip 또는 폴더> [출력 폴더, 기본 ~/kanna/chars_new]
# 경로에 hebi/헤비 또는 kanna/칸나, 파일 이름에 상태 이름(idle, think ... 또는 평소, 생각중 ...)이 있으면 됨.
# 프레임은 버리지 않고 쓰되, 앱 메모리 때문에 상태마다 최대 32장까지만 (많으면 고르게 골라냄).
import io, math, os, re, sys, zipfile
from PIL import Image, ImageChops

SRC = sys.argv[1]
OUT = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else '~/kanna/chars_new')
SC = 1.25      # 시트 해상도 배율 (conv.py 와 같게)
REFH = 218     # 원본 칸나 스프라이트 기준 높이
MAXF = 32      # 상태마다 최대 프레임 수
STATES = ['idle', 'think', 'talk', 'point', 'type', 'look', 'wait', 'ask', 'done', 'error', 'sleep']
KO = {'평소': 'idle', '생각중': 'think', '생각 중': 'think', '말하는중': 'talk', '말하는 중': 'talk', '탭': 'point',
      '입력': 'type', '화면확인': 'look', '화면 확인': 'look', '기다림': 'wait', '질문': 'ask', '완료': 'done',
      '오류': 'error', '잠': 'sleep'}
CHARS = {'hebi': ('hebi', '헤비 (일반)'), '헤비': ('hebi', '헤비 (일반)'),
         'kanna': ('kanna', '기존 캐릭터 (일반)'), '칸나': ('kanna', '기존 캐릭터 (일반)')}


def sources():
    """(경로, 바이트 읽는 함수) 목록"""
    if os.path.isdir(SRC):
        for d, _, fs in os.walk(SRC):
            for f in fs:
                p = os.path.join(d, f)
                yield os.path.relpath(p, SRC), (lambda p=p: open(p, 'rb').read())
    else:
        z = zipfile.ZipFile(SRC)
        for info in z.infolist():
            if not info.is_dir():
                yield info.filename, (lambda info=info: z.read(info))


def state_of(name):
    base = os.path.splitext(os.path.basename(name))[0].lower()
    for t in re.split(r'[^a-z가-힣 ]+', base):
        for w in [t.strip()] + t.split():
            if w in STATES:
                return w
            if w in KO:
                return KO[w]
    return None


def char_of(path):
    low = path.lower()
    for k, v in CHARS.items():
        if k in low:
            return v
    return None


def frames(data):
    im = Image.open(io.BytesIO(data))
    n = getattr(im, 'n_frames', 1)
    out = []
    for i in range(n):
        im.seek(i)
        out.append((im.convert('RGBA'), int(im.info.get('duration', 40) or 40)))
    return out


def pick(fr):
    # 마지막 장이 첫 장과 똑같으면 반복할 때 같은 장면이 두 번 나와 멈칫하므로 뺌
    if len(fr) > 2 and ImageChops.difference(fr[0][0], fr[-1][0]).getbbox() is None:
        fr = fr[:-1]
    step = max(1, math.ceil(len(fr) / MAXF))
    out = []
    for i in range(0, len(fr), step):
        grp = fr[i:i + step]
        out.append((grp[0][0], sum(g[1] for g in grp)))
    return out[:MAXF]


jobs = {}   # folder -> (title, {state: data getter})
for path, read in sources():
    if os.path.splitext(path)[1].lower() not in ('.gif', '.webp', '.png', '.apng'):
        continue
    c, st = char_of(path), state_of(path)
    if not c or not st:
        print('skip', path)
        continue
    folder, title = c[0] + '_normal', c[1]
    jobs.setdefault(folder, (title, {}))[1][st] = read

if not jobs:
    sys.exit('GIF 를 못 찾음')

for folder, (title, d) in sorted(jobs.items()):
    miss = [s for s in STATES if s not in d]
    print('==', folder, len(d), 'states', ('빠짐: ' + ' '.join(miss)) if miss else '')
    data, box = {}, None
    for st in STATES:
        if st not in d:
            continue
        fr = frames(d[st]())
        p = pick(fr)
        if len(p) < 2:
            print('  ', st, '움직이지 않는 그림 (프레임 1장)')
        data[st] = p
        for im, _ in p:
            b = im.getchannel('A').getbbox()
            if b:
                box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        print('  ', st, len(fr), '->', len(p))
    bw, bh = box[2] - box[0], box[3] - box[1]
    fh = round(REFH * SC)
    fw = round(bw * fh / bh)
    refw = round(fw / SC)
    od = os.path.join(OUT, folder)
    os.makedirs(od, exist_ok=True)
    for st, p in data.items():
        cnt, cols = len(p), 8
        rows = (cnt + cols - 1) // cols
        sheet = Image.new('RGBA', (fw * cols, fh * rows), (0, 0, 0, 0))
        for i, (im, _) in enumerate(p):
            sheet.paste(im.crop(box).resize((fw, fh), Image.LANCZOS), ((i % cols) * fw, (i // cols) * fh))
        sheet.save(os.path.join(od, st + '.png'), optimize=False, compress_level=6)
        durs = [max(20, x) for _, x in p]
        with open(os.path.join(od, st + '.txt'), 'w') as fo:
            fo.write('%d %d %d %d %d %d\n' % (cols, cnt, round(sum(durs) / cnt), refw, REFH, refw // 2))
            fo.write(' '.join(str(x) for x in durs) + '\n')
    with open(os.path.join(od, 'name.txt'), 'w', encoding='utf-8') as fo:
        fo.write(title + '\n')
    print('  box', box, 'frame', fw, 'x', fh)
print('GIF2CHARS_OK')
