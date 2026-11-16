"""어드벤트 타이틀 로고 「ロックマンゼクス / アドベント」 → 「록맨 젝스 / 어드벤트」.
title.bin 그림1(8bpp, 408타일, 비압축) + 맵6(BG1, 팔레트 슬롯 0 하나). 색 번호→RGB 는 일본판 타이틀 캡처와
대조해 뽑은 표(data/zxa_logo_pal.json, 일치율 100%)를 쓴다.
- 1줄(초록) 심 72~92행, 2줄(주황) 심 97~117행. 행마다 원본 글자의 채움색(그러데이션)을 그대로 쓴다.
- 글자가 뒤 그림 위에 겹쳐 있어 「비우기」가 불가능 → 원본 글자 덩어리(채움 픽셀을 닫고 넓힌 영역)를
  흰 테 1px + 진한 판으로 덮고, 그 위에 새 글자를 그린다(흰 테 1px · 진한 외곽선 1px · 위/왼쪽 하이라이트).
- 글자 모양: 갈무리11 을 세로 2배(22행)·가로 3배(1줄)/2배+세로획 1px(2줄), 원본처럼 아래로 갈수록 왼쪽으로
  기울인다(4행마다 1px). ZX 로고의 직사각형 설계와 갈무리7 확대는 이 크기에서 ㄹ·ㄱ 이 뭉개져 버렸다.
- 타일: VRAM 에서 그림1 바로 뒤를 다른 데이터가 쓰므로 덧붙이지 않는다. 그림1 을 쓰는 다른 맵(12)의 타일은 보호."""
import os, sys, json, struct
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import gfx_bg, gfx_zx

LOGO_MAP = 6
# 그림1(408타일)을 쓰는 맵: 맵별 타일 번호 범위로 판단. 6·12 만 최대 번호가 0x197(=407). 맵 0~3·4/5·10·13/14·18~20 은
# 다른 그림의 연속 구간이라 제외. 12번(36x9)은 보호한다.
REC1_OTHER_MAPS = (12,)
import logo_zx
rect = logo_zx.rect


# 2줄 글자(21행, 0..20). 획 3~4px, 획 사이 틈 2px 이상(진한 외곽선이 틈을 긋는다).
def eo(W):
    g = set(); r = 17
    rect(g, 2, 2, r - 2, 4); rect(g, 2, 15, r - 2, 17)                 # ㅇ: 위·아래
    rect(g, 0, 4, 3, 15); rect(g, r - 3, 4, r, 15)                     # ㅇ: 좌·우
    rect(g, r + 3, 8, W - 6, 10); rect(g, W - 4, 0, W - 1, 20)         # ㅓ
    return g


def deu(W):
    g = set()
    rect(g, 2, 0, W - 3, 2); rect(g, 2, 0, 5, 11); rect(g, 2, 9, W - 3, 11)   # ㄷ
    rect(g, 0, 16, W - 1, 18)                                                   # ㅡ
    return g


def ben(W):
    g = set()
    rect(g, 0, 0, 3, 11); rect(g, 13, 0, 16, 11); rect(g, 0, 5, 16, 6); rect(g, 0, 9, 16, 11)   # ㅂ
    rect(g, 19, 5, 22, 6); rect(g, 22, 0, 25, 13); rect(g, W - 4, 0, W - 1, 13)                # ㅔ
    rect(g, 3, 16, 6, 20); rect(g, 3, 18, W - 3, 20)                                           # ㄴ
    return g


def teu(W):
    g = set()
    rect(g, 2, 0, W - 3, 2); rect(g, 2, 0, 5, 11); rect(g, 2, 5, W - 6, 6); rect(g, 2, 9, W - 3, 11)   # ㅌ
    rect(g, 0, 16, W - 1, 18)                                                                         # ㅡ
    return g


LINES = [   # (글자, 심 첫 행, 심 끝 행, 원본 채움 판별, 가로 배율, 세로획 보강 px)
    ('록맨 젝스', 71, 92, 'green', 3, 0),
    ('어드벤트', 96, 117, 'orange', 2, 1),
]


def lum(c): return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
def is_green(c): return c[1] > c[0] + 30 and c[1] > c[2] + 20
def is_orange(c): return c[0] > 200 and c[1] > 100 and c[2] < 120 and c[0] > c[1]
def is_white(c): return lum(c) > 225


def nb(p, r=1):
    x, y = p
    return {(x + dx, y + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)}


def dil(s, r=1):
    out = set()
    for p in s: out |= nb(p, r)
    return out


def ero(s, r=1):
    return {p for p in s if nb(p, r) <= s}


def galmuri_set(text, sx, thick):
    """갈무리11(11행)을 가로 sx 배·세로 2배(22행). thick: 세로획을 오른쪽으로 더 굵게."""
    w, pts = gfx_zx.text_mask(text, 'Galmuri11', 1)
    x0 = min(p[0] for p in pts); y0 = min(p[1] for p in pts)
    S = {((x - x0) * sx + i, (y - y0) * 2 + j) for x, y in pts for i in range(sx) for j in (0, 1)}
    for _ in range(thick): S |= {(x + 1, y) for x, y in S}
    return S, max(p[0] for p in S) + 1


def glyph_set(glyphs, gap, space):
    pts = set(); x = 0
    for k, (fn, w) in enumerate(glyphs):
        if space and k == space[0]: x += space[1]
        pts |= {(gx + x, gy) for gx, gy in fn(w)}
        x += w + gap
    return pts, x - gap


def glyph_pts(text, sx, gap):
    """갈무리7 → 가로 sx 배·세로 3배. 반환 (점 집합(0 기준), 폭)."""
    G = gfx_zx.kfont12.glyphs('Galmuri7'); pts = set(); x = 0
    for ch in text:
        if ch == ' ': x += 3 * sx; continue
        dw, w, h, xo, yo, rows, bits = G[ord(ch)]
        top = 7 - yo - h                              # 7줄 칸 안 위치
        for r_, v in enumerate(rows):
            for c in range(w):
                if v >> (bits - 1 - c) & 1:
                    for i in range(sx):
                        for j in range(3): pts.add((x + (c + xo) * sx + i, (top + r_) * 3 + j))
        x += (dw - 1) * sx + gap
    ys = [p[1] for p in pts]; y0 = min(ys)
    return {(a, b - y0) for a, b in pts}, x


def apply_title(raw, pal):
    pal = {int(k): tuple(v) for k, v in pal.items()}
    A = gfx_bg.Arc(raw); t = A.tiles(1); md = A.map(LOGO_MAP)
    W, H = 256, 192
    cell = lambda cx, cy: struct.unpack_from('<H', md, 2 * (cy * 32 + cx))[0]
    assert all(cell(cx, cy) >> 12 == 0 for cy in range(24) for cx in range(32)), '팔레트 슬롯 0 하나라는 가정'
    # 펼친 그림(색 번호)
    P = [[0] * W for _ in range(H)]
    for cy in range(24):
        for cx in range(32):
            v = cell(cx, cy); ti = v & 0x3ff; hf, vf = v >> 10 & 1, v >> 11 & 1
            for y in range(8):
                for x in range(8):
                    P[cy * 8 + y][cx * 8 + x] = t[ti * 64 + (7 - y if vf else y) * 8 + (7 - x if hf else x)]
    rgb = lambda p: pal.get(P[p[1]][p[0]]) if P[p[1]][p[0]] else None
    allp = [(x, y) for y in range(H) for x in range(W)]
    white = Counter(P[y][x] for x, y in allp if P[y][x] and is_white(pal[P[y][x]])).most_common(1)[0][0]
    dark = Counter(P[y][x] for x, y in allp if P[y][x] and lum(pal[P[y][x]]) < 30).most_common(1)[0][0]
    T = {}; letters = []
    for text, y0, y1, kind, sx, thick in LINES:
        test = is_green if kind == 'green' else is_orange
        # 원본 글자 덩어리: 띠 안의 채움(그러데이션 색 + 가운데 흰 띠) 픽셀
        band = [(x, y) for y in range(y0, y1 + 1) for x in range(W)]
        fill = {p for p in band if rgb(p) and test(rgb(p))}
        colc = Counter(p[0] for p in fill)
        xs = [x for x, n in colc.items() if n >= 4]; xa, xb = min(xs), max(xs)   # 글자 열(뒤 그림의 낱 픽셀 제외)
        print(f'로고 {kind}: x {xa}..{xb}')
        # 덮개: 원본 글자 가로 범위 × 심 행의 띠(원본처럼 기울임) — 글자 사이 흰 테 조각까지 깔끔히 덮는다
        yc0 = (y0 + y1) // 2
        blob = {(x + (yc0 - y) // 4, y) for y in range(y0, y1 + 1) for x in range(xa, xb + 1)}
        cover = dil(blob, 1)
        rim = dil(cover, 1) - cover
        # 행별 채움색(원본 최빈값)
        F = {}
        for y in range(y0, y1 + 1):
            c = Counter(P[y][x] for x in range(xa, xb + 1) if P[y][x] and (test(pal[P[y][x]]) or is_white(pal[P[y][x]])))
            F[y] = c.most_common(1)[0][0] if c else None
        for y in F:                                      # 흰 행(원본 가운데 띠)은 가까운 색 행으로 — 획이 흰 테에 묻히지 않게
            if F[y] is not None and is_white(pal[F[y]]): F[y] = None
        for y in F:
            if F[y] is None: F[y] = next(F[q] for k in range(1, 30) for q in (y - k, y + k) if F.get(q) is not None)
        # 새 글자: 원본 덩어리 폭 가운데, 기울임
        pts, tw = galmuri_set(text, sx, thick)
        th = max(p[1] for p in pts) + 1
        assert th <= y1 - y0 + 1, (kind, th)
        oy = y0 + (y1 - y0 + 1 - th) // 2; ox = (xa + xb) // 2 - tw // 2
        yc = (y0 + y1) // 2
        core = {(x + ox + (yc - (y + oy)) // 4, y + oy) for x, y in pts}
        for p in rim: T.setdefault(p, white)
        for p in cover: T[p] = dark
        letters.append((core, F))
    for core, F in letters:                              # 덮개를 다 칠한 뒤 글자(다른 줄 덮개에 가리지 않게)
        for p in dil(core, 2) - dil(core): T[p] = white
    for core, F in letters:
        for p in dil(core) - core: T[p] = dark
        for x, y in core:
            T[(x, y)] = white if (x, y - 1) not in core and (x, y + 2) in core else F[y]   # 3행 이상 획의 위 가장자리만 하이라이트
    lost = 0
    for (x, y), v in T.items():
        assert 0 <= x < W and 0 <= y < H
        if not P[y][x]: lost += 1; continue          # 원래 투명한 자리(타일 0 등)는 건드리지 않는다
        P[y][x] = v
    print(f'로고: 투명 자리라 못 그린 픽셀 {lost}')
    # 타일 제자리 수정: 맵12(같은 로고의 다른 배치)가 띠 타일을 모두 공유하므로 번호는 그대로 두고 내용을 바꾼다.
    # 같은 타일을 쓰는 맵6 칸들이 서로 다른 그림을 요구하면(충돌) 그 칸은 같은 그림의 기존 타일로 돌리거나 실패.
    changed = sorted({(x // 8, y // 8) for x, y in T})
    want = {}
    def cell_px(cx, cy):
        v = cell(cx, cy); hf, vf = v >> 10 & 1, v >> 11 & 1
        return v & 0x3ff, bytes(P[cy * 8 + (7 - y if vf else y)][cx * 8 + (7 - x if hf else x)] for y in range(8) for x in range(8))
    for cy in range(24):
        for cx in range(32):
            ti, data = cell_px(cx, cy)
            want.setdefault(ti, {}).setdefault(data, []).append((cx, cy))
    need = conflict = 0
    for ti, opts in want.items():
        if len(opts) == 1:
            data, = opts
            if bytes(t[ti * 64:ti * 64 + 64]) != data: t[ti * 64:ti * 64 + 64] = data; need += 1
        else:
            conflict += 1
            print('충돌 타일', ti, [v for v in opts.values()][:3])
    assert not conflict, f'타일 공유 충돌 {conflict}건'
    print(f'로고: 바꾼 칸 {len(changed)}, 내용 바꾼 타일 {need}')
    apply_small(A)
    return A.build()


# ---------------------------------------------------------------- 작은 로고(그림0, 맵4 「ロックマンゼクス」 24x4·맵5 「アドベント」 16x4)
# 바탕 투명(0), 글자는 행마다 값이 바뀌는 그러데이션 색 번호 + 가장자리 색. 팔레트(확장 슬롯 4)는 확인 못 해
# 색 번호 공간에서만 작업한다: 행별 채움 = 원본 글자 안쪽 최빈값, 외곽선 = 원본 가장자리 최빈값.
# 그림0 의 0x324 이후 타일은 맵 4·5(+빈 칸 맵 15)만 쓴다(맵 13·19·20 은 번호만 겹치는 다른 그림의 맵).
SMALL = [(4, '록맨 젝스', 3, 0), (5, '어드벤트', 2, 1)]


def apply_small(A):
    t = A.tiles(0); e1 = A.ents[1]
    def mp(m):
        mo = struct.unpack_from('<I', e1, 4 * m)[0]; w, h = struct.unpack_from('<HH', e1, mo + 4)
        return mo, w, h
    jobs = []; use = Counter()
    for m, text, sx, thick in SMALL:
        mo, w, h = mp(m)
        cells = [struct.unpack_from('<H', e1, mo + 8 + 2 * i)[0] for i in range(w * h)]
        assert all(c >> 10 & 3 == 0 for c in cells)
        P = [[t[(cells[(y // 8) * w + x // 8] & 0x3ff) * 64 + (y % 8) * 8 + x % 8] for x in range(w * 8)] for y in range(h * 8)]
        ink = {(x, y) for y in range(h * 8) for x in range(w * 8) if P[y][x]}
        inner = {p for p in ink if nb(p) <= ink}
        edge = Counter(P[y][x] for x, y in ink - inner).most_common(1)[0][0]
        ys = [p[1] for p in ink]; y0, y1 = min(ys), max(ys)
        F = {}
        for y in range(y0, y1 + 1):
            c = Counter(P[y][x] for x, yy in inner if yy == y)
            F[y] = c.most_common(1)[0][0] if c else None
        for y in F:
            if F[y] is None: F[y] = next(F[q] for k in range(1, 40) for q in (y - k, y + k) if F.get(q))
        pts, tw = galmuri_set(text, sx, thick)
        th = max(q[1] for q in pts) + 1
        oy = (y0 + y1 + 1 - th) // 2; ox = (w * 8 - tw) // 2; yc = oy + th // 2
        core = {(x + ox + (yc - (y + oy)) // 4, y + oy) for x, y in pts}
        Q = [[0] * (w * 8) for _ in range(h * 8)]
        for x, y in dil(core) - core: Q[y][x] = edge
        for x, y in core: Q[y][x] = F[min(max(y, y0), y1)]
        assert all(0 <= x < w * 8 and 0 <= y < h * 8 for x, y in dil(core)), ('작은 로고 칸 밖', text)
        jobs.append((mo, w, h, cells, Q))
        for c in cells: use[c & 0x3ff] += 1
    others = set()
    for m in (15,):
        mo, w, h = mp(m); others |= {struct.unpack_from('<H', e1, mo + 8 + 2 * i)[0] & 0x3ff for i in range(w * h)}
    pool = sorted(i for i in use if i not in others)
    blank = next(i for i in sorted(use) if not any(t[i * 64:i * 64 + 64]))
    have = {bytes(64): blank}; e1b = bytearray(e1)
    for mo, w, h, cells, Q in jobs:
        for k in range(w * h):
            cx, cy = k % w, k // w
            data = bytes(Q[cy * 8 + y][cx * 8 + x] for y in range(8) for x in range(8))
            if data not in have:
                i = pool.pop(0)
                while i == blank: i = pool.pop(0)
                t[i * 64:i * 64 + 64] = data; have[data] = i
            struct.pack_into('<H', e1b, mo + 8 + 2 * k, (cells[k] & 0xf000) | have[data])
    A.ents[1] = bytes(e1b)
    print(f'작은 로고: 남은 전용 타일 {len(pool)}')


def apply(rom):
    pal = json.load(open(os.path.join(HERE, '..', 'data', 'zxa_logo_pal.json')))
    fid = rom.filenames.idOf('title.bin')
    rom.files[fid] = apply_title(rom.files[fid], pal)
