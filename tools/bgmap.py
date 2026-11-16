"""sub.bin 류 BG: 8bpp 타일 + 32x32 맵(u16: 타일 10비트, H플립 bit10, V플립 bit11) 조립."""
from PIL import Image
import struct
def tile8(tiles,t):
    return [tiles[t*64+y*8:t*64+y*8+8] for y in range(8)]
def render(tiles,mapdata,w=32,h=32,pal=None):
    im=Image.new('RGB',(w*8,h*8)); px=im.load(); nt=len(tiles)//64
    for cy in range(h):
        for cx in range(w):
            v=struct.unpack_from('<H',mapdata,2*(cy*w+cx))[0]
            t=v&0x3ff; hf=v>>10&1; vf=v>>11&1
            if t>=nt: continue
            rows=tile8(tiles,t)
            for y in range(8):
                for x in range(8):
                    c=rows[7-y if vf else y][7-x if hf else x]
                    px[cx*8+x,cy*8+y]=pal[c] if pal else (c,c,c)
    return im
