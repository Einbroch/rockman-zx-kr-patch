"""sub.bin(서브 화면 배경) 라벨 한글화. 0번 항목 = 그림 레코드 32개(20바이트: 타일 상대오프셋, 크기, 형식,
팔레트 상대오프셋, 팔레트 크기 — 오프셋은 각 필드 위치 기준), 1번 항목 = 32x32 맵 11개(+8 헤더).
맵 0 은 그림 0 의 타일을 쓴다(머리 구역: 플레이 타임·E크리스탈, 모델 이름 조각 모음 24~27행)."""
import struct, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bglabel, gfx_zx

MAX_ADD = 32          # 그림 0 타일 추가 상한(VRAM 여유 추정: 32KB 경계)

def arc_parse(b):
    n = struct.unpack_from('<I', b, 0)[0]
    offs = [struct.unpack_from('<I', b, 4 + 4 * i)[0] for i in range(n + 1)]
    return [b[offs[i] & 0x7fffffff:offs[i + 1] & 0x7fffffff] for i in range(n)], offs
def arc_build(ents, flags):
    n = len(ents); out = bytearray(4 + 4 * (n + 1)); pos = len(out)
    struct.pack_into('<I', out, 0, n)
    for i, e in enumerate(ents):
        struct.pack_into('<I', out, 4 + 4 * i, pos | flags[i]); out += e; pos += len(e)
    struct.pack_into('<I', out, 4 + 4 * n, pos | flags[n]); return bytes(out)

def recs_parse(e0, n=32):
    R = []
    for k in range(n):
        f = list(struct.unpack_from('<5I', e0, 20 * k))
        ts = 20 * k + f[0]; ps = 20 * k + 12 + f[3]
        R.append(dict(f=f, tiles=e0[ts:ts + (f[1] & 0xffff)], tpos=ts, pal=e0[ps:ps + (f[4] & 0xffff)], ppos=ps))
    return R
def recs_build(R, e0_orig):
    """데이터 블록을 원래 위치 순서대로 다시 깔고 상대 오프셋·크기를 고친다."""
    blocks = []
    for k, r in enumerate(R):
        blocks.append((r['tpos'], k, 't')); blocks.append((r['ppos'], k, 'p'))
    blocks.sort()
    out = bytearray(e0_orig[:20 * len(R)]); pos = {}
    first = min(b[0] for b in blocks); out += e0_orig[len(out):first]
    seen = set()
    for p, k, kind in blocks:
        key = (p, kind, len(R[k]['tiles' if kind == 't' else 'pal']))
        if key in seen:                       # 같은 위치를 공유하는 빈 블록
            pos[(k, kind)] = pos[[q for q in pos if q[1] == kind and R[q[0]]['tpos' if kind == 't' else 'ppos'] == p][0]]
            continue
        seen.add(key)
        pos[(k, kind)] = len(out); out += R[k]['tiles' if kind == 't' else 'pal']
    for k, r in enumerate(R):
        f = r['f'][:]
        f[0] = pos[(k, 't')] - 20 * k; f[1] = (f[1] & 0xffff0000) | len(r['tiles'])
        f[3] = pos[(k, 'p')] - (20 * k + 12)
        struct.pack_into('<5I', out, 20 * k, *f)
    return bytes(out)

def piece_cells(k):
    out = []
    for row in (0, 1):
        for j in range(6):
            lin = k * 6 + j; out.append((lin % 32, 24 + 2 * (lin // 32) + row))
    return out

def draw(P, text, font, x0, y0, fill, shadow, gap=0, center_w=None, bold=False):
    w, pts = gfx_zx.text_mask(text, font, gap)
    if bold:
        pts = pts | {(x + 1, y) for x, y in pts}
    ys = [p[1] for p in pts]; xs = [p[0] for p in pts]
    tw = max(xs) + 1
    if center_w: x0 = x0 + (center_w - tw) // 2
    dy = y0 - min(ys)
    H = len(P); W = len(P[0])
    for x, y in pts:
        X, Y = x + x0 + 1, y + dy + 1
        if 0 <= X < W and 0 <= Y < H and (x + 1, y + 1) not in pts and shadow is not None: P[Y][X] = shadow
    for x, y in pts:
        X, Y = x + x0, y + dy
        assert 0 <= X < W and 0 <= Y < H, (text, X, Y, W, H)
        P[Y][X] = fill
    return tw

def erase(P, rows, colors, bg):
    for y in rows:
        for x in range(len(P[0])):
            if P[y][x] in colors: P[y][x] = bg

def mask6(text, gap=0):
    """갈무리7 글자를 6줄로: 빈 줄이 있으면 빼고, 없으면 차이가 가장 적은 이웃 두 줄을 OR 로 합친다.
    (예전엔 3번째 줄을 지워 「타」의 ㅏ 가지가 사라져 「티」가 됐다) -> (좌표 집합, 폭)"""
    G = gfx_zx.kfont12.glyphs('Galmuri7'); pts = set(); X = 0
    for ch in text:
        dw, w, h, xo, yo, rows, bits = G[ord(ch)]
        R = [[(v >> (bits - 1 - x)) & 1 for x in range(w)] for v in rows]
        R = [[0] * w] * (7 - len(R)) + R
        drop = next((i for i in range(7) if not any(R[i])), None)
        if drop is not None: R = R[:drop] + R[drop + 1:]
        else:
            i = min(range(6), key=lambda i: (sum(a != b for a, b in zip(R[i], R[i + 1])), abs(i - 2.5)))
            R = R[:i] + [[a | b for a, b in zip(R[i], R[i + 1])]] + R[i + 2:]
        for y in range(6):
            for x in range(w):
                if R[y][x]: pts.add((X + x + xo, y))
        X += dw + gap
    return pts, max(p[0] for p in pts) + 1


def map_get(e1, m):
    mo = struct.unpack_from('<I', e1, 4 * m)[0]; return bytearray(e1[mo + 8:mo + 8 + 2048])
def map_put(e1, m, md):
    mo = struct.unpack_from('<I', e1, 4 * m)[0]; e1[mo + 8:mo + 8 + 2048] = md

MARK = 0x3ff
def localize(md, base):
    """타일 번호를 그림판 기준(−base)으로. base 아래 칸은 표시(0x3ff)로 바꾸고 원래 값을 기억."""
    out = bytearray(md); saved = {}
    for i in range(1024):
        v = struct.unpack_from('<H', md, 2 * i)[0]; t = v & 0x3ff
        if t >= base: struct.pack_into('<H', out, 2 * i, (v & 0xfc00) | (t - base))
        else: saved[i] = v; struct.pack_into('<H', out, 2 * i, (v & 0xfc00) | MARK)
    return out, saved
def delocalize(L, saved, base):
    out = bytearray(L)
    for i in range(1024):
        v = struct.unpack_from('<H', L, 2 * i)[0]
        if i in saved:
            assert v & 0x3ff == MARK, ('그림판 밖 칸을 고침', i)
            struct.pack_into('<H', out, 2 * i, saved[i])
        else: struct.pack_into('<H', out, 2 * i, (v & 0xfc00) | ((v & 0x3ff) + base))
    return out

def tab_specs(left, right, btn=0xfe):
    """(x0, x1, 지울 행, 그릴 위 행, 글자, 글꼴, 굵게, 색). 화살표(◀▶)와 L/R 글자는 둔다. btn: 버튼 글자 색(비활성 회색 0xcd)."""
    return [(9, 54, range(4, 13), 4, left, 'Galmuri9', True, 0xfe),
            (65, 90, range(4, 10), 4, '버튼', 'Galmuri7', False, btn),
            (174, 203, range(4, 10), 4, '버튼', 'Galmuri7', False, btn),
            (202, 248, range(4, 13), 4, right, 'Galmuri9', True, 0xfe)]

def tab_strip(tiles, md, r0, specs, others=()):
    """탭 줄(맵 r0~r0+1행, 흰 막대 0xFF) 글자 상자를 막대색으로 비우고 다시 쓴다."""
    cells = [(cx, cy) for cy in (r0, r0 + 1) for cx in range(32)]
    P = bglabel.region_px(tiles, md, cells, 32)
    for x0, x1, rows, top, text, font, bold, fill in specs:
        for y in rows:
            for x in range(x0, x1):
                P[y][x] = 0xff
        w, pts = gfx_zx.text_mask(text, font, 1 if bold else 0)
        if bold: pts = pts | {(x + 1, y) for x, y in pts}
        tw = max(p[0] for p in pts) + 1; ymin = min(p[1] for p in pts)
        assert tw <= x1 - x0, (text, tw, x1 - x0)
        ox = x0 + (x1 - x0 - tw) // 2
        for x, y in pts:
            X, Y = x + ox, y - ymin + top
            assert P[Y][X] >= 0xf8, (text, X, Y, hex(P[Y][X]))
            P[Y][X] = fill
    bglabel.write_region(tiles, md, cells, 32, P, others=others)

def inpaint(P, mask):
    """mask 좌표를 같은 행의 가장 가까운 비마스크 픽셀로 채운다(없으면 위아래)."""
    H, W = len(P), len(P[0]); src = [r[:] for r in P]
    for (x, y) in mask:
        best = None
        for d in range(1, W):
            for X in (x - d, x + d):
                if 0 <= X < W and (X, y) not in mask: best = src[y][X]; break
            if best is not None: break
        P[y][x] = best

def outlined6(P, text, x0, y0, fill, outline, bold=False):
    """갈무리7 6줄 축소(굵게면 가로 2px 획) + 8방향 1px 외곽선."""
    pts, tw = mask6(text, 1 if bold else 0)
    if bold: pts = pts | {(x + 1, y) for x, y in pts}; tw += 1
    pts = {(x + x0, y + y0) for x, y in pts}
    out = {(x + dx, y + dy) for x, y in pts for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - pts
    for x, y in out: P[y][x] = outline
    for x, y in pts: P[y][x] = fill
    return tw

ITEM_TAGS = [(2, '아이템A', (0xf0, 0xf1, 0xf2)), (8, '아이템B', (0xf3, 0xf4, 0xf5)), (14, '아이템C', (0xf6, 0xf7, 0xf8))]
def item_tags(tiles, md, others=()):
    """아이템 페이지(맵 2) 「アイテムA/B/C」: 흰 글자+검은 외곽선, 배경은 로고가 비치는 무늬라 글자 자리를 옆 픽셀로 메운다."""
    for cy0, text, tones in ITEM_TAGS:
        cells = [(cx, cy) for cy in range(cy0, cy0 + 3) for cx in range(1, 8)]
        P = bglabel.region_px(tiles, md, cells, 7)
        mask = {(x, y) for y in range(8, 16) for x in range(2, 42) if P[y][x] == 0x04 or P[y][x] in tones}
        assert len(mask) > 150, (text, len(mask))
        inpaint(P, mask)
        tw = outlined6(P, text, 4, 9, tones[0], 0x04)   # 굵게는 6줄에서 ㅇ·템이 뭉개진다(실측)
        assert 4 + tw < 42, (text, tw)
        bglabel.write_region(tiles, md, cells, 7, P, others=others)

# 옵션 페이지 표(맵 5·6·7 = 그림 4). 글자 하나가 8x8 칸 하나쯤이고 게임이 24~27행 조각 칸을 표로 복사해 조립한다.
# 같은 타일을 다른 단어가 공유한다(オン의 ン = ウェポン의 ン, オ = オーバードライブ 첫 칸, ウェポン 꼬리 두 벌 등).
# → 칸마다 한 음절, 공유 타일은 모든 쓰임에서 같은 그림이 되도록 배치하고 어긋나면 빌드 실패.
# 단위: (맵, 행, [칸 x...] 또는 [(x,y)...], 음절 목록). 빈 문자열 = 빈 칸. 글자색은 원래 칸에서 잰다(13 밝음, 8 흐림).
SR = lambda *xy: list(xy)
OPT_UNITS = [
    (5, 24, range(0, 4), ['', '', '타', '입']),           # タイプー (밝음). 다음 글자 칸이 「-A」(대시 포함)라 오른쪽에 붙인다
    (5, 24, range(14, 18), ['', '', '타', '입']),         # (흐림)
    (5, 24, range(8, 14), ['', '커', '스', '텀', '', '']),
    (5, 24, range(22, 28), ['', '커', '스', '텀', '', '']),
    (5, 24, range(28, 32), ['', '버', '튼', '']),         # ボタン 밝음
    (5, 25, range(0, 4), ['', '버', '튼', '']),           # ボタン 흐림
    (5, 25, range(20, 30), ['메', '인', '', '웨', '폰', '', '', '', '', '']),
    (5, None, SR((31, 25), (0, 26), (1, 26), (2, 26), (3, 26), (4, 26), (5, 26), (6, 26), (7, 26), (8, 26)),
        ['서', '브', '', '웨', '폰', '', '', '', '', '']),
    (5, 26, range(10, 21), ['메', '인', '', '서', '브', '', '전', '환', '', '', '']),
    (5, 26, range(22, 25), ['', '켬', '']), (5, 26, range(25, 28), ['', '켬', '']),
    (5, 26, range(28, 31), ['', '끔', '']), (5, None, SR((31, 26), (0, 27), (1, 27)), ['', '끔', '']),
    # 정적 표(맵 5): 왼쪽 열
    (5, 10, range(6, 15), ['메', '인', '', '웨', '폰', '', '', '', '']),
    (5, 11, range(6, 15), ['서', '브', '', '웨', '폰', '', '', '', '']),
    (5, 12, range(8, 13), ['점', '프', '', '', '']),
    (5, 13, range(8, 13), ['대', '시', '', '', '']),
    (5, 14, range(8, 13), ['변', '신', '', '', '']),
    (5, 15, range(6, 15), ['', '오', '버', '드', '라', '이', '브', '', '']),
    # 맵 6(공격 모드): Y버튼 - 메인 웨폰 / R+Y버튼 - 서브 웨폰
    (6, 11, range(16, 26), ['메', '인', '', '웨', '폰', '', '', '', '', '']),
    (6, 12, range(16, 26), ['서', '브', '', '웨', '폰', '', '', '', '', '']),
    # 맵 7(액션 모드)
    (7, 7, range(5, 13), ['커', '맨', '드', '', '대', '시', '', '']),
    (7, 11, range(5, 11), ['호', '버', '', '', '', '']),
    (7, 15, range(5, 11), ['수', '영', '', '', '', '']),
]

def option_tables(tiles, mds):
    """mds: {맵 번호: bytearray}. 타일 그림만 제자리로 바꾼다(맵·타일 수 불변)."""
    from collections import Counter
    want = {}
    for m, y, xs, syl in OPT_UNITS:
        cells = [(x, y) for x in xs] if y is not None else list(xs)
        assert len(cells) == len(syl), (m, y, syl)
        c = Counter()
        for cx, cy in cells:
            for row in bglabel.tile_px(tiles, bglabel.cell(mds[m], cx, cy)): c.update(row)
        fg = 13 if c[13] >= c[8] else 8
        assert c[fg] > 10, ('글자색 없음', m, y, syl)
        for (cx, cy), ch in zip(cells, syl):
            v = bglabel.cell(mds[m], cx, cy); t = v & 0x3ff
            assert not v & 0xc00, ('플립 칸', m, cx, cy)
            P = [[0] * 8 for _ in range(8)]
            if ch:
                pts, tw = mask6(ch)
                pts = {(x, y + 1) for x, y in pts}
                for x, yy in {(x + dx, yy + dy) for x, yy in pts for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - pts:
                    if 0 <= x < 8 and 0 <= yy < 8: P[yy][x] = 2
                for x, yy in pts: P[yy][x] = fg
            data = bytes(v for r in P for v in r)
            assert t != 0, ('빈 타일 0 칸에 글자', m, cx, cy, ch)
            if t in want: assert want[t] == data, ('공유 타일 충돌', hex(t), m, cx, cy, ch)
            want[t] = data
    # 위쪽 탭 세 개(맵 2~4행, 글자 픽셀 행 11~17 = 3·4행에 걸침). 고른 탭 글자 13, 나머지 8, 외곽선 2.
    TABS = [(11, 57, '버튼 배치'), (71, 112, '공격 모드'), (131, 186, '액션 모드')]   # 탭2 x112~ 타일(0x3b)은 맵5·6 공유라 잉크 금지
    region = [(x, y) for y in (2, 3, 4) for x in range(24)]
    inside = set()
    for m, sel in ((5, 0), (6, 1), (7, 2)):
        P = bglabel.region_px(tiles, mds[m], region, 24)
        for y in range(10, 19):
            for x in range(9, 190):
                if P[y][x] in (2, 8, 13, 9, 12): P[y][x] = 0
        for k, (x0, x1, text) in enumerate(TABS):
            fg = 13 if k == sel else 8
            w, pts = gfx_zx.text_mask(text, 'Galmuri7', 1)
            # 굵게는 「배」 등이 뭉개진다(실측) → 1px 획
            tw = max(p[0] for p in pts) + 1; ymin = min(p[1] for p in pts)
            assert tw + 2 <= x1 - x0, (text, tw)
            ox = x0 + (x1 - x0 - tw) // 2
            pts = {(x + ox, y - ymin + 11) for x, y in pts}
            assert max(p[1] for p in pts) <= 17, text
            for x, y in {(x + dx, y + dy) for x, y in pts for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - pts:
                assert P[y][x] == 0, ('탭 외곽선이 테두리를 덮음', text, x, y)
                P[y][x] = 2
            for x, y in pts: P[y][x] = fg
        for k, (cx, cy) in enumerate(region):
            v = bglabel.cell(mds[m], cx, cy); t = v & 0x3ff
            ox, oy = (k % 24) * 8, (k // 24) * 8
            data = bytes(P[oy + y][ox + x] for y in range(8) for x in range(8))
            if bglabel.tile_px(tiles, v) == [list(data[y * 8:y * 8 + 8]) for y in range(8)]: continue
            assert not v & 0xc00 and t != 0, ('탭: 플립/빈 타일', m, cx, cy)
            if t in want: assert want[t] == data, ('탭 공유 타일 충돌', hex(t), m, cx, cy)
            want[t] = data; inside.add(t)
    # 탭 밖에서 쓰이는 타일을 바꾸면 안 된다
    for m in (5, 6, 7):
        for cy in range(32):
            for cx in range(32):
                if (cx, cy) in region: continue
                assert bglabel.cell(mds[m], cx, cy) & 0x3ff not in inside, ('탭 타일이 다른 곳에도 쓰임', m, cx, cy)
    for t, data in want.items(): tiles[t * 64:t * 64 + 64] = data
    return len(want)

def main_sub_tags(tiles, md):
    """상태 페이지 BG2(맵 1 = 그림 1) 의 작은 파란 상자 「メイン」「サブ」. 흰 글자(0xF9, 반투명 0x97/0xE3/0xC8)를
    상자 바탕(0x71/0xB1 그러데이션)으로 메우고 6줄 축소 갈무리7 을 같은 중심에 그린다."""
    cells = [(x, y) for y in (11, 12) for x in range(7, 16)]
    P = bglabel.region_px(tiles, md, cells, 9)
    INK = (0xf9, 0x97, 0xe3, 0xc8)
    for x0, x1, text, gap in ((20, 44, '메인', 0), (52, 72, '서브', -1)):   # 서브 상자 안쪽은 14px
        mask = {(x, y) for y in range(6, 12) for x in range(x0, x1) if P[y][x] in INK}
        assert len(mask) > 20, (text, len(mask))
        cx = (min(p[0] for p in mask) + max(p[0] for p in mask) + 1) / 2
        inpaint(P, mask)
        pts, tw = mask6(text, gap)
        ox = int(cx - tw / 2 + 0.5)
        edge = 0
        for x, y in pts:
            X, Y = x + ox, y + 6
            assert x0 <= X < x1 and P[Y][X] in (0x71, 0xb1, 0x20, 0x23), (text, X, Y, hex(P[Y][X]))
            edge += P[Y][X] in (0x20, 0x23)
            P[Y][X] = 0xf9
        assert edge <= 1, (text, '상자 테두리를 덮음', edge)   # 서브: 둥근 모서리 1px 허용
    bglabel.write_region(tiles, md, cells, 9, P)

PIECES = ['모델ZX', '모델X', '모델HX', '모델FX', '모델LX', '모델PX', '모델OX', '반', '에일']

def apply(rom):
    fid = rom.filenames.idOf('sub.bin'); b = rom.files[fid]
    ents, offs = arc_parse(b); flags = [o & 0x80000000 for o in offs]
    e0, e1 = ents[0], bytearray(ents[1])
    R = recs_parse(e0); tiles = bytearray(R[0]['tiles']); n0 = len(tiles) // 64
    mo = struct.unpack_from('<I', e1, 0)[0]; md = bytearray(e1[mo + 8:mo + 8 + 2048])
    mo4 = struct.unpack_from('<I', e1, 16)[0]; md4 = bytes(e1[mo4 + 8:mo4 + 8 + 2048])   # 옵션 쪽(그림 0 공유)
    # 1) 플레이 타임 / E크리스탈 (텍스트 행 3~7, 테두리 1~2행까지 빌려 7px)
    # 원본 글자는 3~7행 5px. 아래 칸(맵 4·6행)은 게임이 숫자를 그릴 때 다시 써서 못 쓴다(실측) →
    # 갈무리7 을 6줄로 줄여(빈 줄/같은 줄 하나 제거) 2~7행에. 그림자 색 0x20 은 실제 팔레트에서 밝아 쓰지 않는다.
    for cy, text in ((3, '플레이 타임'), (5, 'E크리스탈')):
        cells = [(cx, cy) for cx in range(20, 31)]
        P = bglabel.region_px(tiles, md, cells, 11)
        erase(P, range(3, 8), (0xfe, 0x20), 0x02)
        pts, tw = mask6(text)
        x0 = 10 + (68 - tw) // 2
        for x, y in pts:
            assert P[y + 2][x + x0] in (0x02, 0x2d), (text, x, y)
            P[y + 2][x + x0] = 0xfe
        bglabel.write_region(tiles, md, cells, 11, P, others=(md4,))
    # 2) 모델 이름 조각 + 기본 칸
    for k, text in enumerate(PIECES):
        cells = piece_cells(k)
        P = bglabel.region_px(tiles, md, cells, 6)
        erase(P, range(2, 16), (0xf8, 0x91, 0x17), 0x02)
        draw(P, text, 'Galmuri11', 1 if text.startswith('모델') else 0, 3, 0xf8, 0x91, 1,
             center_w=None if text.startswith('모델') else 48, bold=True)
        bglabel.write_region(tiles, md, cells, 6, P, others=(md4,))
        if k == 0:
            slot = [(cx, cy) for cy in (3, 4) for cx in range(1, 7)]
            bglabel.write_region(tiles, md, slot, 6, P, others=(md4,))
    # 3) 탭 줄(맵 1~2행): 흰 막대(0xFF) 위 글자(0xFE/0xFD, 그림자 0x20). 화살표·L/R 글자는 둔다.
    tab_strip(tiles, md, 1, tab_specs('미션', '아이템'), others=(md4,))
    # 4) 옵션 페이지 탭(맵 4 = 그림 0, 0~1행)
    md4 = bytearray(md4)
    tab_strip(tiles, md4, 0, tab_specs('아이템', '미션'), others=(md,))
    e1[mo4 + 8:mo4 + 8 + 2048] = md4

    added = len(tiles) // 64 - n0
    assert added <= MAX_ADD, f'sub.bin 그림0 타일 {added}개 추가 > {MAX_ADD}'
    R[0]['tiles'] = bytes(tiles)
    # 5) 아이템 페이지(맵 2)·미션 페이지(맵 8): 그림 2 를 타일 번호 512 부터 올린다
    t2 = bytearray(R[2]['tiles']); n2 = len(t2) // 64
    m2 = map_get(e1, 2); m8 = map_get(e1, 8)
    L2, s2 = localize(m2, 512); L8, s8 = localize(m8, 512)
    tab_strip(t2, L2, 0, tab_specs('상태', '옵션', btn=0xcd), others=(L8,))
    tab_strip(t2, L8, 0, tab_specs('옵션', '상태'), others=(L2,))
    item_tags(t2, L2, others=(L8,))
    map_put(e1, 2, delocalize(L2, s2, 512)); map_put(e1, 8, delocalize(L8, s8, 512))
    add2 = len(t2) // 64 - n2
    assert n2 + add2 <= 512, f'그림2 타일 {n2 + add2} > 512'
    R[2]['tiles'] = bytes(t2)
    # 7) 상태 페이지 메인/서브 꼬리표(맵 1, 그림 1)
    t1 = bytearray(R[1]['tiles']); n1 = len(t1) // 64; m1 = map_get(e1, 1)
    main_sub_tags(t1, m1); map_put(e1, 1, m1)
    add1 = len(t1) // 64 - n1
    assert n1 + add1 <= 512, f'그림1 타일 {n1 + add1} > 512'
    R[1]['tiles'] = bytes(t1)
    # 6) 옵션 페이지 표(맵 5·6·7, 그림 4)
    t4 = bytearray(R[4]['tiles']); n4 = len(t4)
    nopt = option_tables(t4, {m: map_get(e1, m) for m in (5, 6, 7)})
    assert len(t4) == n4
    R[4]['tiles'] = bytes(t4)
    ents[0] = recs_build(R, e0)
    e1[mo + 8:mo + 8 + 2048] = md; ents[1] = bytes(e1)
    rom.files[fid] = arc_build(ents, flags)
    print(f'sub.bin: 그림0 타일 +{added}, 그림2 타일 +{add2}, 옵션 표 타일 {nopt}개, 그림1 타일 +{add1}')
