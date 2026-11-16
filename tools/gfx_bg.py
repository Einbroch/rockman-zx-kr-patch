"""sub.bin 과 같은 형식의 BG 그림 파일(g_over·g_back·miss·repair·sec_disk …) 글자 한글화.
아카이브: u32 개수, u32 오프셋[개수+1] — 오프셋[i] 비트31 = i번 항목 LZ10 압축. 0번 = 그림 레코드(20바이트),
그림 형식 0x44xxxx = 8bpp 타일 그대로, 0x46xxxx = 8bpp 타일 LZ10 압축. 1번 = 맵 표(u32 오프셋, 맵마다 8바이트 머리:
?, u16 폭, u16 높이). 저장 형태(압축 여부)는 원본을 따른다."""
import struct, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import gfx_sub, gfx_zx, bglabel, lz10


def pad4(b):
    """원본의 블록·항목 오프셋은 모두 4 정렬이다. LZ 재압축 길이를 4의 배수로 채운다(비정렬이면 타이틀 전체가 깨짐, 실측)."""
    return bytes(b) + bytes(-len(b) % 4)


class Arc:
    def __init__(self, raw):
        ents, offs = gfx_sub.arc_parse(raw)
        self.raw_ents = [bytes(e) for e in ents]
        self.flags = [o & 0x80000000 for o in offs]
        self.comp = [bool(offs[i] & 0x80000000) for i in range(len(ents))]
        self.ents = [lz10.decompress(e)[0] if self.comp[i] and e else bytes(e) for i, e in enumerate(ents)]
        self._recs = {}; self._maps = {}

    # 그림 레코드
    def recs(self, ei=0):
        if ei not in self._recs:
            e = self.ents[ei]; R = gfx_sub.recs_parse(e, struct.unpack_from('<I', e, 0)[0] // 20)
            for r in R:
                r['lz'] = r['f'][2] & 0xff0000 == 0x460000 and r['tiles'][:1] == b'\x10'
                r['px'] = bytearray(lz10.decompress(r['tiles'])[0] if r['lz'] else r['tiles'])
                r['n0'] = len(r['px']) // 64
            self._recs[ei] = (R, e)
        return self._recs[ei][0]

    def tiles(self, rk, ei=0):
        return self.recs(ei)[rk]['px']

    # 맵
    def map(self, m, ei=1):
        if (ei, m) not in self._maps:
            e = self.ents[ei]; mo = struct.unpack_from('<I', e, 4 * m)[0]
            w, h = struct.unpack_from('<HH', e, mo + 4)
            assert w == 32, ('폭 32 맵만', m, w)   # bglabel 은 32칸 행 기준
            self._maps[(ei, m)] = (mo, bytearray(e[mo + 8:mo + 8 + 2 * w * h]), h)
        return self._maps[(ei, m)][1]

    def build(self):
        for ei, (R, e) in self._recs.items():
            for r in R:
                if r['lz']:
                    if bytes(r['px']) != lz10.decompress(r['tiles'])[0]: r['tiles'] = lz10.compress(bytes(r['px']))
                else: r['tiles'] = bytes(r['px'])
            self.ents[ei] = gfx_sub.recs_build(R, e)
        for (ei, m), (mo, md, h) in self._maps.items():
            e = bytearray(self.ents[ei]); e[mo + 8:mo + 8 + len(md)] = md; self.ents[ei] = bytes(e)
        out = []
        for i, e in enumerate(self.ents):
            orig = lz10.decompress(self.raw_ents[i])[0] if self.comp[i] and self.raw_ents[i] else self.raw_ents[i]
            if e == orig: out.append(self.raw_ents[i])          # 안 바뀐 항목은 원본 바이트 그대로
            else: out.append(pad4(lz10.compress(e)) if self.comp[i] and e else pad4(e))
        return gfx_sub.arc_build(out, self.flags)


def region(tiles, md, cx0, cy0, cx1, cy1):
    cells = [(cx, cy) for cy in range(cy0, cy1) for cx in range(cx0, cx1)]
    return cells, bglabel.region_px(tiles, md, cells, cx1 - cx0)


def text_pts(text, font='Galmuri11', gap=1, bold=False):
    w, pts = gfx_zx.text_mask(text, font, gap)
    if bold: pts = pts | {(x + 1, y) for x, y in pts}
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, y0 = min(xs), min(ys)
    pts = {(x - x0, y - y0) for x, y in pts}
    return pts, max(xs) - x0 + 1, max(ys) - y0 + 1


def all_ids(A, skip=(), ei=1):
    """맵 표의 모든 맵(폭 무관)이 쓰는 타일 번호. skip 맵은 제외."""
    e = A.ents[ei]; nm = struct.unpack_from('<I', e, 0)[0] // 4; ids = set()
    for m in range(nm):
        if m in skip: continue
        mo = struct.unpack_from('<I', e, 4 * m)[0]; w, h = struct.unpack_from('<HH', e, mo + 4)
        ids |= {struct.unpack_from('<H', e, mo + 8 + 2 * i)[0] & 0x3ff for i in range(w * h)}
    return ids


def assign(tiles, jobs, maps, keep=()):
    """jobs: [(맵, 칸 목록, 픽셀 P, 가로 칸 수)]. maps: 이 그림판을 쓰는 모든 맵.
    편집 칸만 쓰던 타일은 비워 재사용하고, 같은 그림 타일은 공유, 모자라면 덧붙인다. 반환: 덧붙인 수."""
    from collections import Counter
    use = Counter(bglabel.cell(m, cx, cy) & 0x3ff for m in maps for cy in range(len(m) // 64) for cx in range(32))
    want = []
    for md, cells, P, cols in jobs:
        for k, (cx, cy) in enumerate(cells):
            ox, oy = (k % cols) * 8, (k // cols) * 8
            data = bytes(P[oy + y][ox + x] for y in range(8) for x in range(8))
            v = bglabel.cell(md, cx, cy); use[v & 0x3ff] -= 1
            want.append((md, cx, cy, v, data))
    free = sorted(t for t, n in use.items() if n == 0 and t not in keep)
    have = {}
    for t in range(len(tiles) // 64 - 1, -1, -1):
        if use[t] > 0: have[bytes(tiles[t * 64:t * 64 + 64])] = t
    added = 0
    for md, cx, cy, v, data in want:
        if data in have: t = have[data]
        elif free: t = free.pop(0); tiles[t * 64:t * 64 + 64] = data; have[data] = t
        else:
            t = len(tiles) // 64; tiles += data; have[data] = t; added += 1
        use[t] += 1
        bglabel.set_cell(md, cx, cy, (v & 0xf000) | t)   # 플립은 지운다(펼친 그림을 담으므로), 팔레트 비트는 보존
    return added


def glow(pts, levels):
    """심 픽셀에서의 유클리드 거리로 색을 매긴다. levels: [(최대거리, 색), ...] 가까운 순."""
    R = int(math.ceil(levels[-1][0])); out = {}
    for x, y in pts:
        for dy in range(-R, R + 1):
            for dx in range(-R, R + 1):
                d = math.hypot(dx, dy); q = (x + dx, y + dy)
                if d <= levels[-1][0] and (q not in out or d < out[q]): out[q] = d
    col = {}
    for q, d in out.items():
        for lim, c in levels:
            if d <= lim + 1e-9: col[q] = c; break
    return col


# ---------------------------------------------------------------- 게임 오버(g_over.bin)
GOVER_LINES = [   # (첫 픽셀 행, 원문, 한글)
    (25, 'ゲームオーバー', '게임 오버'),
    (56, 'ミッションをやりなおす', '미션 다시 하기'),
    (88, 'ミッションをやめる', '미션 그만두기'),
    (120, 'セーブしたばしょからやりなおす', '기록한 곳부터 다시 하기'),
    (152, 'ゲームをやめる', '게임 그만두기'),
    (192, 'クエストをやりなおす', '퀘스트 다시 하기'),
    (224, 'クエストをやめる', '퀘스트 그만두기'),
]


def colmap(tiles, a, b, rows):
    """같은 배치의 두 맵(a, b)을 픽셀 위치로 맞대어 색 대응표(다수결)를 만든다."""
    from collections import Counter, defaultdict
    m = defaultdict(Counter)
    for cy0, cy1 in rows:
        _, Pa = region(tiles, a, 0, cy0, 32, cy1); _, Pb = region(tiles, b, 0, cy0, 32, cy1)
        for ra, rb in zip(Pa, Pb):
            for va, vb in zip(ra, rb): m[va][vb] += 1
    out = {}
    for va, c in m.items():
        (vb, n), = c.most_common(1); out[va] = vb
        assert n >= 0.8 * sum(c.values()), ('색 대응이 흐림', hex(va), c)
    return out


def g_over(raw):
    A = Arc(raw); t = A.tiles(0); m0, m1 = A.map(0), A.map(1)
    jobs = []
    cmap = colmap(t, m0, m1, [(7, 9), (11, 13), (15, 17), (19, 21), (24, 26), (28, 30)])
    for top, jp, ko in GOVER_LINES:
        cy = top // 8
        if top == 25:      # 제목: 단색 0x17 + 가장자리 0x16, 13줄 → 갈무리11 굵게
            pts, w, h = text_pts(ko, 'Galmuri11', 2, bold=True)
            col = {p: 0x17 for p in pts}
            for x, y in pts:
                for q in ((x - 1, y), (x, y + 1)):
                    if q not in pts: col.setdefault(q, 0x16)
            cy0, cy1 = 2, 6
        else:              # 메뉴: 심 0x17 에서 0x15·0x13·0x11·0x0E·0x07 로 번지는 빛
            pts, w, h = text_pts(ko, 'Galmuri11', 2)
            col = glow(pts, [(0, 0x17), (1, 0x15), (1.5, 0x13), (2.3, 0x11), (3.2, 0x0e), (4.2, 0x07)])
            cy0, cy1 = cy - 1, cy + 3
        xs = [q[0] for q in col]; ys = [q[1] for q in col]
        bw, bh = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        for md, cm in ((m0, None), (m1, None if top == 25 else cmap)):   # 제목은 두 맵이 같은 색
            cells, P = region(t, md, 0, cy0, 32, cy1)
            ox = 128 - bw // 2 - min(xs); oy = (top - cy0 * 8) + 8 - bh // 2 - min(ys) if top != 25 else (top - cy0 * 8) + 6 - bh // 2 - min(ys)
            for y in range(len(P)):
                for x in range(256): P[y][x] = 0
            for (x, y), c in col.items():
                X, Y = x + ox, y + oy
                assert 0 <= X < 256 and 0 <= Y < len(P), (ko, X, Y)
                P[Y][X] = cm[c] if cm else c
            jobs.append((md, cells, P, 32))
    add = assign(t, jobs, (m0, m1))
    print(f'g_over: 타일 {A.recs()[0]["n0"]} -> {len(t) // 64} (+{add})')
    return A.build()


# ---------------------------------------------------------------- 기록/불러오기 화면(g_back.bin) 아래 버튼 3개
def g_back(raw):
    A = Arc(raw); t = A.tiles(0); m0, m1 = A.map(0), A.map(1); jobs = []
    for k, ko in enumerate(('지우기', '불러오기', '기록')):          # イレース / ロード / セーブ
        cells, P = region(t, m0, k * 8, 24, k * 8 + 8, 26)
        n = 0
        for y in range(2, 13):
            for x in range(7, 57):
                if P[y][x] in (0xff, 0xfe, 0xfd): P[y][x] = 0x01; n += 1
        assert n > 40, (ko, n)
        pts, w, h = text_pts(ko, 'Galmuri9', 1, bold=True)
        assert w <= 46, (ko, w)
        ox = 32 - w // 2; oy = 3 + (9 - h) // 2
        for x, y in pts:
            assert P[y + oy][x + ox] == 0x01, (ko, x, y)
            P[y + oy][x + ox] = 0xff
        jobs.append((m0, cells, P, 8))
    add = assign(t, jobs, (m0, m1))
    print(f'g_back: 타일 +{add}')
    return A.build()


def plain_label(t, md, cx0, cy0, ncx, ncy, text, xr, yr, bg, fg, keep=(), font='Galmuri9', ytop=None):
    """검은 상자 안 흰 글자 라벨: xr·yr 범위에서 bg·keep 이 아닌 픽셀을 bg 로 지우고 굵은 글자를 가운데에.
    반환: (칸 목록, P). 굵게가 안 들어가면 보통 굵기."""
    cells, P = region(t, md, cx0, cy0, cx0 + ncx, cy0 + ncy)
    n = 0
    for y in range(*yr):
        for x in range(*xr):
            if P[y][x] != bg and P[y][x] not in keep: P[y][x] = bg; n += 1
    assert n > 20, (text, n)
    W = xr[1] - xr[0]
    pts, w, h = text_pts(text, font, 1, bold=True)
    if w > W: pts, w, h = text_pts(text, font, 1)
    if w > W: pts, w, h = text_pts(text, font, 0)
    assert w <= W, (text, w, W)
    ox = xr[0] + (W - w) // 2
    oy = ytop if ytop is not None else yr[0] + (yr[1] - yr[0] - h) // 2
    for x, y in pts: P[y + oy][x + ox] = fg
    return cells, P


# ---------------------------------------------------------------- 미션 화면 머리 꼬리표(miss.bin)
def miss(raw):
    A = Arc(raw); t = A.tiles(0); jobs = []
    maps = [A.map(m) for m in (0, 5, 6)]
    for m, ko in ((0, '미션'), (6, '전송에리어')):      # ミッション / 転送エリア (띄어 쓰면 굵게가 안 들어감)
        md = A.map(m)
        jobs.append((md,) + plain_label(t, md, 11, 0, 10, 2, ko, (12, 67), (2, 13), 0x01, 0xff) + (10,))
    add = assign(t, jobs, maps)
    print(f'miss: 타일 +{add}')
    return A.build()


def mask6pts(text, gap=0, bold=False):
    pts, tw = gfx_sub.mask6(text, gap)
    if bold: pts = pts | {(x + 1, y) for x, y in pts}; tw += bold
    return pts, tw


# ---------------------------------------------------------------- 플루브 연구소(repair.bin)
def repair(raw):
    A = Arc(raw); t = A.tiles(0); m0, m1 = A.map(0), A.map(1); jobs = []
    # 1) 머리 꼬리표 フルーブのラボ (미션 화면과 같은 흰 글자 상자)
    jobs.append((m0,) + plain_label(t, m0, 10, 0, 12, 2, '플루브 연구소', (14, 83), (2, 13), 0x01, 0xff) + (12,))
    # 2) 왼쪽 안내 リペアに ひつような / Eクリスタル: 채움 0xC9 + 외곽선 0x04 (그늘 0x39·0xBF 는 생략), 6줄
    cells, P = region(t, m0, 1, 4, 15, 8)
    for y in range(15, 32):
        for x in range(12, 112):
            if P[y][x] != 0x00: P[y][x] = 0x00
    for top, text in ((17, '수리에 필요한'), (25, 'E크리스탈')):
        pts, tw = mask6pts(text, 1, bold=True)
        pts = {(x + 17, y + top) for x, y in pts}
        assert max(p[0] for p in pts) < 111, (text, tw)
        for q in {(x + dx, y + dy) for x, y in pts for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - pts: P[q[1]][q[0]] = 0x04
        for x, y in pts: P[y][x] = 0xc9
    jobs.append((m0, cells, P, 14))
    # 3) 오른쪽 칸 제목 Eクリスタル (작은 글자 0xC3·가장자리 0x53, 바탕 0x00)
    cells, P = region(t, m0, 19, 2, 31, 5)
    ink = [(x, y) for y in range(8, 15) for x in range(20, 82) if P[y][x] in (0xc3, 0x53)]
    cx = (min(p[0] for p in ink) + max(p[0] for p in ink) + 1) / 2
    for x, y in ink: P[y][x] = 0x00
    pts, tw = mask6pts('E크리스탈')
    ox = int(cx - tw / 2 + 0.5)
    for x, y in pts:
        assert P[y + 8][x + ox] == 0x00, ('E크리스탈', x, y)
        P[y + 8][x + ox] = 0xc3
    jobs.append((m0, cells, P, 12))
    add = assign(t, jobs, (m0, m1))
    print(f'repair: 타일 +{add}')
    return A.build()


def outlined(P, pts, ox, oy, fill, line):
    pts = {(x + ox, y + oy) for x, y in pts}
    for q in {(x + dx, y + dy) for x, y in pts for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - pts:
        if P[q[1]][q[0]] == 0: P[q[1]][q[0]] = line
    for x, y in pts: P[y][x] = fill


# ---------------------------------------------------------------- 시크릿 디스크(sec_disk.bin) 탭: 맵 1~4 = 보스/에너미A/에너미B/기타 쪽
SD_TABS = ['보스', '에너미A', '에너미B', '기타']
SD_ABBR = ['보', 'A', 'B', '기']          # 비활성 탭의 한 글자(원본 ボ·A·B·他)


def sec_disk(raw):
    A = Arc(raw); t = A.tiles(1); maps = [A.map(m) for m in range(0, 6)]; jobs = []
    LIVE = (0xcf, 0x5f, 0x90, 0x32)
    for k in range(4):
        md = A.map(k + 1)
        cells, P = region(t, md, 0, 4, 16, 6)          # 픽셀 행 32..47
        XT = 112                                        # 탭 줄 끝(오른쪽은 No. 상자, 같은 흰색을 쓴다)
        live = [(x, y) for y in range(16) for x in range(XT) if P[y][x] in LIVE]
        dim = [(x, y) for y in range(16) for x in range(XT) if P[y][x] == 0x18]
        assert live, k
        lx0 = min(p[0] for p in live); lx1 = max(p[0] for p in live) + 1
        ys = [p[1] for p in live]; cyy = (min(ys) + max(ys) + 1) / 2
        groups = []
        for x in sorted({p[0] for p in dim}):
            if groups and x - groups[-1][1] <= 3: groups[-1][1] = x
            else: groups.append([x, x])
        others = [i for i in range(4) if i != k]
        assert len(groups) == 3, (k, groups)
        boxes = [(lx0 - 1, lx1, LIVE)] + [(a, b, (0x18,)) for (a, b), i in zip(groups, others) if SD_ABBR[i] not in 'AB']
        for a, b, cs in boxes:          # 글자 상자 안만 지운다(외곽선 0x01 은 탭 구분선에도 쓰인다). A·B 는 라틴이라 그대로
            for y in range(min(ys) - 1, max(ys) + 2):
                for x in range(a, b + 1):
                    if P[y][x] in cs + (0x01,): P[y][x] = 0
        for gap, bold in ((1, True), (1, False), (0, False)):
            pts, w, h = text_pts(SD_TABS[k], 'Galmuri9', gap, bold=bold)
            if w <= lx1 - lx0 + 2: break
        assert w <= lx1 - lx0 + 2, (SD_TABS[k], w, lx1 - lx0)
        outlined(P, pts, (lx0 + lx1) // 2 - w // 2, int(cyy - h / 2 + 0.5), 0xcf, 0x01)
        for (gx0, gx1), i in zip(groups, others):
            if SD_ABBR[i] in 'AB': continue
            pts, w, h = text_pts(SD_ABBR[i], 'Galmuri9', 0)
            outlined(P, pts, (gx0 + gx1 + 1) // 2 - w // 2, int(cyy - h / 2 + 0.5), 0x18, 0x01)
        jobs.append((md, cells, P, 16))
    add = assign(t, jobs, [A.map(m) for m in range(1, 6)])
    print(f'sec_disk: 타일 +{add}')
    return A.build()


def strip_label(t, first, n, text):
    """연속 타일 first..first+n-1 이 가로 한 줄 글자(8줄)일 때 제자리로 다시 그린다. 바탕=최빈색, 글자=두 번째 색."""
    from collections import Counter
    W = n * 8
    P = [[t[(first + x // 8) * 64 + y * 8 + x % 8] for x in range(W)] for y in range(8)]
    c = Counter(v for r in P for v in r).most_common()
    bg, fg = c[0][0], c[1][0]
    pts, w, h = text_pts(text, 'Galmuri7', 1)
    assert w <= W and h <= 8, (text, w, h)
    ox = (W - w) // 2; oy = (8 - h) // 2
    for y in range(8):
        for x in range(W): P[y][x] = bg
    for x, y in pts: P[y + oy][x + ox] = fg
    for x in range(W):
        for y in range(8): t[(first + x // 8) * 64 + y * 8 + x % 8] = P[y][x]


# ---------------------------------------------------------------- 스테이지 표지(그림2 의 연속 타일, 제자리)
def h01(raw):
    A = Arc(raw); strip_label(A.recs(1)[2]['px'], 921, 6, '최단 기록'); return A.build()   # ベストタイム


def i04(raw):
    A = Arc(raw); strip_label(A.recs(1)[2]['px'], 841, 5, '최고 점수'); return A.build()   # ハイスコア


# ---------------------------------------------------------------- 퍼즐 미니게임(puzzle.bin) 맵0 오른쪽 라벨
PUZ = [(48, 55, '최고 점수'), (64, 71, '점수'), (83, 92, '체인'), (100, 108, '스매시'), (171, 180, '에너지')]
#       ハイスコア            スコア          チェイン         スマッシュ          エネルギー


def puzzle(raw):
    A = Arc(raw); t = A.tiles(0); md = A.map(0)
    from collections import Counter
    cells, P = region(t, md, 16, 0, 26, 24)          # x 128..207
    for a, b, ko in PUZ:
        c = Counter(P[y][x] for y in range(a, b + 1) for x in range(14, 60))
        if c[0x04] < c[0x6a] + c[0x65]: INK, shadow = (0xcc, 0xc6, 0x9a, 0x8a), 0x8a      # 밝은 띠(무늬 바탕)
        else: INK, shadow = (0xcc, 0xc6, 0x9a, 0x6a, 0x17), 0x6a                # 어두운 띠(0x04)
        mask = {(x, y) for y in range(a - 1, b + 3) for x in range(10, 66) if P[y][x] in INK}
        x0 = min(p[0] for p in mask if P[p[1]][p[0]] == 0xcc)
        gfx_sub.inpaint(P, mask)
        for gap, bold in ((1, True), (1, False), (0, False)):
            pts, w, h = text_pts(ko, 'Galmuri9', gap, bold=bold)
            if x0 + w <= 63: break
        assert x0 + w <= 63, (ko, w)
        oy = (a + b + 1) // 2 - h // 2
        for x, y in pts:
            q = (x + x0 + 1, y + oy + 1)
            if (x + 1, y + 1) not in pts: P[q[1]][q[0]] = shadow
        for x, y in pts: P[y + oy][x + x0] = 0xcc
    add = assign(t, [(md, cells, P, 10)], [md], keep=all_ids(A, skip=(0,)))
    print(f'puzzle: 타일 +{add}')
    return A.build()


# ---------------------------------------------------------------- 버스터 에디트(elf.bin 항목4 그림0 4bpp + 항목5 맵 8·10·11)
# 라벨: 바탕 3, 글자 D(가장자리 C·9), 외곽선 6. のこり_マス 의 숫자 칸(x 56..63)은 게임이 숫자를 찍는다.
ELF_BOX = [  # (x0, x1, y0, y1, 글자, 정렬)  y 는 글자(외곽선 포함) 행 범위
    (21, 55, 27, 39, '남은', 'r'), (64, 86, 27, 39, '칸', 'l'),            # のこり / マス
    (18, 52, 121, 133, '왼팔', 'c'), (54, 86, 121, 133, '오른팔', 'c'),     # アームL / アームR
    (17, 79, 160, 173, '편집', 'c'), (95, 165, 160, 173, '기본', 'c'), (181, 245, 160, 173, '종료', 'c'),  # エディット / ノーマル / しゅうりょう
]


def elf(raw):
    A = Arc(raw); r = A.recs(4)[0]; t4 = r['px']
    t = bytearray(len(t4) * 2)                       # 4bpp → 8bpp 로 펼쳐 편집
    for i, b in enumerate(t4): t[2 * i] = b & 15; t[2 * i + 1] = b >> 4
    m8, m11 = A.map(8, 5), A.map(11, 5)
    orig8, orig11 = bytes(m8), bytes(m11)
    cells, P = region(t, m8, 0, 0, 32, 23)
    for x0, x1, y0, y1, text, al in ELF_BOX:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if P[y][x] in (0xd, 0xc, 0x9, 0x6): P[y][x] = 0x3
        W = x1 - x0 + 1 - 2
        for gap in (1, 0):
            pts, w, h = text_pts(text, 'Galmuri9', gap, bold=True)
            if w <= W: break
        assert w <= W, (text, w, W)
        ox = {'l': x0 + 1, 'r': x1 - w, 'c': x0 + (x1 - x0 + 1 - w) // 2}[al]
        oy = y0 + (y1 - y0 + 1 - h) // 2
        q = {(x + ox, y + oy) for x, y in pts}
        for a, b in {(x + dx, y + dy) for x, y in q for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - q:
            assert x0 - 1 <= a <= x1 + 1 and P[b][a] == 0x3, (text, a, b, P[b][a])
            P[b][a] = 0x6
        for a, b in q: P[b][a] = 0xd
    rows = sorted({y // 8 for b in ELF_BOX for y in range(b[2], b[3] + 1)})
    sel = [(cx, cy) for cy in rows for cx in range(32)]
    Psel = [P[cy * 8 + y] for cy in rows for y in range(8)]
    keep = all_ids(A, skip=(6, 7, 8, 10, 11), ei=5)   # 6·7 은 다른 그림판(1·2)의 타일 나열
    jobs = [(m8, sel, Psel, 32)]
    for mo_ in (A.map(10, 5), m11):                  # 같은 칸(같은 타일)을 쓰는 맵 10·11 도 같은 그림으로
        orig = bytes(mo_)
        same = [(cx, cy) for cx, cy in sel if orig[2 * (cy * 32 + cx):2 * (cy * 32 + cx) + 2] == orig8[2 * (cy * 32 + cx):2 * (cy * 32 + cx) + 2]]
        if not same: continue
        Q = [[0] * 8 * len(same) for _ in range(8)]
        for k, (cx, cy) in enumerate(same):
            for y in range(8):
                for x in range(8): Q[y][k * 8 + x] = P[cy * 8 + y][cx * 8 + x]
        jobs.append((mo_, same, Q, len(same)))
    add = assign(t, jobs, [m8, A.map(10, 5), m11], keep=keep)
    assert max(t[i] for i in range(len(t))) < 16
    r['px'] = bytearray(t[2 * i] | t[2 * i + 1] << 4 for i in range(len(t) // 2))
    print(f"elf: 그림0 타일 {len(t4) // 32} -> {len(t) // 64} (+{add})")
    return A.build()


JOBS = {'g_over.bin': g_over, 'g_back.bin': g_back, 'miss.bin': miss, 'repair.bin': repair, 'sec_disk.bin': sec_disk, 'h01.bin': h01, 'i04.bin': i04, 'puzzle.bin': puzzle, 'elf.bin': elf}


def apply(rom):
    for name, fn in JOBS.items():
        fid = rom.filenames.idOf(name)
        rom.files[fid] = fn(rom.files[fid])
