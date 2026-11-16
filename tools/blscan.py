"""Thumb BL/BLX 호출자 찾기(ARM9+전 오버레이). blscan.py 롬 대상주소(hex)..."""
import sys,struct,ndspy.rom,ndspy.codeCompression as cc
r=ndspy.rom.NintendoDSRom.fromFile(sys.argv[1])
imgs=[('arm9',0x2000000,cc.decompress(r.arm9))]+[('ov%d'%k,o.ramAddress,bytes(o.data)) for k,o in sorted(r.loadArm9Overlays().items())]
T={int(x,16) for x in sys.argv[2:]}
for name,base,d in imgs:
    for i in range(0,len(d)-4,2):
        h1,h2=struct.unpack_from('<HH',d,i)
        if h1>>11==0b11110 and (h2>>11) in (0b11111,0b11101):
            off=((h1&0x7ff)<<12)|((h2&0x7ff)<<1)
            if off&0x400000: off-=0x800000
            tgt=base+i+4+off
            if h2>>11==0b11101: tgt&=~3
            if tgt in T: print(name,hex(base+i),'->',hex(tgt),'blx' if h2>>11==0b11101 else 'bl')
    # ARM BL
    for i in range(0,len(d)-4,4):
        w=struct.unpack_from('<I',d,i)[0]
        if (w>>24)&0xF in (0xB,) and (w>>28) in (0xE,):
            off=w&0xffffff
            if off&0x800000: off-=0x1000000
            tgt=base+i+8+off*4
            if tgt in T: print(name,hex(base+i),'->',hex(tgt),'ARM bl')
        if (w>>25)==0b1111101:
            off=w&0xffffff
            if off&0x800000: off-=0x1000000
            tgt=base+i+8+off*4+((w>>24)&1)*2
            if tgt|1 in T or tgt in T: print(name,hex(base+i),'->',hex(tgt),'ARM blx')
