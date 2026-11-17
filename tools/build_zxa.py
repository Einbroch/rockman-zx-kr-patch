"""록맨 ZX 어드벤트 한글 빌드. python tools/build_zxa.py [-o out/zxa_kr.nds] [--allow-jp]
엔진은 ZX(build_zx.py)와 같고 판본 값만 다르다. 근거(어드벤트 ARM9 해제본, 11/16):
- 출력기 입구 0x0207FF6C (ZX 0x020078A8 와 같은 코드), 글자 처리 0x02080042(ZX 0x0200797E), 제어 0x0208005C,
  그리기 0x020800E0, FA 진행 0x020800C0(ZX 0x020079F6), 건너뛰기 0x02080464, 글자 수 0x02080510
  (0x020804A0 은 어드벤트에 새로 생긴 '바이트 수' 함수라 그대로 둔다 — 한글 2바이트도 바이트 수는 맞다).
- F0 사슬: F0 FF.. xx = 0xF0 + 0xFF*(FF 개수) + xx (글리프 562개).
- 글리프 기준 리터럴(0x0208028C) = 0x021175AC, FA 버퍼 0x0211FF54.
- 아레나 시작 리터럴 0x020A7524 = 0x021C38C0. 0x021C4000 부터 게임 고정 버퍼(리터럴 0x021C4000/4004/5800..).
"""
import sys, os, re, json, struct, argparse, zlib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ndspy.rom, ndspy.code
import zxtext, kfont12, asm
import build_zx as bz

SRC_ROM = os.path.join(ROOT, 'Rockman ZX Advent (J).nds')
SRC_CRC = 0x89C919BC
NGLYPH = 562
FONT = 0x021175AC
FABUF = 0x0211FF54
ARENA_LO_LIT = 0x020A7524
HOOK_BASE = 0x021C38C0
FREE_END = 0x021C4000
HOOK_RESERVE = 0x240
P_RENDER, P_CTRL, P_DRAW, P_FAADV, P_SKIP, P_COUNT = 0x02080042, 0x0208005C, 0x020800E0, 0x020800C0, 0x02080464, 0x02080510

# 문자표에서 특수 글리프 번호를 찾는다(어드벤트는 한자 구역 끝쪽에 있다)
CM = zxtext.load_charmap('zxa')
INV = {}
for g, ch in CM.items():
    INV.setdefault(ch, g)
SPECIAL = '✚ⒶⒷⓍⓎⓁⓇ▶・―─'
CHARMAP = dict(bz.CHARMAP)
for ch in SPECIAL:
    CHARMAP[ch] = INV[ch]
DOT = max(g for g, ch in CM.items() if ch == '.')            # 끝쪽의 '.' (게임이 직접 찍을 수 있어 보존)
KEEP = set(range(0, 0x40)) | set(range(0xE5, 0x100)) | {CHARMAP[c] for c in SPECIAL} | {DOT} \
    | {g for g, ch in CM.items() if not ch or ch.startswith('{')}
FREE = [g for g in range(0x40, NGLYPH) if g not in KEEP]
SCR0 = FREE[-2]; assert FREE[-1] == SCR0 + 1, '임시 칸 두 개는 이어져야 한다'
FREE = FREE[:-2]


# 본체 폰트(font_jp)가 아니라 다운로드 플레이 자기용 font_ds 로 그리는 파일: 원문 유지, 칸 보호 대상 아님
OTHER_FONT = {'m_mg_ds_jp.bin'}


def runs(gs):
    out = []
    for g in gs:
        if out and g == out[-1][1]: out[-1][1] = g + 1
        else: out.append([g, g + 1])
    return out


def enc_glyph(g):
    if g < 0xF0: return bytes([g])
    g -= 0xF0; out = bytearray([0xF0])
    while g >= 0xFF: out.append(0xFF); g -= 0xFF
    out.append(g); return bytes(out)


def encode_ko(s, kr, errors):
    out = bytearray(); i = 0
    while i < len(s):
        if s.startswith('{p}\n', i): out.append(0xFD); i += 4; continue
        c = s[i]
        if c == '\n': out.append(0xFC); i += 1; continue
        if c == '{':
            m = re.match(r'\{J([0-9A-F]{3})\}', s[i:])
            if m: out += enc_glyph(int(m[1], 16)); i += m.end(); continue
            m = re.match(r'\{([0-9A-F]{2})(?::([0-9a-f]+))?\}', s[i:])
            if not m: raise ValueError('알 수 없는 표기: ' + s[i:i + 12])
            out.append(int(m[1], 16)); out += bytes.fromhex(m[2] or ''); i += m.end(); continue
        c = bz.norm(c); i += 1
        if c in kr:
            k = kr[c]; out += bytes([bz.LEAD0 + k // bz.TRAIL, k % bz.TRAIL]); continue
        g = CHARMAP.get(c)
        if g is None: errors.append(c); continue
        out += enc_glyph(g)
    return bytes(out)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', default=os.path.join(ROOT, 'out', 'zxa_kr.nds'))
    ap.add_argument('--allow-jp', action='store_true', help='번역 없는 메시지를 원문으로 둔 채 빌드(시험용)')
    ap.add_argument('--check', action='store_true', help='폭·인코딩만 검사하고 끝낸다')
    a = ap.parse_args()
    raw = open(SRC_ROM, 'rb').read()
    assert zlib.crc32(raw) == SRC_CRC, '원본 롬 CRC 불일치'
    rom = ndspy.rom.NintendoDSRom(raw)
    jp = json.load(open(os.path.join(ROOT, 'data', 'zxa_jp.json'), encoding='utf-8'))
    tr = bz.load_translations('zxa', jp)

    by_src = {}
    for f, v in jp.items():
        for i, m in enumerate(v['msgs']):
            t = tr.get((f[:-4], i))
            if t is not None: by_src.setdefault(m['s'], t)
    bz.address_gate('zxa', jp, tr, by_src)
    bz.lead_gate('zxa', jp, tr)
    plan = {}; n_tr = n_jp = 0; missing = []
    for f, v in jp.items():
        for i, m in enumerate(v['msgs']):
            t = tr.get((f[:-4], i))
            if t is None and m['s']: t = by_src.get(m['s'])
            if t is None:
                n_jp += 1
                if f not in OTHER_FONT and re.search(r'[ぁ-んァ-ヶ一-龯]', m['s']): missing.append((f, i))
            else: n_tr += 1
            plan[(f, i)] = t
    over = [(f, i, max(bz.line_widths(t)), bz.width_limit(f[:-4], jp[f]['msgs'][i]['s']))
            for (f, i), t in plan.items() if t is not None]
    over = [o for o in over if o[2] > o[3]]
    if over: print(f'줄 폭 초과 {len(over)}건, 예:', over[:8])
    hangul = bz.collect_hangul([t for t in plan.values() if t])
    kr = {ch: k for k, ch in enumerate(hangul)}
    print(f'번역 {n_tr}, 원문 {n_jp} (일본어가 남는 메시지 {len(missing)}); 한글 음절 {len(hangul)}')
    if a.check:
        errs = []
        for (f, i), t in plan.items():
            if t is not None: encode_ko(t, kr, errs)
        if errs:
            from collections import Counter; print('인코딩 불가:', Counter(errs).most_common(20))
        return
    if missing and not a.allow_jp: sys.exit('빌드 중단: 미번역 메시지가 있다(--allow-jp 로 시험 빌드)')

    errors = []
    for f, v in jp.items():
        fid = rom.filenames.idOf(f); b = rom.files[fid]
        A, base, offs = zxtext.parse(b)
        body = bytearray(); newoff = {}; msgs = v['msgs']
        for i, m in enumerate(msgs):
            newoff[m['off']] = len(body)
            t = plan[(f, i)]
            if t is None:
                e = i + 1 < len(msgs) and base + msgs[i + 1]['off'] or (A + 4)
                body += b[base + m['off']:e]
            else:
                body += encode_ko(t, kr, errors) + bytes([int(m['end'], 16)])
        offs2 = [newoff[o] for o in offs]; B = len(offs) * 2
        assert len(body) + B < 0x10000, f
        rom.files[fid] = struct.pack('<HH', B + len(body), B) + struct.pack('<%dH' % len(offs), *offs2) + bytes(body)
    if errors:
        from collections import Counter
        print('인코딩 불가 문자:', Counter(errors).most_common(30)); sys.exit('빌드 중단: 인코딩 불가 문자')

    # ---- 폰트 ----
    ffid = rom.filenames.idOf('font_jp.bin'); F = bytearray(rom.files[ffid])
    assert len(F) == 0x20 + NGLYPH * 32 and struct.unpack_from('<H', F, 0)[0] == 12
    for ch, g in bz.REDRAW.items():
        F[0x20 + g * 32:0x20 + g * 32 + 32] = bz.glyph_bytes(ch)
    F[0x20:0x40] = bz.glyph_bytes(' ')
    packed = [bz.pack_glyph(ch) for ch in hangul]
    # 영소문자(0x25..0x3E)·전각 기호(0xE5..0xFF) 중 어떤 원고(번역문·남은 일본어)에도 안 나오는 칸은 한글 칸으로 돌린다.
    # 숫자·영대문자·'－'·공백(0x00..0x24, 0x3F)은 코드가 직접 찍을 수 있어 늘 보존한다.
    seen = set()
    for (f, i), t in plan.items():
        if t is not None:
            for mm in re.finditer(r'\{J([0-9A-F]{3})\}', t): seen.add(int(mm[1], 16))
            for ch in re.sub(r'\{[^}]*\}', '', t):
                g = CHARMAP.get(bz.norm(ch))
                if g is not None: seen.add(g)
        elif f not in OTHER_FONT:
            s_ = jp[f]['msgs'][i]['s']
            for mm in re.finditer(r'\{J([0-9A-F]{3})\}', s_): seen.add(int(mm[1], 16))
            for ch in re.sub(r'\{[^}]*\}', '', s_):
                if ch in INV: seen.add(INV[ch])
    reclaim = [g for g in list(range(0x25, 0x3F)) + list(range(0xE5, 0x100)) if g not in seen]
    print(f'되돌린 칸 {len(reclaim)}개:', ''.join(CM[g] for g in reclaim))
    free = sorted(FREE + reclaim)
    if a.allow_jp:      # 시험 빌드: 아직 번역 안 된 대사가 쓰는 칸은 덮지 않는다(덮으면 폭 값이 깨져 화면 붕괴, 11/16 실측)
        used = set()
        for (f, i), t in plan.items():
            if t is None and f not in OTHER_FONT:
                s_ = jp[f]['msgs'][i]['s']
                for mm in re.finditer(r'\{J([0-9A-F]{3})\}', s_): used.add(int(mm[1], 16))
                for ch in re.sub(r'\{[^}]*\}', '', s_):
                    if ch in INV: used.add(INV[ch])
        free = [g for g in free if g not in used]
    regions = [(FONT + a * 32, (b - a) * 2) for a, b in runs(free)]
    e_start = HOOK_BASE + HOOK_RESERVE
    regions.append((e_start, (FREE_END - e_start) // 16))
    cap = sum(n for _, n in regions)
    assert len(packed) <= cap, f'한글 {len(packed)}자 > 상주 용량 {cap}자'
    stream = b''.join(packed); pos = 0; e_data = b''
    for addr, n in regions:
        chunk = stream[pos:pos + n * 16]; pos += n * 16
        if addr == e_start: e_data = chunk
        else:
            o = 0x20 + (addr - FONT); F[o:o + len(chunk)] = chunk
    for g in (SCR0, SCR0 + 1):
        F[0x20 + g * 32:0x20 + g * 32 + 32] = bytes(32)
    rom.files[ffid] = bytes(F)
    print(f'한글 상주 {len(packed)}/{cap}자 (임시 칸 {SCR0:#x})')

    # ---- ARM9 ----
    m9 = rom.loadArm9(); main_ = m9.sections[0]; d = bytearray(main_.data)
    import nameplate_zxa; nameplate_zxa.apply(d)                         # 대화창 화자 이름표
    def put(addr, bs):
        o = addr - 0x02000000; d[o:o + len(bs)] = bs
    sym = dict(HDR=FONT - 0x20, FONT=FONT, FABUF=FABUF, SCR0=SCR0)
    src = open(os.path.join(HERE, 'zxahook.s'), encoding='utf-8').read()
    src = src.replace('KRTAB_WORDS', ', '.join('0x%X, %d' % r for r in regions))
    code = asm.assemble(src, HOOK_BASE, sym)
    bad = asm.check_thumb1(code, HOOK_BASE); assert not bad, bad
    assert len(code) <= HOOK_RESERVE, len(code)
    lab = {n: asm.label_addr(src, HOOK_BASE, n, sym) for n in ('hook_render', 'skip_impl', 'count_impl')}
    p = P_RENDER
    assert d[p - 0x02000000:p - 0x02000000 + 2] == bytes.fromhex('f028')     # cmp r0,#0xf0
    blk = struct.pack('<H', 0x4669) + bz.thumb_bl(p + 2, lab['hook_render']) + struct.pack('<H', 0x2900) \
        + bz.thumb_b(p + 8, P_CTRL, cond=0) + bz.thumb_b(p + 10, P_DRAW)
    blk += bz.NOP * ((P_CTRL - p - len(blk)) // 2)                         # 원래 F0 사슬 처리 자리까지 비움
    put(p, blk)
    assert d[P_FAADV - 0x02000000:P_FAADV - 0x02000000 + 2] == bytes.fromhex('1c99')
    put(P_FAADV, struct.pack('<HH', 0x9901, 0x8D8F) + bz.NOP * 3)
    for at, tgt in ((P_SKIP, lab['skip_impl']), (P_COUNT, lab['count_impl'])):
        assert (at + 4) % 4 == 0
        put(at, struct.pack('<HHI', 0x4B00, 0x4718, tgt | 1))
    sec = code + bytes(HOOK_RESERVE - len(code)) + e_data
    sec += bytes(-len(sec) % 32)
    arena_lo = HOOK_BASE + len(sec)
    assert arena_lo <= FREE_END, hex(arena_lo)
    assert struct.unpack_from('<I', d, ARENA_LO_LIT - 0x02000000)[0] == HOOK_BASE
    put(ARENA_LO_LIT, struct.pack('<I', arena_lo))
    main_.data = bytes(d)
    m9.sections.append(ndspy.code.MainCodeFile.Section(sec, HOOK_BASE, 0))
    rom.arm9 = m9.save(compress=False)
    os.makedirs(os.path.dirname(a.o), exist_ok=True)
    import gfx_zxa; gfx_zxa.apply(rom)                                    # 그림 글자
    rom.saveToFile(a.o)
    out = open(a.o, 'rb').read()
    print(f'출력 {a.o} {len(out)} CRC {zlib.crc32(out):08X} 훅 {len(code)} 바이트, 아레나 시작 {arena_lo:#x}')


if __name__ == '__main__':
    main()
