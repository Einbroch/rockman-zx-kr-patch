"""BG(8bpp 타일 + 32x32 맵) 라벨 편집. 칸 목록(표시 순서) -> 픽셀 배열, 다시 타일로.
공유 타일(같은 맵의 다른 칸이 씀)은 덮지 않고 새 타일을 덧붙여 맵을 고친다."""
import struct
def cell(md, cx, cy): return struct.unpack_from('<H', md, 2 * (cy * 32 + cx))[0]
def set_cell(md, cx, cy, v): struct.pack_into('<H', md, 2 * (cy * 32 + cx), v)
def tile_px(tiles, v):
    t = v & 0x3ff; hf = v >> 10 & 1; vf = v >> 11 & 1
    return [[tiles[t * 64 + (7 - y if vf else y) * 8 + (7 - x if hf else x)] for x in range(8)] for y in range(8)]
def region_px(tiles, md, cells, cols):
    """cells: [(cx,cy)] 행 우선, cols = 가로 칸 수 -> 2차원 픽셀"""
    rows = len(cells) // cols
    P = [[0] * (cols * 8) for _ in range(rows * 8)]
    for k, (cx, cy) in enumerate(cells):
        px = tile_px(tiles, cell(md, cx, cy)); ox, oy = (k % cols) * 8, (k // cols) * 8
        for y in range(8):
            for x in range(8): P[oy + y][ox + x] = px[y][x]
    return P
def write_region(tiles, md, cells, cols, P, protect=(), others=()):
    """P 를 칸들에 쓴다. tiles: bytearray(늘어날 수 있음). others: 같은 타일 묶음을 쓰는 다른 맵들(공유 판정에 포함).
    반환: 새로 붙인 타일 수"""
    from collections import Counter
    use = Counter(cell(m, cx, cy) & 0x3ff for m in (md,) + tuple(others) for cy in range(32) for cx in range(32))
    mine = Counter(cell(md, cx, cy) & 0x3ff for cx, cy in cells)
    added = 0
    have = {bytes(tiles[i * 64:i * 64 + 64]): i for i in range(len(tiles) // 64 - 1, -1, -1)}
    for k, (cx, cy) in enumerate(cells):
        ox, oy = (k % cols) * 8, (k // cols) * 8
        data = bytes(P[oy + y][ox + x] for y in range(8) for x in range(8))
        v = cell(md, cx, cy); t = v & 0x3ff
        if tile_px(tiles, v) == [list(data[y*8:y*8+8]) for y in range(8)]:
            continue
        if data in have:                                        # 같은 그림의 타일 재사용(플립 없이)
            set_cell(md, cx, cy, (v & 0xf000) | have[data]); use[have[data]] += 1; continue
        if use[t] == mine[t] == 1 and t not in protect:          # 이 칸만 쓰는 타일: 제자리
            tiles[t * 64:t * 64 + 64] = data; set_cell(md, cx, cy, (v & 0xf000) | t); have[data] = t
        else:                                                   # 공유: 새 타일
            nt = len(tiles) // 64; tiles += data; added += 1; have[data] = nt
            set_cell(md, cx, cy, (v & 0xf000) | nt)
    return added
