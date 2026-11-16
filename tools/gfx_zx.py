"""록맨 ZX 그림 글자(스프라이트 라벨) 한글화. build_zx.py 에서 apply(rom) 으로 부른다.
라벨 = obj_fnt.bin 항목의 한 프레임. 프레임의 OAM 오브젝트 타일을 지우고, 한글을 원본과 같은 색 번호 체계
(STYLE: 획 가운데/가장자리/외곽선/그림자)로 그려 넣는다. 오브젝트 배치(obj_dat)는 그대로 둔다."""
import struct, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import objcell, kfont12

# 항목 번호: {프레임: 한글}
LABELS = {
    146: {0: '처음부터', 1: '이어서', 2: 'START 버튼을 눌러 주세요', 3: '이지', 4: '노멀', 5: '하드', 6: '반', 7: '에일'},
    77: {4: '라이브메탈', 9: '웨폰', 14: '서브탱크'},
}
# 색 번호: 획 중심, 획 가장자리, 외곽선, 그림자 (원본 픽셀 분석: E/C/4/1)
STYLE = {146: dict(core=0xE, edge=0xC, outline=0x4, shadow=0x1),
         77: dict(font='Galmuri9', gap=-1, thick=False, core=0x5, outline=0x1)}


def text_mask(text, font='Galmuri11', gap=1):
    """갈무리 1px 획 비트맵 -> (w, set(좌표)). 한글 글자 사이 gap px 추가."""
    G = kfont12.glyphs(font); pts = set(); x = 0
    for ch in text:
        dw, w, h, xo, yo, rows, bits = G[ord(ch)]
        for r, v in enumerate(rows):
            y = 13 - yo - h + r
            for c in range(w):
                if v >> (bits - 1 - c) & 1:
                    pts.add((x + c + xo, y))
        x += dw + (gap if '가' <= ch <= '힣' else 0)
    return x, pts


def styled(text, st):
    w, core = text_mask(text, st.get('font', 'Galmuri11'), st.get('gap', 1))
    if not st.get('thick', True):                           # 얇은 글자: 채움 + 한 겹 외곽선
        out = {(x + dx, y + dy) for x, y in core for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - core
        px = {p: st['outline'] for p in out}
        for p in core: px[p] = st['core']
        xs = [p[0] for p in px]; ys = [p[1] for p in px]
        return px, (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    edge = {(x + 1, y) for x, y in core} - core           # 가로 2px 획
    body = core | edge
    out = {(x + dx, y + dy) for x, y in body for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - body
    shadow = {(x + 1, y + 1) for x, y in out} - body - out
    px = {}
    for p in shadow: px[p] = st['shadow']
    for p in out: px[p] = st['outline']
    for p in edge: px[p] = st['edge']
    for p in core: px[p] = st['core']
    xs = [p[0] for p in px]; ys = [p[1] for p in px]
    return px, (min(xs), min(ys), max(xs) + 1, max(ys) + 1)


def put_obj(tiles, unit, w, x, y, v):
    tx, ty = x // 8, y // 8
    o = unit * 128 + (ty * (w // 8) + tx) * 32 + (y % 8) * 4 + (x % 8) // 2
    b = tiles[o]
    tiles[o] = (b & 0xF0) | v if x % 2 == 0 else (b & 0x0F) | (v << 4)


def relabel(fnt_entry, dat_entry, frames, st):
    h = struct.unpack_from('<5I', fnt_entry, 0)
    e = bytearray(fnt_entry)
    tiles = memoryview(e)[h[0]:h[0] + (h[1] & 0xffff)]
    fr = objcell.frames(dat_entry)
    used = {}
    for fi, text in frames.items():
        objs = []
        for t, a, x, y in fr[fi]:
            ow, oh = objcell.SIZES[(a >> 6) & 3][(a >> 4) & 3]
            objs.append((t, ow, oh, x, y))
            for u in range(t, t + ow * oh // 256):
                assert used.setdefault(u, fi) == fi, f'타일 단위 {u} 를 프레임 {used[u]}·{fi} 가 공유'
        # 원본 잉크 범위
        ink = []
        for t, ow, oh, ox, oy in objs:
            p = objcell.obj_pixels(bytes(tiles), t, ow, oh)
            ink += [(ox + xx, oy + yy) for yy in range(oh) for xx in range(ow) if p[yy][xx]]
        ix0 = min(p[0] for p in ink); ix1 = max(p[0] for p in ink) + 1
        iy0 = min(p[1] for p in ink); iy1 = max(p[1] for p in ink) + 1
        bx0 = min(o[3] for o in objs); bx1 = max(o[3] + o[1] for o in objs)
        px, (tx0, ty0, tx1, ty1) = styled(text, st)
        tw, th = tx1 - tx0, ty1 - ty0
        assert tw <= bx1 - bx0, f'{text}: 폭 {tw} > 칸 {bx1 - bx0}'
        cx = (ix0 + ix1) // 2; dx = max(bx0, min(bx1 - tw, cx - tw // 2)) - tx0
        dy = (iy0 + iy1) // 2 - th // 2 - ty0
        for t, ow, oh, ox, oy in objs:                      # 지우기
            for yy in range(oh):
                for xx in range(ow):
                    put_obj(tiles, t, ow, xx, yy, 0)
        for (x, y), v in px.items():
            X, Y = x + dx, y + dy
            for t, ow, oh, ox, oy in objs:
                if ox <= X < ox + ow and oy <= Y < oy + oh:
                    put_obj(tiles, t, ow, X - ox, Y - oy, v); break
            else:
                raise AssertionError(f'{text}: 픽셀 ({X},{Y}) 가 오브젝트 밖')
    return bytes(e)


def apply(rom):
    fid = rom.filenames.idOf('obj_fnt.bin'); F = bytearray(rom.files[fid])
    D = rom.files[rom.filenames.idOf('obj_dat.bin')]
    for i, frames in LABELS.items():
        o0, o1 = [struct.unpack_from('<I', F, 4 + 4 * j)[0] & 0x7fffffff for j in (i, i + 1)]
        new = relabel(bytes(F[o0:o1]), objcell.entry(D, i), frames, STYLE[i])
        assert len(new) == o1 - o0
        F[o0:o1] = new
    rom.files[fid] = bytes(F)
    buster_edit_overlay(rom)


# 버스터 에디트 화면에서 고른 버튼 위에 겹치는 강조 글자(obj_fnt 221). 레코드 타일 번호는 32바이트 단위이고 속성 bit0 =
# 타일 bit8(어드벤트에서 확인한 규칙; 예전 128바이트 단위 해석으로는 조립이 안 맞았다). 글자는 32x16 블록 + 꼬리 조각,
# 바탕 투명(0)·외곽선 1·속 4(음영 2·3). 표기는 배경 라벨(elf.bin)과 같게.
OVERLAY_221 = [([(0x08, 32, 16)], '왼팔'), ([(0x00, 32, 16)], '오른팔'),
               ([(0x20, 32, 16), (0x6c, 16, 16)], '편집'), ([(0x38, 32, 16), (0x80, 16, 16)], '기본'),
               ([(0x48, 32, 16), (0x40, 32, 16)], '종료')]


def buster_edit_overlay(rom):
    import gfx_zxa
    fid = rom.filenames.idOf('obj_fnt.bin'); F = bytearray(rom.files[fid])
    a, b = gfx_zxa.obj_entry(F, 221); e = memoryview(F)[a:b]
    h = struct.unpack_from('<5I', e, 0); tiles = e[h[0]:h[0] + (h[1] & 0xffff)]
    for pieces, text in OVERLAY_221:
        P = gfx_zxa.pieces_px(tiles, pieces); W = len(P[0])
        f = next(f for f in ('Galmuri11', 'Galmuri9', 'Galmuri7') if text_mask(text, f, 1)[0] + 2 <= W)
        gfx_zxa.relabel(P, text, (0, 16), 0, 4, 1, {1, 2, 3, 4}, xr=(0, W), font=f)
        gfx_zxa.put_pieces(tiles, pieces, P)
    rom.files[fid] = bytes(F)
