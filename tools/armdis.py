import capstone,sys
md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB)
mda=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_ARM)
def dis(d,base,a,b,arm=False):
    off=a
    m=mda if arm else md; st=4 if arm else 2
    while off<b:
        got=False
        for ins in m.disasm(d[off-base:off-base+4],off,1):
            print('%08x %-8s %s'%(ins.address,ins.mnemonic,ins.op_str)); off+=ins.size; got=True
        if not got: print('%08x .word %04x'%(off,int.from_bytes(d[off-base:off-base+st],'little'))); off+=st
if __name__=='__main__':
    f,a,b=sys.argv[1],int(sys.argv[2],16),int(sys.argv[3],16)
    arm=len(sys.argv)>4
    dis(open(f,'rb').read(),0x2000000,a,b,arm)
