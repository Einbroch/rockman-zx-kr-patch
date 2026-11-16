"""갈무리 BDF 읽기 + ZX 폰트 글리프(12x16 1bpp, 행마다 u16 LE, 비트 x = 픽셀 x). 한글 잉크 행 2~12(일본판 가나와 같은 높이)."""
import re,os
HERE=os.path.dirname(os.path.abspath(__file__))
_G={}
def glyphs(name='Galmuri11'):
    """글꼴 이름(external/fonts/<name>.bdf) -> {코드포인트: (dwidth, w, h, xoff, yoff, rows, bits)}"""
    if name not in _G:
        t=open(os.path.join(HERE,'..','external','fonts',name+'.bdf'),encoding='utf-8',errors='replace').read(); G={}
        for blk in t.split('STARTCHAR ')[1:]:
            m=re.search(r'ENCODING (-?\d+)',blk)
            if not m: continue
            dw=int(re.search(r'DWIDTH (\d+)',blk)[1])
            w,h,xo,yo=map(int,re.search(r'BBX (-?\d+) (-?\d+) (-?\d+) (-?\d+)',blk).groups())
            bm=blk.split('BITMAP\n',1)[1].split('ENDCHAR')[0].split()
            G[int(m[1])]=(dw,w,h,xo,yo,[int(r,16) for r in bm],len(bm[0])*4 if bm else 0)
        _G[name]=G
    return _G[name]
BASE=13   # 기준선 다음 행 (한글 h=11, yo=0 -> 행 2..12)
def glyph(ch,dx=0):
    dw,w,h,xo,yo,rows,bits=glyphs()[ord(ch)]
    out=[0]*16
    for r,v in enumerate(rows):
        y=BASE-yo-h+r
        for x in range(w):
            if v>>(bits-1-x)&1:
                X=x+xo+dx
                if 0<=X<12 and 0<=y<16: out[y]|=1<<X
    return b''.join(v.to_bytes(2,'little') for v in out)
