"""시각 PoC: 오프닝 첫 메시지 1~2쪽을 한국어로. 한글 글리프는 덜 쓰인 가나 칸에 임시로 덮는다(훅 없음, 배포 금지)."""
import sys,os,json,collections,struct
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import ndspy.rom, zxtext, kfont12
rom=ndspy.rom.NintendoDSRom.fromFile('Rockman ZX (J).nds')
cm=zxtext.prep(zxtext.load_charmap('zx'),False)
jp=json.load(open('data/zx_jp.json',encoding='utf-8'))
# 가나 사용 빈도
freq=collections.Counter()
for f,v in jp.items():
    for m in v['msgs']:
        for ch in m['s']: freq[ch]+=1
kana=[c for c in range(0x40,0xE5)]
kana.sort(key=lambda c: freq[cm[c]])
P1='{F2:02}{F9:e903}{F3:0d}{F8:03}네, 네!\n의뢰만 있다면\n무엇이든 어디로든!{p}\n'
P2='{F2:02}{F9:ea03}{F3:0d}{F8:03}여기는 「운반책」\n지르웨 익스프레스\n입니다!{p}\n'
name='talk_m01_jp1.bin'
m0=jp[name]['msgs'][0]['s']
pages=m0.split('{p}\n')
new=P1+P2+'{p}\n'.join(pages[2:])
syl=sorted({ch for ch in P1+P2 if '가'<=ch<='힣'})
assert len(syl)<=len(kana)
slot={ch:kana[i] for i,ch in enumerate(syl)}
print('syllables',len(syl),'slots',[cm[s] for s in slot.values()])
# 인코딩: 한글은 칸 번호, 나머지는 원본 문자표
for ch,c in slot.items(): cm['_uniq'][ch]=c
cm['_uniq'][' ']=0; cm['_uniq'][',']=0xF0  # 、
cm['_uniq']['!']=cm['_uniq']['！']
raw=zxtext.encode_jp(new,cm)
# 파일 재조립 (모든 메시지 원본 바이트 유지, 첫 메시지만 교체)
fid=rom.filenames.idOf(name); b=rom.files[fid]
A,base,offs=zxtext.parse(b)
old_end=base+jp[name]['msgs'][1]['off']
delta=len(raw)+1-(old_end-base)
body=raw+bytes([0xFE])+b[old_end:A+4]
newoffs=[0]+[o+delta for o in offs[1:]]
B=len(offs)*2
out=struct.pack('<HH',B+len(body),B)+struct.pack('<%dH'%len(offs),*newoffs)+body
assert struct.unpack_from('<H',out)[0]+4==len(out)
rom.files[fid]=out
# 폰트
ffid=rom.filenames.idOf('font_jp.bin'); F=bytearray(rom.files[ffid])
for ch,c in slot.items(): F[0x20+c*32:0x20+c*32+32]=kfont12.glyph(ch)
rom.files[ffid]=bytes(F)
os.makedirs('out',exist_ok=True); rom.saveToFile('out/zx_poc.nds'); print('ok',len(out),len(b))
