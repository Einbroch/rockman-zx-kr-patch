"""일본판 대사·메뉴 파일 → data/<game>_jp.json  {파일: [{"s":문자열,"end":"FE"|"FF"}...]}, 왕복 검사 포함.
사용: python tools/dump_jp.py zx|zxa [출력 경로]
저장소 최상위의 일본판 롬(Rockman ZX (J).nds / Rockman ZX Advent (J).nds)에서 바로 읽는다."""
import sys,os,glob,json
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import zxtext
import ndspy.rom
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
game=sys.argv[1]
dst=sys.argv[2] if len(sys.argv)>2 else os.path.join(ROOT,'data','%s_jp.json'%game)
rom=ndspy.rom.NintendoDSRom.fromFile(os.path.join(ROOT,{'zx':'Rockman ZX (J).nds','zxa':'Rockman ZX Advent (J).nds'}[game]))
cm=zxtext.prep(zxtext.load_charmap(game),chain=(game=='zxa'))
out={}; bad=0; n=0
def walk(f,p=''):
    for nm in f.files: yield p+nm
    for nm,sub in f.folders: yield from walk(sub,p+nm+'/')
files=sorted(nm for nm in walk(rom.filenames) if '/' not in nm and nm.endswith('.bin') and nm.startswith(('talk_','m_')))
for f in files:
    b=rom.getFileByName(f); A,base,offs=zxtext.parse(b)
    end=A+4; i=base; msgs=[]
    while i<end:
        s0=i; s,i,term=zxtext.decode_msg(b,i,cm)
        raw=b[s0:i-1]
        if zxtext.encode_jp(s,cm)!=raw: bad+=1; print('roundtrip fail',f,hex(s0))
        msgs.append({'off':s0-base,'s':s,'end':'%02X'%term}); n+=1
    assert i==end, (f,hex(i),hex(end))
    out[os.path.basename(f)]={'A':A,'offs':offs,'msgs':msgs}
json.dump(out,open(dst,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(game,'files',len(out),'msgs',n,'roundtrip fail',bad)
