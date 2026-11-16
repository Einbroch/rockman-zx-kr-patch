"""NDS/GBA LZ77 (0x10) 해제·압축(압축은 재압축이 필요할 때만)."""
def decompress(d, off=0):
    assert d[off] == 0x10, hex(d[off])
    n = d[off+1] | d[off+2] << 8 | d[off+3] << 16
    out = bytearray(); i = off + 4
    while len(out) < n:
        f = d[i]; i += 1
        for b in range(8):
            if len(out) >= n: break
            if f & (0x80 >> b):
                v = d[i] << 8 | d[i+1]; i += 2
                l = (v >> 12) + 3; disp = (v & 0xfff) + 1
                for _ in range(l): out.append(out[-disp])
            else:
                out.append(d[i]); i += 1
    return bytes(out), i - off

def compress(data):
    """간단한 탐욕 LZ10 (윈도 4KB, 길이 3~18). VRAM 안전: 거리 1 참조를 쓰지 않는다
    (게임이 VRAM 으로 바로 풀면 16비트 쓰기라 거리 1 이 깨진다 — 타이틀 화면 전체가 깨진 원인)."""
    out = bytearray([0x10, len(data) & 255, len(data) >> 8 & 255, len(data) >> 16 & 255])
    i = 0; n = len(data)
    while i < n:
        flag_pos = len(out); out.append(0); flag = 0
        for b in range(8):
            if i >= n: break
            best_l = 0; best_d = 0
            start = max(0, i - 4096)
            for j in range(i - 2, start - 1, -1):
                l = 0
                while l < 18 and i + l < n and data[j + l] == data[i + l]:
                    l += 1
                if l > best_l:
                    best_l, best_d = l, i - j
                    if l == 18: break
            if best_l >= 3:
                flag |= 0x80 >> b
                v = ((best_l - 3) << 12) | (best_d - 1)
                out += bytes([v >> 8, v & 255]); i += best_l
            else:
                out.append(data[i]); i += 1
        out[flag_pos] = flag
    while len(out) % 4: out.append(0)
    return bytes(out)
