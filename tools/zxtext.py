"""록맨 ZX/ZXA 대사 파일(talk_*, m_*) 파서.
형식: u16 A, u16 B, u16 off[B/2], 본문(base=4+B). 메시지는 FE 로 끝, 파일은 FF 로 끝.
제어 인수(ARM9 0x2007976 출력기·0x2011f98 앞머리 해석기에서 확정):
  F0 xx = 글리프 0xF0+xx, F1~F8 = 1바이트 인수, F9 = 2바이트, FA/FB/FC = 0, FD = 쪽 넘김, FE = 메시지 끝, FF = 파일 끝."""
import struct
ARGN={0xF0:1,0xF1:1,0xF2:1,0xF3:1,0xF4:1,0xF5:1,0xF6:1,0xF7:1,0xF8:1,0xF9:2,0xFA:0,0xFB:0,0xFC:0,0xFD:0,0xFE:0,0xFF:0}

def parse(b):
    A,B=struct.unpack_from('<HH',b)
    n=B//2
    offs=list(struct.unpack_from('<%dH'%n,b,4))
    base=4+B
    return A,base,offs

def tokens(b,i,stop=(0xFE,0xFF)):
    """i 부터 FE/FF 까지 토큰 [(kind,val,raw)]"""
    out=[]
    while i<len(b):
        c=b[i]
        if c<0xF0: out.append(('g',c,b[i:i+1])); i+=1; continue
        if c==0xF0: out.append(('g',0xF0+b[i+1],b[i:i+2])); i+=2; continue
        k=ARGN[c]; out.append(('c',c,b[i:i+1+k])); i+=1+k
        if c in stop: break
    return out,i

# ---- 문자표·문자열 표기 ----
import re,os
DATA=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','data')
def load_charmap(game):
    m={}
    for line in open(os.path.join(DATA,'%s_jp_charmap.txt'%game),encoding='utf-8'):
        line=line.rstrip('\n')
        if not line: continue
        k,v=line.split('=',1); m[int(k,16)]=v
    return m

def decode_msg(b,i,cm):
    """한 메시지(FE/FF 까지) → (문자열, 다음 i, 종료바이트). 글리프는 문자표, 없는/중복 글자는 {Jxxx}."""
    s=''
    while True:
        c=b[i]
        if c<0xF0:
            g=c; i+=1
        elif c==0xF0:
            g=0xF0; i+=1
            while b[i]==0xFF and cm.get('chain'): g+=0xFF; i+=1   # ZXA 사슬
            g+=b[i]; i+=1
        else:
            n=ARGN[c]; arg=b[i+1:i+1+n]; i+=1+n
            if c==0xFC: s+='\n'
            elif c==0xFD: s+='{p}\n'
            elif c in (0xFE,0xFF): return s,i,c
            else: s+='{%02X%s}'%(c,(':'+arg.hex()) if n else '')
            continue
        ch=cm.get(g)
        s+= ch if ch is not None and cm['_uniq'].get(ch)==g else '{J%03X}'%g
    
def prep(cm,chain):
    u={}
    for k,v in cm.items():
        if isinstance(k,int): u.setdefault(v,k)
    cm['_uniq']=u; cm['chain']=chain; return cm

def encode_jp(s,cm):
    """decode_msg 의 역(왕복 검사용). 종료 바이트는 붙이지 않는다."""
    out=bytearray(); i=0
    while i<len(s):
        if s.startswith('{p}\n',i): out.append(0xFD); i+=4; continue
        if s[i]=='\n': out.append(0xFC); i+=1; continue
        m=re.match(r'\{J([0-9A-F]{3})\}',s[i:])
        if m: g=int(m.group(1),16); i+=m.end()
        else:
            m=re.match(r'\{([0-9A-F]{2})(?::([0-9a-f]+))?\}',s[i:])
            if m:
                out.append(int(m.group(1),16)); out+=bytes.fromhex(m.group(2) or ''); i+=m.end(); continue
            g=cm['_uniq'][s[i]]; i+=1
        if g<0xF0: out.append(g)
        else:
            out.append(0xF0); g-=0xF0
            while g>=0xFF: out.append(0xFF); g-=0xFF
            out.append(g)
    return bytes(out)
