"""12x16 1bpp 폰트(.bin, 헤더 0x20) 시트 렌더: fontsheet.py font.bin out.png [start] [count]"""
import sys,struct
from PIL import Image, ImageDraw
def glyph(b,c,base=0x20):
    g=b[base+c*32:base+c*32+32]
    return [[(g[2*y]|g[2*y+1]<<8)>>x&1 for x in range(16)] for y in range(16)]
if __name__=='__main__':
    b=open(sys.argv[1],'rb').read()
    st=int(sys.argv[3],0) if len(sys.argv)>3 else 0
    cnt=int(sys.argv[4],0) if len(sys.argv)>4 else (len(b)-0x20)//32-st
    S=2; rows=(cnt+31)//32
    img=Image.new('L',(48+32*18*S, rows*18*S),255); d=ImageDraw.Draw(img)
    for k in range(cnt):
        c=st+k; gl=glyph(b,c); x0=48+(k%32)*18*S; y0=(k//32)*18*S
        for y in range(16):
            for x in range(16):
                if gl[y][x]: d.rectangle([x0+x*S,y0+y*S,x0+x*S+S-1,y0+y*S+S-1],fill=0)
    for r in range(rows): d.text((2,r*18*S+12),'%03x'%(st+r*32),fill=0)
    img.save(sys.argv[2])
