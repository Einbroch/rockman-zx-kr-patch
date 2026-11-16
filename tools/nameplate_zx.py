"""대화창 화자 이름표. ARM9 정적 데이터 안의 8x8 작은 글꼴(8bpp, 0 = 글자, 1 = 가장자리, 2 = 판 바탕)과
이름 표(12바이트 칸 88개, 글꼴 번호 열 + 0xFF)를 고친다. 글꼴은 글자 한 칸에 타일 하나라, 가나 81칸(ア..ン, 0x00..0x50)을
이름에 쓰는 한글 음절로 바꾸고 이름 표를 다시 쓴다. 영문·숫자·'?'(0x51..0x76) 중 이름에 안 쓰는 칸도 한글로 쓴다
(이 글꼴은 이름표 전용으로 보임 — 다른 화면에서 영문·숫자가 깨지면 이 가정을 의심)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import kfont12

TABLE = 0x020BE6B8          # 이름 표 (88칸 × 12바이트)
GLYPH = 0x020BF118          # 글꼴 번호 0 의 타일
KANA = 0x51                 # 0x00..0x50 = 가나(바꿀 칸)
LATIN = 'ABCDEFGHIJKLMNOPQRSTUVWXYZー0123456789?'   # 0x51..0x76

NAMES = [
    '????', '반', '에일', '지르웨', '프레리', '모델X', '모델Z', '모델H', '모델F', '모델L', '모델P', '모델O',
    '세르판', '프로메테', '판도라', '루아르', '하이볼트', '허리케누', '파프릴', '레그앵커', '플람마르', '프로텍터스',
    '피스트레오', '가디언', '플루브', '칼레', '앨런', '세드르', '사르딘', '스콩브레소스', '트뤼이트', '콩글', '통',
    '뮈게', '로즈', '실뤼르', '앙길', '가르데니아', '튤립', '마르그리트', '위예', '셴', '플라탄', '바르', '마크로',
    '몰뤼', '도라드', '보니트', '솔', '민간인', '알렌', '차보', '제프', '케니', '피트', '프랭크', '라벨', '유', '루',
    '사리아', '셰리', '아시아', '루카', '루크', '해리슨', '레오나르도', '레이븐', '소니아', '피오나', '미셸', '멜로디',
    '캐미', '캐스퍼', '잭', '로베르토', '모건', '실비아', '바바라', '캐런', '루시아', '맥스', '고요크', '보슈',
    '트랜스서버', '카니스', '오퍼레이터', '컴퓨터', '시스템',
]
# 원문 순서 확인용(표 해독 결과): ????/ヴァン/エール/ジルウェ/プレリー/モデルX..O/セルパン/プロメテ/パンドラ/ルアール/
# ハイボルト/ハリケンヌ/パープリル/レグアンカー/フランマール/プロテクタス/フィストレオ/ガーディアン/フルーブ/… /システム


def glyph(ch):
    """갈무리7 한글(7줄)을 8x8 타일 1~7행에: 글자 0, 오른쪽 가장자리 1, 바탕 2.
    (6줄로 줄이면 「르」의 ㄹ 이 ㄷ 처럼 뭉개진다 — 실측)"""
    import gfx_zx
    w, pts = gfx_zx.text_mask(ch, 'Galmuri7', 0)
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    tw = max(xs) - min(xs) + 1; th = max(ys) - min(ys) + 1
    assert tw <= 8 and th <= 7, (ch, tw, th)
    ox = (8 - tw) // 2 - min(xs); oy = 1 + (7 - th) - min(ys)
    pts = {(x + ox, y + oy) for x, y in pts}
    t = [[2] * 8 for _ in range(8)]
    for x, y in pts:
        q = (x + 1, y)
        if q not in pts and q[0] < 8: t[y][q[0]] = 1
    for x, y in pts: t[y][x] = 0
    return bytes(v for r in t for v in r)


def apply(d, base=0x02000000):
    """d: ARM9 주 구역(해제본) bytearray."""
    o = lambda a: a - base
    # 판본 확인: 표 0번 「????」, 1번 「ヴァン」
    assert d[o(TABLE):o(TABLE) + 5] == bytes([0x76] * 4 + [0xFF]), '이름 표 위치가 다름'
    assert d[o(TABLE) + 12:o(TABLE) + 16] == bytes([0x0A, 0x05, 0x50, 0xFF]), '이름 표 위치가 다름'
    assert len(NAMES) == 88
    syl = []
    for n in NAMES:
        for ch in n:
            if '가' <= ch <= '힣' and ch not in syl: syl.append(ch)
    keep = {ch for n in NAMES for ch in n if ch in LATIN}          # 이름에 쓰는 영문·'?'
    slots = list(range(KANA)) + [KANA + i for i, ch in enumerate(LATIN) if ch not in keep]
    assert len(syl) <= len(slots), f'이름 음절 {len(syl)} > 빈 칸 {len(slots)}'
    code = {ch: slots[i] for i, ch in enumerate(syl)}
    for i, ch in enumerate(LATIN):
        if ch in keep: code[ch] = KANA + i
    for ch in syl:
        i = code[ch]; d[o(GLYPH) + i * 64:o(GLYPH) + i * 64 + 64] = glyph(ch)
    for k, n in enumerate(NAMES):
        enc = bytes(code[ch] for ch in n) + b'\xff'
        assert len(enc) <= 12, (n, len(enc))
        d[o(TABLE) + 12 * k:o(TABLE) + 12 * k + 12] = enc + bytes(12 - len(enc))
    print(f'이름표: {len(NAMES)}명, 한글 음절 {len(syl)}/{len(slots)}칸 (가나 81 + 안 쓰는 영문·숫자)')
