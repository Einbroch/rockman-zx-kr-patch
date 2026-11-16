"""번역 원고 틀 생성: data/ko/<game>/<파일>.txt. 이미 있으면 건너뜀.
블록: '## 번호', ';JP ' 원문 줄, ';KR ' 참고 줄, 그 아래 빈 본문. 같은 원문이 앞에 나왔으면 ';= 파일 번호' 만 적는다."""
import json,os,sys,re
sys.stdout.reconfigure(encoding='utf-8')
game=sys.argv[1]; ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
jp=json.load(open(f'{ROOT}/data/{game}_jp.json',encoding='utf-8'))
kp=f'{ROOT}/work/{game}_ref.json'; k=json.load(open(kp,encoding='utf-8')) if os.path.exists(kp) else {}
od=f'{ROOT}/data/ko/{game}'; os.makedirs(od,exist_ok=True)
seen={}; n=0
for f,v in jp.items():
    p=f'{od}/{f[:-4]}.txt'
    if os.path.exists(p): continue
    out=[]; kk=k.get(f,[])
    for i,m in enumerate(v['msgs']):
        if not m['s']: continue
        out.append(f'## {i}')
        if m['s'] in seen: out.append(';= %s %d'%seen[m['s']]); out.append(''); continue
        seen[m['s']]=(f[:-4],i); n+=1
        out += [';JP '+l for l in m['s'].split('\n')]
        if i<len(kk): out += [';KR '+l for l in kk[i].split('\n')]
        out.append('')
    open(p,'w',encoding='utf-8').write('\n'.join(out)+'\n')
print(game,'고유 메시지',n)
