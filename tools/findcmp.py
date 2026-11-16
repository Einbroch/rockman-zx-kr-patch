"""ARM9 이미지에서 0xF0대 비교가 몰린 Thumb 코드 구역 찾기: findcmp.py arm9.bin [base]"""
import capstone,collections,re,sys
d=open(sys.argv[1],'rb').read(); base=int(sys.argv[2],16) if len(sys.argv)>2 else 0x2000000
md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB)
res=collections.defaultdict(set)
for off in range(0,len(d)-2,2):
    for ins in md.disasm(d[off:off+2],base+off,1):
        if ins.mnemonic=='cmp' and re.search(r'#0x(f[0-9a-f])$',ins.op_str):
            res[(base+off)//0x100].add(int(ins.op_str.split('#')[1],16))
for k,v in sorted(res.items()):
    if len(v)>=4: print(hex(k*0x100),sorted(hex(x) for x in v))
