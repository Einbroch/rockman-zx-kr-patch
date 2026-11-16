"""keystone Thumb 어셈블 래퍼: @주석 제거, 숫자 지역 레이블(1: / 1f / 1b) 풀기, 기호 치환."""
import re
import keystone


def preprocess(src, symbols):
    lines = []
    counter = {}
    defs = []  # (line_index, num, unique)
    raw = []
    for line in src.splitlines():
        line = line.split('@', 1)[0].rstrip()
        raw.append(line)
    # 지역 레이블 정의 위치 수집
    uid = 0
    labels = {}  # num -> list of (idx, name)
    for i, line in enumerate(raw):
        m = re.match(r'\s*(\d+):(.*)$', line)
        if m:
            uid += 1
            name = f'_L{m[1]}_{uid}'
            labels.setdefault(m[1], []).append((i, name))
            raw[i] = f'{name}:' + (('\n' + m[2]) if m[2].strip() else '')
    for i, line in enumerate(raw):
        def rep(m):
            num, d = m[1], m[2]
            cands = labels.get(num, [])
            if d == 'f':
                for idx, name in cands:
                    if idx > i:
                        return name
            else:
                for idx, name in reversed(cands):
                    if idx <= i:
                        return name
            raise ValueError(f'local label {num}{d} unresolved at line {i}')
        line = re.sub(r'\b(\d+)([fb])\b', rep, line)
        for k, v in symbols.items():
            line = re.sub(r'\b' + re.escape(k) + r'\b', f'0x{v:X}', line)
        lines.append(line)
    return '\n'.join(lines)


def assemble(src, base, symbols=None):
    ks = keystone.Ks(keystone.KS_ARCH_ARM, keystone.KS_MODE_THUMB)
    text = preprocess(src, symbols or {})
    try:
        enc, _ = ks.asm(text, base)
    except keystone.KsError as e:
        # 오류 줄 찾기: 한 줄씩 누적 어셈블
        acc = []
        for ln in text.splitlines():
            acc.append(ln)
            try:
                ks.asm('\n'.join(acc), base)
            except keystone.KsError as e2:
                if 'SYMBOL' in str(e2) or 'LABEL' in str(e2):
                    continue
                raise ValueError(f'asm error at: {ln!r}: {e2}') from None
        raise
    return bytes(enc)


def label_addr(src, base, label, symbols=None):
    """레이블 주소: 레이블 직전까지 어셈블한 길이로 계산 (레이블은 줄 맨 앞)."""
    text = preprocess(src, symbols or {})
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith(label + ':'):
            head = '\n'.join(lines[:i])
            ks = keystone.Ks(keystone.KS_ARCH_ARM, keystone.KS_MODE_THUMB)
            # 앞부분만 어셈블하면 뒤 레이블 참조가 풀리지 않으므로 전체에 표식 삽입
            marker = lines[:i] + [ln.replace(label + ':', label + ':\n.word 0xDEADBEEF', 1)] + lines[i+1:]
            enc, _ = ks.asm('\n'.join(marker), base)
            b = bytes(enc)
            off = b.find(bytes.fromhex('EFBEADDE'))
            return base + off
    raise KeyError(label)


def check_thumb1(code, base):
    """ARMv4T Thumb 만 허용: bl 외 32비트 명령이 있으면 실패."""
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    bad = []
    for ins in md.disasm(code, base):
        if ins.size == 4 and ins.mnemonic not in ('bl', 'blx'):
            bad.append(f'{ins.address:08x} {ins.mnemonic} {ins.op_str}')
    return bad
