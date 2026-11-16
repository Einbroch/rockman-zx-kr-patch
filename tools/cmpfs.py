import ndspy.rom, hashlib, sys
def files(p):
    r=ndspy.rom.NintendoDSRom.fromFile(p)
    out={}
    for i,f in enumerate(r.files):
        n=r.filenames.filenameOf(i)
        out[n or f'#{i}']=f
    return r,out
a,fa=files(sys.argv[1]); b,fb=files(sys.argv[2])
print('arm9',len(a.arm9),len(b.arm9),a.arm9==b.arm9,'arm7',a.arm7==b.arm7)
print('ovl9',len(a.arm9OverlayTable),len(b.arm9OverlayTable))
print('nfiles',len(fa),len(fb))
from collections import Counter
same=0;ch=[];
for n in fa:
    if n not in fb: print('only J',n); continue
    if fa[n]==fb[n]: same+=1
    else: ch.append((n,len(fa[n]),len(fb[n])))
for n in fb:
    if n not in fa: print('only K',n,len(fb[n]))
print('same',same,'changed',len(ch))
for c in ch: print(c)
