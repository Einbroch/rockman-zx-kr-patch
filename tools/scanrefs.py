"""ARM9·전 오버레이에서 리터럴(주소) 참조와 0xF0대 비교 군집을 센다. scanrefs.py 롬 주소...(hex)"""
import sys,struct,ndspy.rom,ndspy.codeCompression as cc,capstone,re,collections
r=ndspy.rom.NintendoDSRom.fromFile(sys.argv[1])
imgs=[('arm9',0x2000000,cc.decompress(r.arm9))]
for k,o in sorted(r.loadArm9Overlays().items()): imgs.append(('ov%d'%k,o.ramAddress,bytes(o.data)))
targets=[int(x,16) for x in sys.argv[2:]]
md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB)
for name,base,d in imgs:
    for t in targets:
        p=struct.pack('<I',t); i=d.find(p)
        while i>=0:
            if i%4==0: print(name,'ref',hex(t),'at',hex(base+i))
            i=d.find(p,i+1)
    if name=='arm9': continue
    res=collections.defaultdict(set)
    for off in range(0,len(d)-2,2):
        for ins in md.disasm(d[off:off+2],base+off,1):
            if ins.mnemonic=='cmp' and re.search(r'#0x(f[0-9a-f])$',ins.op_str):
                res[(base+off)//0x100].add(int(ins.op_str.split('#')[1],16))
    for k,v in sorted(res.items()):
        if len(v)>=3: print(name,'cmp cluster',hex(k*0x100),sorted(hex(x) for x in v))
