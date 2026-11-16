"""번역문 줄 폭 점검: 원문 최장 줄(12px/자) 또는 지정 한도를 넘는 줄 출력. widthcheck.py zx [접두사] [한도px]"""
import sys,os,json,re
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import build_zx as b
game=sys.argv[1]; pre=sys.argv[2] if len(sys.argv)>2 else ''; cap=int(sys.argv[3]) if len(sys.argv)>3 else 0
jp=json.load(open(f'{b.ROOT}/data/{game}_jp.json',encoding='utf-8'))
tr=b.load_translations(game,jp)
n=0
for (name,i),t in sorted(tr.items()):
    if not name.startswith(pre): continue
    src=jp[name+'.bin']['msgs'][i]['s']
    lim=cap or b.width_limit(name,src)
    for ln,w in zip(t.replace('{p}\n','\n').split('\n'),b.line_widths(t)):
        if w>lim: n+=1; print(name,i,w,lim,re.sub(r'\{[^}]*\}','',ln))
print('초과',n)
