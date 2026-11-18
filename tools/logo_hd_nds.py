"""타이틀 로고를 사용자 제작 HD 한글 로고(art/logo_hd/{zx,zxa}.png)로 통째로 바꾼다 (ZX·ZXA 공용, NDS·컬렉션 공용).

로고 층은 8bpp BG(title.bin 그림1 + 로고 맵). 방법:
1. 원래 로고(일본판 로고 픽셀, 저작권 줄 위)의 상자에 HD 로고를 비율 유지로 줄여 놓는다(LANCZOS, 알파 128 이상).
2. 색: 캡처로 뽑은 팔레트 표(data/*_logo_pal.json)에 있는 색 번호(= 원래 로고가 쓰던 색) 중 가장 가까운 색.
   ZX 는 확장 팔레트 슬롯(칸마다 4·5) — 새 칸은 슬롯 4(로고 색 234개가 여기). ZXA 는 슬롯 0 하나.
3. 상자를 덮는 칸 전체를 새 그림으로 다시 칠하고 gfx_bg.assign 으로 타일 배정(편집 칸만 쓰던 타일 재사용·같은 그림 공유,
   모자라면 덧붙임). ZXA 는 그림1 뒤 VRAM 을 다른 데이터가 써서 덧붙이면 안 된다 → 덧붙임 0 이 될 때까지 1% 씩 줄인다.
"""
import json
import os
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bglabel
import gfx_bg

ALPHA = 128
COPYRIGHT_Y = 172       # 이 행부터 아래는 저작권 줄(건드리지 않는다)


def art(name):
    a = Image.open(os.path.join(ROOT, 'art', 'logo_hd', f'{name}.png')).convert('RGBA')
    return a.crop(a.getbbox())


def _pal(pal, slotted):
    """{슬롯: {번호: rgb}}"""
    out = {}
    for k, v in pal.items():
        if slotted:
            s, i = map(int, k.split(','))
        else:
            s, i = 0, int(k)
        if i:
            out.setdefault(s, {})[i] = tuple(v)
    return out


def _near(cands, rgb, cache):
    key = rgb
    if key not in cache:
        r, g, b = rgb
        cache[key] = min(cands, key=lambda ic: (ic[1][0] - r) ** 2 * 3 + (ic[1][1] - g) ** 2 * 4 + (ic[1][2] - b) ** 2 * 2)[0]
    return cache[key]


def apply_title(raw, pal, name, logo_map, other_maps, slotted, allow_add, max_tiles=1024):
    pals = _pal(pal, slotted)
    slot_new = 4 if slotted else 0
    cands = sorted(pals[slot_new].items())
    img = art(name)
    for k in range(0, 40):
        sc = 1 - k * 0.01
        A = gfx_bg.Arc(raw)
        t = A.tiles(1)
        md = A.map(logo_map)
        rows = len(md) // 64
        # 원래 로고 상자(0 이 아닌 픽셀, 저작권 줄 위)
        xs, ys = [], []
        for cy in range(min(rows, COPYRIGHT_Y // 8)):
            for cx in range(32):
                v = bglabel.cell(md, cx, cy)
                px = bglabel.tile_px(t, v)
                for y in range(8):
                    for x in range(8):
                        if px[y][x] and cy * 8 + y < COPYRIGHT_Y:
                            xs.append(cx * 8 + x); ys.append(cy * 8 + y)
        bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
        bw, bh = bx1 - bx0 + 1, by1 - by0 + 1
        fit = min(bw / img.width, bh / img.height) * sc
        w, h = max(1, round(img.width * fit)), max(1, round(img.height * fit))
        small = img.resize((w, h), Image.LANCZOS).load()
        ox, oy = bx0 + (bw - w) // 2, by0 + (bh - h) // 2
        cache = {}
        ink = {}
        for y in range(h):
            for x in range(w):
                r, g, b, a = small[x, y]
                if a >= ALPHA:
                    ink[(ox + x, oy + y)] = _near(cands, (r, g, b), cache)
        cx0, cy0 = min(bx0, ox) // 8, min(by0, oy) // 8
        cx1, cy1 = max(bx1, ox + w - 1) // 8, max(by1, oy + h - 1) // 8
        if cy1 * 8 + 7 >= COPYRIGHT_Y:
            raise ValueError(f'{name} logo reaches the copyright row')
        cols = cx1 - cx0 + 1
        cells = [(cx, cy) for cy in range(cy0, cy1 + 1) for cx in range(cx0, cx1 + 1)]
        P = [[ink.get((cx0 * 8 + x, cy0 * 8 + y), 0) for x in range(cols * 8)] for y in range((cy1 - cy0 + 1) * 8)]
        for cx, cy in cells:      # 새 로고가 그리는 칸은 새 슬롯
            if any((cx * 8 + x, cy * 8 + y) in ink for y in range(8) for x in range(8)):
                v = bglabel.cell(md, cx, cy)
                bglabel.set_cell(md, cx, cy, (v & 0x0fff) | (slot_new << 12))
        maps, keep = [md], set()
        e1 = A.ents[1]
        for m in other_maps:      # 폭 32 가 아닌 맵(ZXA 12번 36칸)은 쓰는 타일을 보호만
            mo = struct.unpack_from('<I', e1, 4 * m)[0]
            mw, mh = struct.unpack_from('<HH', e1, mo + 4)
            if mw == 32:
                maps.append(A.map(m))
            else:
                keep |= {struct.unpack_from('<H', e1, mo + 8 + 2 * i)[0] & 0x3ff for i in range(mw * mh)}
        added = gfx_bg.assign(t, [(md, cells, P, cols)], maps, keep=keep)
        if len(t) // 64 > max_tiles:
            raise ValueError(f'{name} logo: {len(t) // 64} tiles > {max_tiles}')
        if added and not allow_add:
            continue
        # 게이트: 새 로고 픽셀이 화면에 그대로
        for (x, y), v in ink.items():
            if bglabel.tile_px(t, bglabel.cell(md, x // 8, y // 8))[y % 8][x % 8] != v:
                raise ValueError(f'{name} logo pixel ({x}, {y}) lost')
        print(f'{name} HD 로고: 크기 {w}x{h} @ ({ox},{oy}) (비율 {sc:.2f}), 칸 {len(cells)}, 덧붙인 타일 {added}, 색 {len(cands)}')
        return A.build()
    raise ValueError(f'{name} logo: no size fits without adding tiles')
