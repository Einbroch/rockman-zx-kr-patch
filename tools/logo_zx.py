"""타이틀 로고 「ロックマンゼクス」 → 「록맨 젝스」. title.bin 그림1(LZ 8bpp, 971타일) + 맵4(BG1, 확장 팔레트 4·5번).
팔레트는 파일에 없어 일본판 타이틀 캡처와 맞대어 뽑은 (슬롯, 색번호) → RGB 표(data/zx_logo_pal.json)를 쓴다.
띠(79~103행, x 29~211)를 비운다: 왼쪽 판은 판 검정, 오른쪽(문장 위)은 위·아래 행 중 가까운 쪽 색.
글자는 직사각형 획으로 설계해 행별 원본 채움색(왼쪽 파랑·오른쪽 주황)으로 칠하고 흰 테 1px + 진한 외곽선 1px.
마지막에 칸마다 그 칸의 팔레트 슬롯에서 가장 가까운 색번호로 바꾼다."""
import os, sys, json, struct
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bglabel, gfx_bg

Y0, Y1 = 79, 103          # 띠(포함)
X0, X1 = 29, 223
SPLIT = 137               # 왼쪽(ロックマン, 판) / 오른쪽(ゼクス, 문장)
H = 23                    # 글자 심 높이: 80..102 (외곽선 79·103)
GY = 80


def rect(g, x0, y0, x1, y1):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1): g.add((x, y))


def line(g, xa, ya, xb, yb, w):
    """(xa,ya)→(xb,yb) 기울어진 획, 행마다 가로 w px."""
    for y in range(ya, yb + 1):
        x = xa + (xb - xa) * (y - ya) / max(1, yb - ya)
        rect(g, int(round(x - w / 2)), y, int(round(x - w / 2)) + w - 1, y)


# 글자 설계(23줄). 획 사이 틈은 1~2px — 진한 외곽선이 틈을 그어 구분한다.
def rok(W):
    g = set(); a, b = 4, W - 5
    rect(g, a, 0, b, 1); rect(g, b - 3, 0, b, 5); rect(g, a, 4, b, 5)          # ㄹ
    rect(g, a, 4, a + 3, 9); rect(g, a, 8, b, 9)
    rect(g, W // 2 - 2, 10, W // 2 + 1, 12); rect(g, 0, 13, W - 1, 15)          # ㅗ (기둥은 ㄹ 아래에 붙는다)
    rect(g, a, 18, b, 19); rect(g, b - 4, 18, b, 22)                             # ㄱ
    return g


def maen(W):
    g = set()
    rect(g, 0, 0, 18, 2); rect(g, 0, 0, 3, 12); rect(g, 15, 0, 18, 12); rect(g, 0, 10, 18, 12)   # ㅁ
    rect(g, 23, 0, 26, 14); rect(g, 27, 6, W - 7, 7); rect(g, W - 6, 0, W - 3, 14)              # ㅐ
    rect(g, 3, 16, 6, 22); rect(g, 3, 20, W - 3, 22)                                             # ㄴ
    return g


def jek(W):
    g = set()
    rect(g, 0, 0, 18, 2)                                       # ㅈ
    line(g, 9, 3, 2, 14, 4); line(g, 10, 3, 17, 14, 4)
    rect(g, 20, 6, 23, 7); rect(g, 23, 0, 26, 15); rect(g, W - 4, 0, W - 1, 15)   # ㅔ
    rect(g, 3, 18, W - 1, 19); rect(g, W - 4, 18, W - 1, 22)                    # ㄱ
    return g


def seu(W):
    g = set()
    line(g, W // 2, 0, 4, 13, 5); line(g, W // 2, 0, W - 5, 13, 5)            # ㅅ
    rect(g, 0, 17, W - 1, 20)                                                   # ㅡ
    return g


REC1_MAPS = (2, 3, 4, 6, 19)   # 9·10 은 그림0 맵(번호가 우연히 겹칠 뿐)
GLYPHS = [(rok, 33, 43), (maen, 83, 43), (jek, 141, 38), (seu, 184, 38)]


def dil(s):
    return {(x + dx, y + dy) for x, y in s for dx in (-1, 0, 1) for dy in (-1, 0, 1)}


def apply_title(raw, pal):
    """raw: title.bin 원본, pal: {(슬롯,번호): (r,g,b)} → 새 title.bin"""
    pal = {k: tuple(v) for k, v in pal.items()}
    A = gfx_bg.Arc(raw); t = A.tiles(1); md = A.map(4)
    e1 = A.ents[1]; nm = struct.unpack_from('<I', e1, 0)[0] // 4
    cells = [(cx, cy) for cy in range((Y0 - 2) // 8, (Y1 + 2) // 8 + 1) for cx in range(X0 // 8, X1 // 8 + 1)]
    cols = X1 // 8 - X0 // 8 + 1
    P = bglabel.region_px(t, md, cells, cols)
    ox, oy = (X0 // 8) * 8, ((Y0 - 2) // 8) * 8
    slot = {(cx, cy): bglabel.cell(md, cx, cy) >> 12 for cx, cy in cells}
    rgb = lambda x, y: pal.get('%d,%d' % (slot[(x // 8, y // 8)], P[y - oy][x - ox]))
    def lum(c): return 0 if c is None else 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    from collections import Counter
    # 채움색: 원본 글자에서 행별 최빈 (왼쪽 = 파랑 계열, 오른쪽 = 주황·노랑 계열)
    def fill_row(xa, xb, y, test):
        c = Counter(rgb(x, y) for x in range(xa, xb) if rgb(x, y) and test(rgb(x, y)))
        return c.most_common(1)[0][0] if c else None
    blue = lambda c: c[2] > c[0] + 40 and c[2] > 120
    warm = lambda c: c[0] > 200 and c[2] < 120
    LF = {y: fill_row(X0, SPLIT, y, blue) for y in range(GY, GY + H)}
    RF = {y: fill_row(SPLIT, X1, y, warm) for y in range(GY, GY + H)}
    for d in (LF, RF):                      # 빈 행은 이웃 행으로
        for y in range(GY, GY + H):
            if d[y] is None: d[y] = next(d[yy] for k in range(1, H) for yy in (y - k, y + k) if d.get(yy))
    white = Counter(rgb(x, y) for y in range(Y0, Y1 + 1) for x in range(X0, X1) if rgb(x, y) and lum(rgb(x, y)) > 225).most_common(1)[0][0]
    dark = Counter(rgb(x, y) for y in range(Y0, Y1 + 1) for x in range(X0, SPLIT) if rgb(x, y) and lum(rgb(x, y)) < 40).most_common(1)[0][0]
    # 1) 띠 비우기
    T = {}
    for y in range(Y0, Y1 + 1):
        for x in range(X0, X1 + 1):
            if x < SPLIT: T[(x, y)] = dark
            else:                       # 문장 위: 위·아래로 가장 가까운 주황·빨강 픽셀
                best = None
                for d in range(1, 16):
                    for yy in (Y0 - d, Y1 + d):
                        c = rgb(x, yy) if (Y0 - 2) // 8 * 8 <= yy < ((Y1 + 2) // 8 + 1) * 8 else None
                        if c and c[0] > 180 and c[0] > c[2] + 60: best = c; break
                    if best: break
                T[(x, y)] = best or dark
    # 2) 글자
    for fn, gx, W in GLYPHS:
        core = {(x + gx, y + GY) for x, y in fn(W)}
        closed = core
        for _ in range(2): closed = dil(closed)
        for _ in range(2): closed = {p for p in closed if all(q in closed for q in dil({p}))}   # 닫힘: 획 사이 틈을 덮은 윤곽
        for p in dil(dil(closed)) - dil(closed) | (dil(closed) - closed):   # 바깥 흰 테(틈 안은 제외), 띠 안만
            if p in T: T[p] = white
        for p in dil(core) - core: T[p] = dark
        for x, y in core:
            T[(x, y)] = white if ((x, y - 1) not in core or (x - 1, y) not in core) else (LF if x < SPLIT else RF)[y]
    for (x, y) in T: assert Y0 <= y <= Y1 and X0 <= x <= X1, ('띠 밖', x, y)
    # 3) 칸 슬롯 팔레트로 양자화
    bypal = {}
    for k, c in pal.items():
        s, i = map(int, k.split(',')); bypal.setdefault(s, []).append((i, c))
    def near(s, c):
        return min(bypal[s], key=lambda ic: sum((a - b) ** 2 for a, b in zip(ic[1], c)))[0]
    for (x, y), c in T.items():
        P[y - oy][x - ox] = near(slot[(x // 8, y // 8)], tuple(c))
    # 그림1 을 쓰는 맵: 4(BG1)·19(BG3)는 일본판 VRAM 대조로 확정, 2·3·6 은 타일 경계 연속성으로 추정
    maps = [A.map(m) for m in REC1_MAPS]
    add = gfx_bg.assign(t, [(md, cells, P, cols)], maps)
    assert len(t) // 64 <= 1024, ('타일 번호 10비트 초과', len(t) // 64)
    print(f'logo: 타일 {A.recs()[1]["n0"]} -> {len(t) // 64} (+{add})')
    return A.build()


def _w32(A, m):
    e = A.ents[1]; mo = struct.unpack_from('<I', e, 4 * m)[0]
    return struct.unpack_from('<H', e, mo + 4)[0] == 32


HD = True   # 사용자 제작 HD 로고(art/logo_hd/zx.png)로 통째로 (logo_hd_nds)


def apply(rom):
    pal = json.load(open(os.path.join(HERE, '..', 'data', 'zx_logo_pal.json')))
    fid = rom.filenames.idOf('title.bin')
    if HD:
        import logo_hd_nds
        rom.files[fid] = logo_hd_nds.apply_title(rom.files[fid], pal, 'zx', 4, REC1_MAPS[:2] + REC1_MAPS[3:], True, True)
    else:
        rom.files[fid] = apply_title(rom.files[fid], pal)
    p258 = json.load(open(os.path.join(HERE, '..', 'data', 'zx_logo258_pal.json')))
    fo = rom.filenames.idOf('obj_fnt.bin'); fd = rom.filenames.idOf('obj_dat.bin')
    rom.files[fo] = apply_obj258(rom.files[fo], rom.files[fd], p258)
    rom.files[fo] = apply_obj145(rom.files[fo], rom.files[fd])


# ---------------------------------------------------------------- 오프닝 하늘 장면의 작은 로고(obj_fnt 258, 8bpp 오브젝트 4개)
# 팔레트는 일본판 캡처(오프닝 600프레임)와 맞대어 뽑은 색번호 → RGB(data/zx_logo258_pal.json, 일치율 100%).
# 글자 띠: 프레임 좌표 행 -3..4, x -39..31 (왼쪽 ロックマン 파랑 ~-1, 오른쪽 ゼクス 주황).
def _obj_cells(e):
    import objcell
    h = struct.unpack_from('<5I', e, 0)
    return h


def apply_obj258(buf, dat, pal):
    import objcell, gfx_zx
    pal = {int(k): tuple(v) for k, v in pal.items()}
    n = struct.unpack_from('<I', buf, 0)[0]
    eo = struct.unpack_from('<I', buf, 4 + 4 * 258)[0] & 0x7fffffff
    e = bytearray(objcell.entry(buf, 258)); h = struct.unpack_from('<5I', e, 0)
    T = memoryview(e)[h[0]:h[0] + (h[1] & 0xffff)]
    fr = objcell.frames(objcell.entry(dat, 258))[0]
    loc = {}                                  # 프레임 좌표 → 타일 바이트 위치
    for u, a, x, y in fr:
        w, hh = objcell.SIZES[(a >> 6) & 3][(a >> 4) & 3]
        for ty in range(hh // 8):
            for tx in range(w // 8):
                o = u * 128 + (ty * (w // 8) + tx) * 64
                for yy in range(8):
                    for xx in range(8): loc[(x + tx * 8 + xx, y + ty * 8 + yy)] = o + yy * 8 + xx
    get = lambda p: pal.get(T[loc[p]]) if p in loc and T[loc[p]] else None
    lum = lambda c: 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    YA, YB, XA, XB, SP = -3, 4, -39, 31, 0
    from collections import Counter
    def rowfill(xa, xb, y, test):
        c = Counter(get((x, y)) for x in range(xa, xb) if get((x, y)) and test(get((x, y))))
        return c.most_common(1)[0][0] if c else None
    blue = lambda c: c[2] > c[0] + 40 and c[2] > 120
    warm = lambda c: c[0] > 200 and c[2] < 120
    dark = Counter(get((x, y)) for y in range(YA, YB + 1) for x in range(XA, SP) if get((x, y)) and lum(get((x, y))) < 40).most_common(1)[0][0]
    white = Counter(get((x, y)) for y in range(YA - 3, YB + 3) for x in range(XA, XB) if get((x, y)) and lum(get((x, y))) > 225).most_common(1)[0][0]
    TT = {}
    for y in range(YA, YB + 1):
        for x in range(XA, XB + 1):
            if x < SP: TT[(x, y)] = dark
            else:
                best = None
                for d in range(1, 14):
                    for yy in (YA - d, YB + d):
                        c = get((x, yy))
                        if c and warm(c): best = c; break
                    if best: break
                TT[(x, y)] = best or dark
    # 글자: 갈무리7 을 가로 2배, 7줄(-2..4)
    G = gfx_zx.kfont12.glyphs('Galmuri7')
    def syl(ch):
        dw, w, hh, xo, yo, rows, bits = G[ord(ch)]
        pts = set()
        for r, v in enumerate(rows):
            for c in range(w):
                if v >> (bits - 1 - c) & 1: pts |= {(2 * c, r), (2 * c + 1, r)}
        return pts, 2 * w
    LFr = {y: rowfill(XA, SP, y, lambda c: lum(c) > 150 and c[2] >= c[0]) for y in range(-2, 5)}   # 작은 크기라 밝은 하늘·흰색으로(남색 판 대비)
    RFr = {y: rowfill(SP, XB, y, warm) for y in range(-2, 5)}
    for d in (LFr, RFr):
        for y in d:
            if d[y] is None: d[y] = next(d[yy] for k in range(1, 7) for yy in (y - k, y + k) if d.get(yy))
    x = -37
    for word, gap_after in (('록맨', 6), ('젝스', 0)):
        for ch in word:
            pts, w = syl(ch)
            core = {(px + x, py - 2) for px, py in pts}
            for p in {(a + dx, b + dy) for a, b in core for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - core:
                if p in TT: TT[p] = dark
            for a, b in core:
                assert (a, b) in TT, ('작은 로고 띠 밖', ch, a, b)
                TT[(a, b)] = (LFr if a < SP else RFr)[b]      # 1줄 가로획이 흰 테에 다 덮여 채움만
            x += w + 1
        x += gap_after
        if word == '록맨': x = max(x, SP + 1)
    assert x <= XB + 2, ('작은 로고 폭 초과', x)
    byrgb = {}
    for i, c in pal.items(): byrgb.setdefault(c, i)
    def near(c): return min(pal, key=lambda i: sum((p - q) ** 2 for p, q in zip(pal[i], c)) if i else 1e9)
    for p, c in TT.items():
        assert p in loc, ('오브젝트 밖', p)
        T[loc[p]] = byrgb.get(c) or near(c)
    out = bytearray(buf); out[eo:eo + len(e)] = e
    return bytes(out)


# ---------------------------------------------------------------- 큰 글자 스프라이트 「ロ·ッ·ク·マ·ン」(obj_fnt 145, 4bpp 32x32 × 5프레임)
# 프레임 1(ッ)에 「록」, 3(マ)에 「맨」을 그리고 나머지는 비운다. 색은 원본 「ロ」(프레임 0)의 행별 채움색,
# 외곽선 1, 위·왼쪽 모서리 하이라이트 0xF. 기울기는 원본처럼 아래로 갈수록 왼쪽(행 4개마다 1px).
def apply_obj145(buf, dat):
    import objcell, gfx_zx
    from collections import Counter
    eo = struct.unpack_from('<I', buf, 4 + 4 * 145)[0] & 0x7fffffff
    e = bytearray(objcell.entry(buf, 145)); h = struct.unpack_from('<5I', e, 0)
    T = memoryview(e)[h[0]:h[0] + (h[1] & 0xffff)]
    fr = objcell.frames(objcell.entry(dat, 145))
    ref = objcell.obj_pixels(bytes(T), fr[0][0][0], 32, 32)
    fill = {}
    for y in range(32):
        c = Counter(v for v in ref[y] if v not in (0, 1, 0xf, 0xe, 0xd))
        fill[y] = c.most_common(1)[0][0] if c else None
    ys = [y for y in fill if fill[y]]
    for y in range(32):
        if fill[y] is None: fill[y] = fill[min(ys, key=lambda q: abs(q - y))]
    for k, f in enumerate(fr):
        (u, a, x, y), = f
        for yy in range(32):
            for xx in range(32): gfx_zx.put_obj(T, u, 32, xx, yy, 0)
        glyph = {1: rok, 3: maen}.get(k)
        if not glyph: continue
        core = set()
        for gx, gy in glyph(40):                      # 로고 설계(폭 40)를 가로 0.62배
            Y = gy + 8; X = int(gx * 0.62) + 2 + (30 - Y) // 4
            core.add((X, Y))
        for p in {(a2 + dx, b2 + dy) for a2, b2 in core for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - core:
            assert 0 <= p[0] < 32 and 0 <= p[1] < 32, ('145 칸 밖', k, p)
            gfx_zx.put_obj(T, u, 32, p[0], p[1], 1)
        for X, Y in core:
            v = 0xf if (X, Y - 1) not in core or (X - 1, Y) not in core else fill[Y]
            gfx_zx.put_obj(T, u, 32, X, Y, v)
    out = bytearray(buf); out[eo:eo + len(e)] = e
    return bytes(out)
