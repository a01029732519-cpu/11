# GIF 에서 한 장 사이에 가장 크게 바뀌는 곳(튀는 구간) 앞뒤 프레임을 크게 펼쳐 보기
#   python spikecheck.py <GIF 폴더> [출력 PNG, 기본 /sdcard/Pictures/petspike.png] [이름 ...]
# 한 줄 = GIF 하나, 4칸 = 튀기 직전, 튀는 장, 다음 장, 그다음 장
import os, sys
from PIL import Image, ImageChops, ImageStat

SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else '/sdcard/Pictures/petspike.png'
NAMES = sys.argv[3:] or ['01_idle', '08_ask', '09_done', '10_error']
CELL = 250

rows = []
for char in ('hebi', 'kanna'):
    for name in NAMES:
        p = os.path.join(SRC, char, name + '.gif')
        if not os.path.isfile(p):
            continue
        im = Image.open(p)
        fr = []
        for i in range(im.n_frames):
            im.seek(i)
            fr.append(im.convert('RGBA'))
        n = len(fr)
        d = [sum(ImageStat.Stat(ImageChops.difference(fr[i], fr[(i + 1) % n])).mean) / 4 for i in range(n)]
        k = max(range(n), key=lambda i: d[i])
        print('%s/%s 가장 크게 바뀌는 곳: %d -> %d 장 (%.2f)' % (char, name, k, (k + 1) % n, d[k]))
        rows.append([fr[(k + j) % n] for j in (-1, 0, 1, 2)])

grid = Image.new('RGB', (4 * CELL, len(rows) * CELL), (190, 190, 190))
for r, row in enumerate(rows):
    for c, f in enumerate(row):
        t = f.copy()
        t.thumbnail((CELL, CELL))
        cell = Image.new('RGBA', (CELL, CELL), (190, 190, 190, 255))
        cell.alpha_composite(t, ((CELL - t.width) // 2, (CELL - t.height) // 2))
        grid.paste(cell.convert('RGB'), (c * CELL, r * CELL))
grid.save(OUT)
print('->', OUT)
