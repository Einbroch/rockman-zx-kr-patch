"""록맨 ZX 한글판 빌드.

  python tools/build_zx.py [--dev] [-o out/zx_kr.nds]

번역: data/ko/zx/<파일>.txt  (블록 "## 번호" 뒤 본문, 표기는 data/zx_jp.json 과 같음)
--dev : 번역이 없는 메시지를 참고 문장(work/zx_ref.json, 제어 골격 일치분)으로 채운다. 배포 금지.

한 일: 대사 파일 재조립(A·B·오프셋표), font_jp.bin(영숫자·문장부호 갈무리 비례폭 + 뒤에 한글 글리프),
ARM9(훅 autoload 구역 + 출력기/글자 수/건너뛰기/FA 패치 + 메인 아레나 시작 이동).
"""
import sys, os, re, json, struct, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ndspy.rom, ndspy.code
import zxtext, kfont12, asm, gfx_zx, gfx_sub, gfx_bg, logo_zx, nameplate_zx

SRC_ROM = os.path.join(ROOT, 'Rockman ZX (J).nds')
SRC_CRC = 0xB577BBE0

# ---- 주소 (일본판 ARZJ, ARM9 압축 해제 기준) ----
FONT = 0x020FCD84          # 글리프 0 (파일 버퍼 0x020FCD64 + 헤더 0x20)
FILENAME = 0x020C6604      # "font_jp.bin"
FABUF = 0x0210419C
FREE_END = 0x0219C000      # 게임이 0x0219C000 부터 고정 버퍼로 쓴다(실측) — 우리 구역은 이 앞까지만
# 한국어판에서 안 쓰는 font_jp 글리프 칸(압축 한글 저장소). 남기는 칸: 0x00~0x3F 영숫자, 0xE5~0xFF 기호,
# 0x141 ・, 0x146~0x14C 아이콘, 0x171/0x172 선, 0x18C ▶. 0x18A/0x18B 는 임시 칸.
FONT_FREE = [(0x40, 0xE5), (0x100, 0x141), (0x142, 0x146), (0x14D, 0x171), (0x173, 0x18A)]
SCR0 = 0x18A
ARENA_LO_LIT = 0x020A8B9C  # OS 초기 메인 아레나 시작 리터럴 (원래 0x02199FC0 = 오버레이 최대 끝)
HOOK_BASE = 0x02199FC0
HOOK_RESERVE = 0x400
LEAD0, NLEAD, TRAIL = 0x40, 16, 240

# ---- 문자 -> 바이트 ----
HEAD = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-"
PUNCT = {'!': 0xE5, '"': 0xE6, '#': 0xE7, '$': 0xE8, '%': 0xE9, '&': 0xEA, "'": 0xEB, '(': 0xEC, ')': 0xED,
         '*': 0xEE, '+': 0xEF, ',': 0xF0, 'ー': 0xF1, '.': 0xF2, '/': 0xF3, ':': 0xF4, '<': 0xF5, '=': 0xF6,
         '>': 0xF7, '?': 0xF8, '[': 0xF9, ']': 0xFA, '_': 0xFB, '~': 0xFC, '「': 0xFD, '」': 0xFE, '…': 0xFF,
         '・': 0x141, '―': 0x171, '─': 0x172,
         '✚': 0x146, 'Ⓐ': 0x147, 'Ⓑ': 0x148, 'Ⓧ': 0x149, 'Ⓨ': 0x14A, 'Ⓛ': 0x14B, 'Ⓡ': 0x14C, '▶': 0x18C}
ALIAS = {'！': '!', '？': '?', '、': ',', '。': '.', '，': ',', '．': '.', '～': '~', '：': ':', '／': '/',
         '（': '(', '）': ')', '－': '-', '＋': '+', '％': '%', '＆': '&', '“': '"', '”': '"', '‘': "'", '’': "'",
         '『': '「', '`': "'", '』': '」', '·': '・', '—': '―', '　': ' '}
CHARMAP = {ch: i for i, ch in enumerate(HEAD)}
CHARMAP.update(PUNCT)
# 갈무리로 다시 그릴 칸 (문자 -> 글리프 번호). 「」…・―─ 는 원본 일본 글리프 유지(폭 12).
REDRAW = {ch: g for ch, g in CHARMAP.items() if ch not in '「」…・―─ー' and ch != ' ' and g < 0x100}


def norm(ch):
    return ALIAS.get(ch, ch)


def collect_hangul(texts):
    s = set()
    for t in texts:
        for ch in re.sub(r'\{[^}]*\}', '', t):
            if '가' <= ch <= '힣':
                s.add(ch)
    return sorted(s)


def encode_ko(s, kr, errors):
    out = bytearray(); i = 0
    while i < len(s):
        if s.startswith('{p}\n', i):
            out.append(0xFD); i += 4; continue
        c = s[i]
        if c == '\n':
            out.append(0xFC); i += 1; continue
        if c == '{':
            m = re.match(r'\{J([0-9A-F]{3})\}', s[i:])
            if m:
                g = int(m[1], 16); i += m.end()
                out += bytes([g]) if g < 0xF0 else bytes([0xF0, g - 0xF0]); continue
            m = re.match(r'\{([0-9A-F]{2})(?::([0-9a-f]+))?\}', s[i:])
            if not m:
                raise ValueError('알 수 없는 표기: ' + s[i:i + 12])
            out.append(int(m[1], 16)); out += bytes.fromhex(m[2] or ''); i += m.end(); continue
        c = norm(c); i += 1
        if c in kr:
            k = kr[c]; out += bytes([LEAD0 + k // TRAIL, k % TRAIL]); continue
        g = CHARMAP.get(c)
        if g is None:
            errors.append(c); continue
        out += bytes([g]) if g < 0xF0 else bytes([0xF0, g - 0xF0])
    return bytes(out)


def glyph_bytes(ch, width=None):
    dw = kfont12.glyphs()[ord(ch)][0]
    g = bytearray(kfont12.glyph(ch))
    w = width or dw
    w = (w + 3) // 4 * 4   # 폭은 4의 배수: 4bpp 출력은 4px=2바이트 단위로 복사하고, 서브 화면은 VRAM 에 직접 그려
                           # 1바이트 복사(2px 조각)가 깨진다(공백 6px 로 서브 화면 붕괴, 11/16 실측). 홀수 폭은 대화창도 붕괴.
    assert 4 <= w <= 12 and w % 4 == 0, (ch, w)
    v = struct.unpack_from('<H', g, 0)[0] & 0x0FFF
    struct.pack_into('<H', g, 0, v | ((w & 0xF) << 12))
    return bytes(g)


def pack_glyph(ch):
    """한글 12x16 글리프 -> 16바이트(2~12행, 행마다 11비트, LSB 먼저)."""
    g = kfont12.glyph(ch)
    rows = [struct.unpack_from('<H', g, 2 * y)[0] for y in range(16)]
    assert not any(rows[y] for y in (0, 1, 13, 14, 15)) and not any(r >> 11 for r in rows), ch
    bits = 0
    for i, y in enumerate(range(2, 13)):
        bits |= rows[y] << (i * 11)
    return bits.to_bytes(16, 'little')


def set_width(gl, w):
    gl = bytearray(gl)
    v = struct.unpack_from('<H', gl, 0)[0] & 0x0FFF
    struct.pack_into('<H', gl, 0, v | ((w & 0xF) << 12))
    return bytes(gl)


def thumb_bl(at, target):
    off = target - (at + 4)
    assert -0x400000 <= off < 0x400000
    return struct.pack('<HH', 0xF000 | ((off >> 12) & 0x7FF), 0xF800 | ((off >> 1) & 0x7FF))


def thumb_b(at, target, cond=None):
    off = (target - (at + 4)) >> 1
    if cond is None:
        assert -1024 <= off < 1024; return struct.pack('<H', 0xE000 | (off & 0x7FF))
    assert -128 <= off < 128; return struct.pack('<H', 0xD000 | (cond << 8) | (off & 0xFF))


NOP = struct.pack('<H', 0x46C0)


def load_translations(game, jp):
    d = os.path.join(ROOT, 'data', 'ko', game); tr = {}
    if not os.path.isdir(d):
        return tr
    for f in os.listdir(d):
        if not f.endswith('.txt'):
            continue
        name = f[:-4]
        txt = open(os.path.join(d, f), encoding='utf-8').read().replace('\r\n', '\n')
        for blk in re.split(r'^## ', txt, flags=re.M)[1:]:
            head, _, body = blk.partition('\n')
            idx = int(head.split()[0])
            # ';' 로 시작하는 줄은 주석(원문·참고). 끝 빈 줄은 블록 구분.
            body = '\n'.join(l for l in body.split('\n') if not l.startswith(';')).rstrip('\n')
            if body.strip():
                tr[(name, idx)] = body
    return tr


def char_width(ch):
    ch = norm(ch)
    if ch == ' ':
        return 4
    if '가' <= ch <= '힣' or ch not in REDRAW:
        return 12
    w = kfont12.glyphs()[ord(ch)][0]
    return (w + 3) // 4 * 4


def line_widths(s, jp=False):
    out = []
    for ln in s.replace('{p}\n', '\n').split('\n'):
        ln = ln.replace('{FA}', 'ＮＮ' if not jp else 'ＮＮＮ')   # 주인공 이름: 한국어 최대 2자(에일), 일본어 3자(エール)
        ln = re.sub(r'\{(?!J)[^}]*\}', '', ln)
        ln = re.sub(r'\{J[0-9A-F]{3}\}', 'X', ln)
        out.append(12 * len(ln) if jp else sum(char_width(c) for c in ln))
    return out


TALK_MIN = 180   # 대화창 실측(11/16): 15자까지 정상, 16자는 끝이 잘리고 줄 첫 글자가 깨진다


def width_limit(name, src):
    lim = max(line_widths(src, jp=True))
    return max(lim, TALK_MIN) if name.startswith('talk_') else lim


def skeleton(s):
    return re.findall(r'\{(?:F[1-9A-B]|p)[^}]*\}', s)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument('--dev', action='store_true')
    ap.add_argument('--stage', type=int, default=9, help='디버그: 1=구역+아레나만 2=+출력기 3=+FA 4=+건너뛰기/글자수, 텍스트는 stage<9면 원문')
    ap.add_argument('-o', default=os.path.join(ROOT, 'out', 'zx_kr.nds'))
    a = ap.parse_args()
    import zlib
    raw = open(SRC_ROM, 'rb').read()
    assert zlib.crc32(raw) == SRC_CRC, '원본 롬 CRC 불일치'
    rom = ndspy.rom.NintendoDSRom(raw)
    jp = json.load(open(os.path.join(ROOT, 'data', 'zx_jp.json'), encoding='utf-8'))
    cmj = zxtext.prep(zxtext.load_charmap('zx'), False)
    tr = load_translations('zx', jp)
    refm = json.load(open(os.path.join(ROOT, 'work', 'zx_ref.json'), encoding='utf-8')) if a.dev else {}

    # 메시지별 최종 문자열(한국어) 또는 None(원문 유지)
    by_src = {}
    for f, v in jp.items():
        for i, m in enumerate(v['msgs']):
            t = tr.get((f[:-4], i))
            if t is not None:
                by_src.setdefault(m['s'], t)
    plan = {}; n_tr = n_dev = n_jp = 0
    for f, v in jp.items():
        name = f[:-4]; ks = refm.get(f, [])
        for i, m in enumerate(v['msgs']):
            t = tr.get((name, i))
            if t is None and m['s']:
                t = by_src.get(m['s'])
            if t is None and a.dev and i < len(ks) and m['s'] and skeleton(ks[i]) == skeleton(m['s']):
                t = ks[i]; n_dev += 1
            elif t is not None:
                n_tr += 1
            if t is None:
                n_jp += 1
            plan[(f, i)] = t
    over = []
    for (f, i), t in plan.items():
        if t is None:
            continue
        lim = width_limit(f[:-4], jp[f]['msgs'][i]['s'])
        w = max(line_widths(t))
        if w > lim:
            over.append((f, i, w, lim))
    if over:
        print(f'줄 폭 초과(원문 최장 줄 기준) {len(over)}건, 예:', over[:5])
    hangul = collect_hangul([t for t in plan.values() if t])
    assert len(hangul) <= NLEAD * TRAIL
    kr = {ch: k for k, ch in enumerate(hangul)}
    print(f'번역 {n_tr}, 개발용 채움 {n_dev}, 원문 {n_jp}; 한글 음절 {len(hangul)}')

    # ---- 대사 파일 ----
    errors = []
    for f, v in jp.items():
        fid = rom.filenames.idOf(f); b = rom.files[fid]
        A, base, offs = zxtext.parse(b)
        body = bytearray(); newoff = {}
        msgs = v['msgs']
        for i, m in enumerate(msgs):
            newoff[m['off']] = len(body)
            t = plan[(f, i)]
            if t is None:
                e = i + 1 < len(msgs) and base + msgs[i + 1]['off'] or (A + 4)
                body += b[base + m['off']:e]
            else:
                enc = encode_ko(t, kr, errors)
                body += enc + bytes([int(m['end'], 16)])
        offs2 = [newoff[o] for o in offs]
        B = len(offs) * 2
        assert len(body) + B < 0x10000, f
        out = struct.pack('<HH', B + len(body), B) + struct.pack('<%dH' % len(offs), *offs2) + bytes(body)
        rom.files[fid] = out
    if errors:
        from collections import Counter
        c = Counter(errors)
        print('인코딩 불가 문자:', c.most_common(30))
        if not a.dev:
            sys.exit('빌드 중단: 인코딩 불가 문자')

    # ---- 폰트 ----
    ffid = rom.filenames.idOf('font_jp.bin'); F = bytearray(rom.files[ffid])
    assert len(F) == 0x20 + 397 * 32
    for ch, g in REDRAW.items():
        F[0x20 + g * 32:0x20 + g * 32 + 32] = glyph_bytes(ch)
    F[0x20:0x40] = glyph_bytes(' ')                      # 공백 = 4px
    for g in (0xFD, 0xFE):                                 # 「」 원본 글리프, 폭 12
        pass
    packed = [pack_glyph(ch) for ch in hangul]
    regions = [(FONT + a * 32, (b - a) * 2) for a, b in FONT_FREE]
    e_start = HOOK_BASE + HOOK_RESERVE
    regions.append((e_start, (FREE_END - e_start) // 16))
    cap = sum(n for _, n in regions)
    assert len(packed) <= cap, f'한글 {len(packed)}자 > 상주 용량 {cap}자'
    stream = b''.join(packed); pos = 0; e_data = b''
    for addr, n in regions:
        chunk = stream[pos:pos + n * 16]; pos += n * 16
        if addr == e_start:
            e_data = chunk
        else:
            o = 0x20 + (addr - FONT)
            F[o:o + len(chunk)] = chunk
    for g in (SCR0, SCR0 + 1):
        F[0x20 + g * 32:0x20 + g * 32 + 32] = bytes(32)
    assert len(F) == 0x20 + 397 * 32
    rom.files[ffid] = bytes(F)
    print(f'한글 상주 {len(packed)}/{cap}자')

    # ---- 그림 글자 ----
    gfx_zx.apply(rom)
    gfx_sub.apply(rom)
    gfx_bg.apply(rom)
    logo_zx.apply(rom)

    # ---- ARM9 ----
    m9 = rom.loadArm9()
    main = m9.sections[0]
    d = bytearray(main.data)

    def put(addr, bs):
        o = addr - 0x02000000
        d[o:o + len(bs)] = bs

    sym = dict(HDR=FONT - 0x20, FONT=FONT, FABUF=FABUF, SCR0=SCR0)
    src = open(os.environ.get('HOOK_SRC', os.path.join(HERE, 'zxhook.s')), encoding='utf-8').read()
    src = src.replace('KRTAB_WORDS', ', '.join('0x%X, %d' % r for r in regions))
    code = asm.assemble(src, HOOK_BASE, sym)
    bad = asm.check_thumb1(code, HOOK_BASE)
    assert not bad, bad
    assert len(code) <= HOOK_RESERVE, len(code)
    lab = {n: asm.label_addr(src, HOOK_BASE, n, sym) for n in ('hook_render', 'skip_impl', 'count_impl')}

    # 출력기 0x0200797E..0x02007991 (20바이트)
    p = 0x0200797E
    blk = struct.pack('<H', 0x4669) + thumb_bl(p + 2, lab['hook_render']) + struct.pack('<H', 0x2900) \
        + thumb_b(p + 8, 0x02007992, cond=0) + thumb_b(p + 10, 0x02007A16)
    blk += NOP * ((20 - len(blk)) // 2)
    assert d[p - 0x02000000:p - 0x02000000 + 2] == bytes.fromhex('f028')  # cmp r0,#0xf0
    if a.stage >= 2: put(p, blk)
    # FA 진행: 안쪽 출력기가 남긴 커서([ctx+0x2C])를 그대로 쓴다. 0x020079F6..0x020079FF
    assert d[0x79F6:0x79F8] == bytes.fromhex('1c99')        # ldr r1,[sp,#0x70]
    if a.stage >= 3: put(0x020079F6, struct.pack('<HH', 0x9901, 0x8D8F) + NOP * 3)   # ldr r1,[sp,#4]; ldrh r7,[r1,#0x2c]
    # 건너뛰기·글자 수 함수 통째로 대체
    for at, tgt in ((0x02007D7C, lab['skip_impl']), (0x02007DB0, lab['count_impl'])):
        assert (at + 4) % 4 == 0
        if a.stage >= 4: put(at, struct.pack('<HHI', 0x4B00, 0x4718, tgt | 1))
    # 아레나 시작 이동
    sec = code + bytes(HOOK_RESERVE - len(code)) + e_data
    sec += bytes(-len(sec) % 32)
    arena_lo = HOOK_BASE + len(sec)
    assert arena_lo <= FREE_END
    assert struct.unpack_from('<I', d, ARENA_LO_LIT - 0x02000000)[0] == HOOK_BASE
    put(ARENA_LO_LIT, struct.pack('<I', arena_lo))
    nameplate_zx.apply(d)          # 대화창 화자 이름표(ARM9 정적 데이터)
    main.data = bytes(d)
    m9.sections.append(ndspy.code.MainCodeFile.Section(sec, HOOK_BASE, 0))
    rom.arm9 = m9.save(compress=False)

    os.makedirs(os.path.dirname(a.o), exist_ok=True)
    rom.saveToFile(a.o)
    out = open(a.o, 'rb').read()
    print('출력', a.o, len(out), 'CRC %08X' % zlib.crc32(out), '훅', len(code), '바이트, 한글', len(hangul), '자, 아레나 시작', hex(arena_lo))


if __name__ == '__main__':
    main()
