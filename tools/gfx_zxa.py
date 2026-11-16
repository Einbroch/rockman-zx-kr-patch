"""록맨 ZX 어드벤트 그림 글자(4bpp BG 라벨) 한글화. build_zxa.py 에서 apply(rom) 으로 부른다.

어드벤트의 언어별 그림 파일(이름 끝 _jp)은 ZX 와 달리 4bpp 다.
- 타일 묶음(fnt): [타일 오프셋, 타일 크기|…, 형식, 팔레트 오프셋, 팔레트 크기|…] 머리(objcell.fnt 와 같음).
- 맵 묶음: u32 오프셋 표, 맵마다 8바이트 머리(?, u16 폭, u16 높이) + u16 칸(타일 10비트, H/V 플립, 팔레트 4비트).
  맵의 타일 번호는 VRAM 기준점(BASE)부터 센다 — 묶음 안 타일 0 = BASE.
라벨 칸을 펼친 그림으로 다시 그린 뒤, 같은 그림 타일은 공유하고 이 라벨만 쓰던 타일 자리를 재사용한다.
타일 수를 늘리지 않는다(VRAM 배치가 고정이라 덧붙이면 남의 타일을 덮는다) — 모자라면 빌드 실패."""
import os, sys, struct
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import gfx_sub, gfx_zx, lz10


# ---------- 4bpp 타일·맵 ----------
def tile_px(tiles, t):
    o = t * 32
    return [[(tiles[o + y * 4 + x // 2] >> ((x & 1) * 4)) & 15 for x in range(8)] for y in range(8)]


def tile_bytes(P, ox, oy):
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            out[y * 4 + x // 2] |= (P[oy + y][ox + x] & 15) << ((x & 1) * 4)
    return bytes(out)


class Map:
    def __init__(self, buf, off):
        self.buf, self.off = buf, off                       # buf: bytearray(맵 묶음), off: 머리 위치
        self.w, self.h = struct.unpack_from('<HH', buf, off + 4)

    def cell(self, cx, cy): return struct.unpack_from('<H', self.buf, self.off + 8 + 2 * (cy * self.w + cx))[0]
    def set(self, cx, cy, v): struct.pack_into('<H', self.buf, self.off + 8 + 2 * (cy * self.w + cx), v)
    def cells(self): return [(cx, cy) for cy in range(self.h) for cx in range(self.w)]


def maps_of(buf):
    n = struct.unpack_from('<I', buf, 0)[0] // 4
    return [Map(buf, struct.unpack_from('<I', buf, 4 * m)[0]) for m in range(n)]


def render(tiles, base, mp):
    P = [[0] * (mp.w * 8) for _ in range(mp.h * 8)]
    for cx, cy in mp.cells():
        v = mp.cell(cx, cy); t = (v & 0x3ff) - base; hf, vf = v >> 10 & 1, v >> 11 & 1
        if not 0 <= t < len(tiles) // 32: continue
        T = tile_px(tiles, t)
        for y in range(8):
            for x in range(8):
                P[cy * 8 + y][cx * 8 + x] = T[7 - y if vf else y][7 - x if hf else x]
    return P


def assign(tiles, base, jobs, allmaps):
    """jobs: [(맵, 펼친 그림 P)] — 맵 전체 칸을 P 로 바꾼다. allmaps: 이 타일 묶음을 쓰는 모든 맵."""
    nt = len(tiles) // 32
    use = Counter((m.cell(cx, cy) & 0x3ff) - base for m in allmaps for cx, cy in m.cells())
    want = []
    for mp, P in jobs:
        for cx, cy in mp.cells():
            v = mp.cell(cx, cy); use[(v & 0x3ff) - base] -= 1
            want.append((mp, cx, cy, v, tile_bytes(P, cx * 8, cy * 8)))
    free = sorted(t for t in range(nt) if use[t] <= 0)
    have = {}
    for t in range(nt - 1, -1, -1):
        if use[t] > 0: have[bytes(tiles[t * 32:t * 32 + 32])] = t
    for mp, cx, cy, v, data in want:
        if data in have: t = have[data]
        else:
            assert free, '빈 타일 자리가 모자람(타일을 덧붙이면 VRAM 의 다른 그림을 덮는다)'
            t = free.pop(0); tiles[t * 32:t * 32 + 32] = data; have[data] = t
        use[t] += 1
        mp.set(cx, cy, (v & 0xf000) | (t + base))          # 펼친 그림이라 플립은 지우고 팔레트는 보존
    return len(free)


# ---------- 글자 ----------
def styled(text, fill, outline, font='Galmuri11', gap=1):
    """갈무리 1px 획 + 8방향 1px 외곽선. 반환 {(x,y): 색}, 폭, 높이 (외곽선 포함, 0부터)."""
    w, pts = gfx_zx.text_mask(text, font, gap)
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, y0 = min(xs) - 1, min(ys) - 1
    pts = {(x - x0, y - y0) for x, y in pts}
    out = {}
    for x, y in pts:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                out.setdefault((x + dx, y + dy), outline)
    for p in pts: out[p] = fill
    return out, max(xs) - x0 + 2, max(ys) - y0 + 2


def big(text, fill, shadow, font='Galmuri9', scale=2, gap=1):
    """갈무리 획을 scale 배로 키우고 오른쪽 아래 1px 그림자."""
    w, pts = gfx_zx.text_mask(text, font, gap)
    x0 = min(p[0] for p in pts); y0 = min(p[1] for p in pts)
    S = {((x - x0) * scale + i, (y - y0) * scale + j) for x, y in pts for i in range(scale) for j in range(scale)}
    out = {(x + 1, y + 1): shadow for x, y in S}
    for q in S: out[q] = fill
    return out, max(q[0] for q in out) + 1, max(q[1] for q in out) + 1


def relabel(P, text, band, bg, fill, outline, inks, xr=None, font='Galmuri11', gap=1, maker=None, left=False):
    """P(펼친 그림)의 band=(y0,y1) 행에서 inks 색 픽셀을 bg 로 지우고 text 를 가운데에 그린다.
    xr=(x0,x1): 글자가 들어갈 가로 범위(기본: 원본 잉크 범위를 포함하는 그림 폭 전체 - 2px)."""
    W = len(P[0]); y0, y1 = band
    ink = [x for y in range(y0, y1) for x in range(W) if P[y][x] in inks]
    for y in range(y0, y1):
        rb = bg if bg is not None else Counter(v for v in P[y] if v not in inks).most_common(1)[0][0]
        for x in range(W):
            if P[y][x] in inks: P[y][x] = rb
    px, tw, th = (maker or styled)(text, fill, outline, font, gap)
    if xr is None: xr = (2, W - 2)
    assert tw <= xr[1] - xr[0], f'{text}: 폭 {tw} > {xr[1] - xr[0]}'
    assert th <= y1 - y0, f'{text}: 높이 {th} > {y1 - y0}'
    cx = (min(ink) + max(ink) + 1) // 2 if ink else (xr[0] + xr[1]) // 2
    dx = xr[0] if left else max(xr[0], min(xr[1] - tw, cx - tw // 2)); dy = y0 + (y1 - y0 - th) // 2
    for (x, y), v in px.items(): P[dy + y][dx + x] = v
    return P


# ---------- 파일별 ----------
LS_TXT = {0: '트랜스포메이션', 1: '디테일 맵', 2: '러프 맵', 3: '버스터 에디트', 4: '에너미 애널라이징',
          5: '아이템 서칭', 6: '레이더 스코프', 18: '전송 에리어'}


def ls_txt(rom):
    """아래 화면 머리 라벨(14x2 칸): 바탕 1, 글자 속 7, 외곽선 3, 안쪽 음영 5·6. 글자 띠는 2~14행."""
    fid = rom.filenames.idOf('ls_txt_fnt_jp.bin'); dfid = rom.filenames.idOf('ls_txt_dat_jp.bin')
    Fe, Fo = gfx_sub.arc_parse(rom.files[fid]); De, Do = gfx_sub.arc_parse(rom.files[dfid])
    assert not any(o & 0x80000000 for o in Fo + Do), '압축 항목(예상 밖)'
    F = bytearray(Fe[0]); D = bytearray(De[0])
    h = struct.unpack_from('<5I', F, 0); tiles = memoryview(F)[h[0]:h[0] + (h[1] & 0xffff)]
    BASE = 0x1a6
    allm = maps_of(D)
    jobs = []
    for m, text in LS_TXT.items():
        mp = allm[m]; P = render(tiles, BASE, mp)
        relabel(P, text, (2, 15), 1, 7, 3, {3, 5, 6, 7})
        jobs.append((mp, P))
    assign(tiles, BASE, jobs, allm)
    rom.files[fid] = gfx_sub.arc_build([bytes(F)], [o & 0x80000000 for o in Fo])
    rom.files[dfid] = gfx_sub.arc_build([bytes(D)] + [bytes(e) for e in De[1:]], [o & 0x80000000 for o in Do])


def sub_oth(rom):
    """게임 오버 메뉴(sub_oth_jp): 맵4 제목(굵은 글자 a·그림자 7·가장자리 8/9), 맵5~7 메뉴(속 5·외곽선 1·음영 2/3).
    그림 레코드 형식(gfx_bg.Arc): 그림0 = 4bpp 타일, 맵 묶음 = 항목1, 기준점 0x1a6."""
    import gfx_bg
    fid = rom.filenames.idOf('sub_oth_jp.bin'); E, O = gfx_sub.arc_parse(rom.files[fid])
    assert not any(o & 0x80000000 for o in O)
    E = [bytearray(e) for e in E]
    R = gfx_sub.recs_parse(bytes(E[0]), 1)[0]; assert R['f'][2] >> 16 & 0xff == 0x20
    tiles = memoryview(E[0])[R['tpos']:R['tpos'] + len(R['tiles'])]
    BASE = 0x1a6; allm = maps_of(E[1]); jobs = []
    mp = allm[4]; P = render(tiles, BASE, mp)
    relabel(P, '게임 오버', (0, 22), 0, 0xa, 7, set(range(1, 16)), maker=lambda t, f, o, fo, g: big(t, f, o))
    jobs.append((mp, P))
    for m, text in ((5, '컨티뉴'), (6, '기록한 곳부터 다시 하기'), (7, '타이틀로')):
        mp = allm[m]; P = render(tiles, BASE, mp)
        relabel(P, text, (0, 16), 0, 5, 1, set(range(1, 16)), font='Galmuri9')
        jobs.append((mp, P))
    # 데이터 화면 제목 띠(14x2): 1행 바탕 7, 2~14행 바탕 6, 글자 속 5·외곽선 1·음영 2/3
    for m, text in ((0, '데이터 기록'), (1, '데이터 불러오기'), (2, '데이터 지우기'), (3, '어드바이스'), (8, '데이터베이스')):
        mp = allm[m]; P = render(tiles, BASE, mp)
        for x in range(len(P[1])):
            if P[1][x] in (1, 2, 3, 5): P[1][x] = 7
        lf = text.startswith('데이터')         # 「데이터」 타일을 맵끼리 공유하도록 같은 x 에서 시작
        relabel(P, text, (2, 15), 6, 5, 1, {1, 2, 3, 5}, xr=(8, 110) if lf else None, left=lf)
        jobs.append((mp, P))
    assign(tiles, BASE, jobs, allm)
    rom.files[fid] = gfx_sub.arc_build([bytes(e) for e in E], [o & 0x80000000 for o in O])


MG_TXT = {0: '미니게임', 1: '퀴즈 어드벤트', 2: '에너지 컨버터 A', 3: '서바이벌 로드', 4: '클리어!', 5: '에너미 셀렉트',
          6: '록맨 a', 8: '베스트 타임', 9: '타임', 10: '플레이어1', 11: '플레이어2', 12: '체인', 13: '맥스 체인',
          14: '스코어', 15: '빅토리', 16: '클리어 타임', 17: '토털 대미지', 29: '서바이벌 로드 룰', 32: '싱글 매치'}


def mg_txt(rom):
    """미니게임 라벨(mg_txt_jp, 두 항목 모두 LZ 압축): 글자 속 9, 외곽선 5, 음영 6·7. 바탕은 행마다 다름(a/b/e/0).
    맵 7 「あと　もん」은 가운데에 숫자가 들어가는 두 조각 → 「남은」·「문제」를 각 조각 자리에."""
    import gfx_bg
    fid = rom.filenames.idOf('mg_txt_jp.bin'); A = gfx_bg.Arc(rom.files[fid])
    F = bytearray(A.ents[0]); D = bytearray(A.ents[1])
    h = struct.unpack_from('<5I', F, 0); tiles = memoryview(F)[h[0]:h[0] + (h[1] & 0xffff)]
    BASE = 0x26e; allm = maps_of(D); jobs = []
    INK = {5, 6, 7, 9}
    for m, text in MG_TXT.items():
        mp = allm[m]; P = render(tiles, BASE, mp)
        if m in (3, 29):        # 「서바이벌 로드」를 두 맵에서 같은 x 에 두어 타일을 공유(안 하면 6칸 모자람)
            relabel(P, text, (1, 15), None, 9, 5, INK, xr=(8, 110), font='Galmuri11', left=True)
        elif mp.w >= 14: relabel(P, text, (1, 15), None, 9, 5, INK, font='Galmuri11')
        else:
            W = mp.w * 8; f = 'Galmuri9' if gfx_zx.text_mask(text, 'Galmuri9', 1)[0] + 2 <= W else 'Galmuri7'
            relabel(P, text, (1, 15), None, 9, 5, INK, xr=(0, W), font=f)
        jobs.append((mp, P))
    mp = allm[7]; P = render(tiles, BASE, mp)
    relabel(P, '남은', (1, 15), None, 9, 5, INK, xr=(0, 28), font='Galmuri9')
    sub = [row[52:80] for row in P]
    relabel(sub, '문제', (1, 15), None, 9, 5, INK, xr=(0, 28), font='Galmuri9')
    for y in range(len(P)): P[y][52:80] = sub[y]
    jobs.append((mp, P))
    assign(tiles, BASE, jobs, allm)
    A.ents[0] = bytes(F); A.ents[1] = bytes(D)
    rom.files[fid] = A.build()


def apply(rom):
    ls_txt(rom)
    sub_oth(rom)
    mg_txt(rom)
