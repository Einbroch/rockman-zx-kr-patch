"""메인 RAM 사용 분포: 롬을 처음부터 A/START 로 진행하며 주기적으로 RAM 을 떠 '한 번이라도 0 아니었던' 바이트를 누적.
사용: ramscan.py 롬 프레임수 [상태]  -> work/ramscan_used.bin (4MiB 비트맵 대신 바이트 플래그)"""
import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import emutest
from desmume.controls import Keys
rom=sys.argv[1]; total=int(sys.argv[2]); state=sys.argv[3] if len(sys.argv)>3 else None
emu=emutest.Emu(rom,state)
if not state: emu.e.reset()
used=bytearray(0x400000)
def snap():
    m=bytes(emu.e.memory.unsigned[0x2000000:0x2400000])
    for i in range(0,0x400000,4096):
        blk=m[i:i+4096]
        if any(blk):
            u=used
            for j,v in enumerate(blk):
                if v: u[i+j]=1
f=0; k=0
keys=[Keys.KEY_START,Keys.KEY_A,Keys.KEY_A,Keys.KEY_A]
while f<total:
    emu.run(120); f+=120
    emu.press(keys[k%len(keys)],after=10); f+=16; k+=1
    if k%5==0: snap()
snap()
open('work/ramscan_used.bin','wb').write(used)
emu.save('ramscan_end'); emu.shot('ramscan_end')
lo=0x199fc0
last=max(i for i in range(len(used)) if used[i])
print('highest used',hex(0x2000000+last))
for a in range(lo&~0xffff,0x400000,0x10000):
    n=sum(used[a:a+0x10000]); print(hex(0x2000000+a),'%5.1f%%'%(n*100/0x10000))
emu.e.lib.desmume_free() if hasattr(emu.e,'lib') else None
sys.stdout.flush(); os._exit(0)
