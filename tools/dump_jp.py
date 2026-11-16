"""일본판 대사·메뉴 파일 → data/<game>_jp.json  {파일: [{"s":문자열,"end":"FE"|"FF"}...]}, 왕복 검사 포함.
사용: python tools/dump_jp.py zx|zxa"""
import sys,os,glob,json
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import zxtext
game=sys.argv[1]; src='work/%s_j'%game
cm=zxtext.prep(zxtext.load_charmap(game),chain=(game=='zxa'))
out={}; bad=0; n=0
files=sorted(set(glob.glob(src+'/talk_*.bin')+glob.glob(src+'/m_*.bin')))
for f in files:
    b=open(f,'rb').read(); A,base,offs=zxtext.parse(b)
    end=A+4; i=base; msgs=[]
    while i<end:
        s0=i; s,i,term=zxtext.decode_msg(b,i,cm)
        raw=b[s0:i-1]
        if zxtext.encode_jp(s,cm)!=raw: bad+=1; print('roundtrip fail',f,hex(s0))
        msgs.append({'off':s0-base,'s':s,'end':'%02X'%term}); n+=1
    assert i==end, (f,hex(i),hex(end))
    out[os.path.basename(f)]={'A':A,'offs':offs,'msgs':msgs}
json.dump(out,open('data/%s_jp.json'%game,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(game,'files',len(out),'msgs',n,'roundtrip fail',bad)
