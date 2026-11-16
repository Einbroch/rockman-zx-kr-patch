"""4bpp 타일 바이트 -> 회색조 시트(타일 8x8, 가로 cols 타일). tilesheet(data, cols) -> PIL.Image"""
from PIL import Image
def sheet(data,cols=32,scale=2):
    nt=len(data)//32; rows=(nt+cols-1)//cols
    im=Image.new('L',(cols*8,rows*8),0)
    px=im.load()
    for t in range(nt):
        tx,ty=(t%cols)*8,(t//cols)*8
        for y in range(8):
            for x in range(8):
                b=data[t*32+y*4+x//2]; v=(b>>((x&1)*4))&15
                px[tx+x,ty+y]=v*17
    return im.resize((im.width*scale,im.height*scale),Image.NEAREST)
def sheet8(data,cols=32,scale=1,pal=None):
    nt=len(data)//64; rows=(nt+cols-1)//cols
    im=Image.new('RGB',(cols*8,rows*8),(0,0,0)); px=im.load()
    for t in range(nt):
        tx,ty=(t%cols)*8,(t//cols)*8
        for y in range(8):
            for x in range(8):
                v=data[t*64+y*8+x]
                px[tx+x,ty+y]=pal[v] if pal else (v,v,v)
    return im.resize((im.width*scale,im.height*scale),Image.NEAREST)
