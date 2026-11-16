"""번역 본문 문자열 치환(주석 줄 제외). kofix.py game 규칙.txt   규칙 줄: 파일접두사<TAB>옛<TAB>새"""
import sys,os,glob
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
game=sys.argv[1]; rules=[l.rstrip('\n').split('\t') for l in open(sys.argv[2],encoding='utf-8') if l.strip()]
for pre,old,new in rules:
    hit=0
    for p in glob.glob(f'{ROOT}/data/ko/{game}/{pre}*.txt'):
        L=open(p,encoding='utf-8').read().split('\n'); ch=False
        for i,l in enumerate(L):
            if not l.startswith(';') and old in l: L[i]=l.replace(old,new); hit+=1; ch=True
        if ch: open(p,'w',encoding='utf-8').write('\n'.join(L))
    print(hit, old, '->', new)
