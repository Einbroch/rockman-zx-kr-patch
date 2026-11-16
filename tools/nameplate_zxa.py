"""어드벤트 대화창 화자 이름표. 구조는 ZX 와 같다(nameplate_zx.py 설명 참고):
ARM9 정적 데이터 안에 이름 표(12바이트 칸 96개, 글꼴 번호 열 + 0xFF)와 8x8 8bpp 작은 글꼴이 있고,
글꼴 0x00..0x50 은 가나, 0x51..0x76 은 영문·'ー'·숫자·'?'. 가나 칸과 이름에 안 쓰는 영숫자 칸을 한글로 바꾼다."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import nameplate_zx as zx

TABLE = 0x020DEAA8          # 이름 표 (96칸 × 12바이트)
GLYPH = 0x020DF968          # 글꼴 번호 0 의 타일 (ZX 글꼴 0번과 같은 바이트로 확인)
KANA = zx.KANA
LATIN = zx.LATIN

NAMES = [
    '????', '그레이', '애시', '프로메테', '판도라', '알버트', '토마스', '미하일', '디아번', '크로노포스', '로즈파크',
    '콘도록', '카이제미네', '아고일', '우고일', '테스랏', '바이프로스트', '헬리오스', '테티스', '아틀라스', '샤르나크',
    '모델A', '모델X', '모델Z', '반', '에일', '믹', '로빈', '니콜', '라자러스', '레드', '빌리', '울프', '제리', '댄',
    '더그', '척', '로저', '커크', '킬리언', '팀', '에이브', '벤', '칼리', '로이', '워렌', '블로섬', '엘레나', '크리스',
    '자크', '로미오', '키드', '렘', '파트리스', '나나', '코코', '닉', '티나', '아울', '섀런', '에이미', '피에르', '존',
    '짐', '마리', '메그', '안나', '루디', '제임스', '레이', '워드', '?', '게리', '리처드', '버트', '안토니오', '조지',
    '패트릭', '로스코', '데일', '티리스', '오스틴', '니나', '재닛', '나디아', '마리나', '레이먼드', '톰', '애덤',
    '대니얼', '에릭', '줄리안', '시스템', '트랜스서버', '보안시스템', '워프포인트',
]
# 원문(해독): ????/グレイ/アッシュ/プロメテ/パンドラ/アルバート/…/システム/トランスサーバー/セキュリティシステム/ワープポイント


def apply(d, base=0x02000000):
    """d: ARM9 주 구역(해제본) bytearray."""
    o = lambda a: a - base
    assert d[o(TABLE):o(TABLE) + 5] == bytes([0x76] * 4 + [0xFF]), '이름 표 위치가 다름'
    assert d[o(TABLE) + 12:o(TABLE) + 16] == bytes([0x12, 0x4C, 0x01, 0xFF]), '이름 표 위치가 다름(グレイ)'
    assert len(NAMES) == 96
    syl = []
    for n in NAMES:
        for ch in n:
            if '가' <= ch <= '힣' and ch not in syl: syl.append(ch)
    keep = {ch for n in NAMES for ch in n if ch in LATIN}
    slots = list(range(KANA)) + [KANA + i for i, ch in enumerate(LATIN) if ch not in keep]
    assert len(syl) <= len(slots), f'이름 음절 {len(syl)} > 빈 칸 {len(slots)}'
    code = {ch: slots[i] for i, ch in enumerate(syl)}
    for i, ch in enumerate(LATIN):
        if ch in keep: code[ch] = KANA + i
    for ch in syl:
        i = code[ch]; d[o(GLYPH) + i * 64:o(GLYPH) + i * 64 + 64] = zx.glyph(ch)
    for k, n in enumerate(NAMES):
        enc = bytes(code[ch] for ch in n) + b'\xff'
        assert len(enc) <= 12, (n, len(enc))
        d[o(TABLE) + 12 * k:o(TABLE) + 12 * k + 12] = enc + bytes(12 - len(enc))
    print(f'이름표: {len(NAMES)}명, 한글 음절 {len(syl)}/{len(slots)}칸')
