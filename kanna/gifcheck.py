# 상태별 GIF 검사: 움직임 크기(프레임 사이 차이) 출력 + 프레임을 펼친 격자 그림 저장
#   python gifcheck.py <GIF 폴더(hebi/ kanna/ 포함)> [출력 폴더, 기본 /sdcard/Pictures]
# 격자 한 장 = 상태 6개 x 프레임 4장(0, 1/4, 1/2, 3/4 지점). 폰 화면 한 장에 들어가는 크기.
import glob, os, sys
from PIL import Image, ImageChops, ImageStat

SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else '/sdcard/Pictures'
COLS, ROWS, CELL = 4, 6, 260


def frames(path):
    im = Image.open(path)
    out = []
    for i in range(getattr(im, 'n_frames', 1)):
        im.seek(i)
        out.append(im.convert('RGBA'))
    return out


for char in sorted(d for d in os.listdir(SRC) if os.path.isdir(os.path.join(SRC, d))):
    files = sorted(glob.glob(os.path.join(SRC, char, '*.gif')))
    for part in range(0, len(files), ROWS):
        chunk = files[part:part + ROWS]
        grid = Image.new('RGB', (COLS * CELL, len(chunk) * CELL), (190, 190, 190))
        for r, f in enumerate(chunk):
            fr = frames(f)
            n = len(fr)
            d = [sum(ImageStat.Stat(ImageChops.difference(fr[i], fr[(i + 1) % n])).mean) / 4 for i in range(n)]
            print('%s/%s %d장 움직임 평균 %.2f 최대 %.2f' % (char, os.path.basename(f), n, sum(d) / n, max(d)))
            for c in range(COLS):
                t = fr[c * n // COLS].copy()
                t.thumbnail((CELL, CELL))
                cell = Image.new('RGBA', (CELL, CELL), (190, 190, 190, 255))
                cell.alpha_composite(t, ((CELL - t.width) // 2, (CELL - t.height) // 2))
                grid.paste(cell.convert('RGB'), (c * CELL, r * CELL))
        p = os.path.join(OUT, 'petcheck_%s_%d.png' % (char, part // ROWS + 1))
        grid.save(p)
        print('->', p)
print('GIFCHECK_OK')
