"""번역 작업 도구.
  kotool.py show <game> <파일이름(확장자 없이)> [시작 번호] [개수]
      미번역 고유 블록을 압축 표기로 출력: 쪽마다 한 줄, 줄바꿈은 '|', 쪽 앞머리 제어는 생략.
  kotool.py apply <game> <입력.txt>
      입력 형식: '@ 파일이름' 다음 '## 번호' 블록, 블록 안 한 줄 = 한 쪽('|' = 줄바꿈).
      쪽 수·본문 안 제어 표기가 원문과 같아야 한다. data/ko/<game>/<파일>.txt 의 해당 블록 본문을 채운다.
"""
import sys,os,re,json
sys.stdout.reconfigure(encoding='utf-8')
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEAD=re.compile(r'^((?:\{[^}]*\})*)')
def pages(s):
    out=[]
    for pg in s.split('{p}\n'):
        h=HEAD.match(pg).group(1); out.append((h,pg[len(h):]))
    return out
def inner(s): return re.findall(r'\{[^}]*\}',s)
def load(game): return json.load(open(f'{ROOT}/data/{game}_jp.json',encoding='utf-8'))
def blocks(path):
    t=open(path,encoding='utf-8').read()
    parts=re.split(r'^(## \d+.*)$',t,flags=re.M)
    return parts
def show(game,name,st=0,n=9999):
    jp=load(game)[name+'.bin']['msgs']
    t=open(f'{ROOT}/data/ko/{game}/{name}.txt',encoding='utf-8').read()
    for blk in re.split(r'^## ',t,flags=re.M)[1:]:
        head,_,body=blk.partition('\n'); i=int(head.split()[0])
        if i<st or not any(l.startswith(';JP ') for l in body.split('\n')): continue
        if any(l and not l.startswith(';') for l in body.split('\n')): continue
        n-=1
        if n<0: break
        print('## %d'%i)
        for h,b in pages(jp[i]['s']): print(b.replace('\n','|'))
def apply(game,inp):
    jpall=load(game); cur=None; data={}
    txt=open(inp,encoding='utf-8').read().replace('\r\n','\n')
    for line in txt.split('\n'):
        if line.startswith('@'): cur=line.lstrip('@').strip(); continue
        m=re.match(r'^## (\d+)\s*$',line)
        if m: idx=int(m.group(1)); data.setdefault(cur,{})[idx]=[]; continue
        if line.strip()=='' : continue
        data[cur][idx].append(line.rstrip())
    err=0; n=0
    for name,d in data.items():
        jp=jpall[name+'.bin']['msgs']; path=f'{ROOT}/data/ko/{game}/{name}.txt'
        t=open(path,encoding='utf-8').read()
        for idx,lines in d.items():
            if idx>=len(jp): print('번호 범위 밖',name,idx); err+=1; continue
            pg=pages(jp[idx]['s'])
            if len(lines)!=len(pg): print('쪽 수 불일치',name,idx,len(lines),len(pg)); err+=1; continue
            bad=[k for k,(l,(h,b)) in enumerate(zip(lines,pg)) if inner(l)!=inner(b)]
            if bad: print('제어 불일치',name,idx,bad); err+=1; continue
            msg='{p}\n'.join(h+l.replace('|','\n') for l,(h,b) in zip(lines,pg))
            # 블록 교체: 주석 줄은 두고 본문만
            pat=re.compile(r'(^## %d\n)((?:;[^\n]*\n)*)(.*?)(?=^## |\Z)'%idx,re.M|re.S)
            m=pat.search(t)
            if not m: print('블록 없음',name,idx); err+=1; continue
            t=t[:m.start()]+m.group(1)+m.group(2)+msg+'\n\n'+t[m.end():]
            n+=1
        open(path,'w',encoding='utf-8').write(t)
    print('적용',n,'오류',err)
if __name__=='__main__':
    c=sys.argv[1]
    if c=='show': show(sys.argv[2],sys.argv[3],*(int(x) for x in sys.argv[4:]))
    elif c=='apply': apply(sys.argv[2],sys.argv[3])
