"""obj_fnt.bin(타일+팔레트) + obj_dat.bin(프레임·OAM) 스프라이트 해석.
obj_fnt 항목: 헤더 [타일 오프셋, 타일 크기|플래그<<16, ?, 팔레트 오프셋, 팔레트 크기|플래그<<16]
obj_dat 항목: u32 프레임 수, u32 애니 오프셋, 프레임 표(+12 기준) [u16 레코드 오프셋, u16 레코드 수],
레코드 4바이트: 타일 단위(128바이트), 속성(상위 4비트 = 모양<<2|크기, 하위 = 팔레트?), x(s8), y(s8)."""
import struct
from PIL import Image
SIZES={0:[(8,8),(16,16),(32,32),(64,64)],1:[(16,8),(32,8),(32,16),(64,32)],2:[(8,16),(8,32),(16,32),(32,64)]}
def entry(buf,i):
    o=[struct.unpack_from('<I',buf,4+4*j)[0]&0x7fffffff for j in (i,i+1)]
    return buf[o[0]:o[1]]
def fnt(e):
    h=struct.unpack_from('<5I',e,0)
    tiles=e[h[0]:h[0]+(h[1]&0xffff)]
    pal=e[h[3]:h[3]+(h[4]&0xffff)]
    cols=[]
    for k in range(len(pal)//2):
        v=struct.unpack_from('<H',pal,2*k)[0]; cols.append(((v&31)*8,((v>>5)&31)*8,((v>>10)&31)*8))
    return h,tiles,cols
def frames(d):
    n=struct.unpack_from('<H',d,12)[0]//4; fr=[]   # 프레임 수 = 첫 레코드 오프셋/4
    for k in range(n):
        off,cnt=struct.unpack_from('<HH',d,12+4*k)
        recs=[]
        for r in range(cnt):
            t,a,x,y=struct.unpack_from('<BBbb',d,12+off+4*r)
            recs.append((t,a,x,y))
        fr.append(recs)
    return fr
def obj_pixels(tiles,unit,w,h):
    base=unit*128; px=[[0]*w for _ in range(h)]
    nt=0
    for ty in range(h//8):
        for tx in range(w//8):
            o=base+(ty*(w//8)+tx)*32
            for y in range(8):
                for x in range(8):
                    if o+y*4+x//2<len(tiles):
                        b=tiles[o+y*4+x//2]; px[ty*8+y][tx*8+x]=(b>>((x&1)*4))&15
    return px
def render_frame(tiles,cols,recs,pal_sel=0):
    boxes=[]
    for t,a,x,y in recs:
        w,h=SIZES[(a>>6)&3][(a>>4)&3]; boxes.append((x,y,x+w,y+h,t,w,h,a))
    if not boxes: return None
    x0=min(b[0] for b in boxes); y0=min(b[1] for b in boxes); x1=max(b[2] for b in boxes); y1=max(b[3] for b in boxes)
    im=Image.new('RGB',(x1-x0,y1-y0),(255,0,255))
    for x,y,_,_,t,w,h,a in boxes:
        px=obj_pixels(tiles,t,w,h); pb=(a&15)*16 if (a&15)*16<len(cols) else 0
        for yy in range(h):
            for xx in range(w):
                v=px[yy][xx]
                if v: im.putpixel((x-x0+xx,y-y0+yy),cols[pb+v] if pb+v<len(cols) else (255,255,255))
    return im
