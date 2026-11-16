"""어드벤트 번역 원고 틀: data/ko/zxa/<파일>.txt. 있으면 건너뜀.
블록 '## 번호', ';JP' 원문 줄, 본문. 같은 원문이 앞에 나왔으면 ';= 파일 번호'.
ZX 와 원문이 똑같은 메시지는 ZX 번역을 본문에 미리 채우고 ';ZX' 표시를 단다(검토 대상)."""
import json, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_zx as bz
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
zxa = json.load(open(f'{ROOT}/data/zxa_jp.json', encoding='utf-8'))
zx = json.load(open(f'{ROOT}/data/zx_jp.json', encoding='utf-8'))
trz = bz.load_translations('zx', zx)
zxmap = {}
for f, v in zx.items():
    for i, m in enumerate(v['msgs']):
        t = trz.get((f[:-4], i))
        if t is not None and m['s']: zxmap.setdefault(m['s'], t)
od = f'{ROOT}/data/ko/zxa'; os.makedirs(od, exist_ok=True)
seen = {}; n = nz = 0
for f, v in zxa.items():
    p = f'{od}/{f[:-4]}.txt'
    if os.path.exists(p): continue
    out = []
    for i, m in enumerate(v['msgs']):
        if not m['s']: continue
        out.append(f'## {i}')
        if m['s'] in seen: out += [';= %s %d' % seen[m['s']], '']; continue
        seen[m['s']] = (f[:-4], i); n += 1
        out += [';JP ' + l for l in m['s'].split('\n')]
        if m['s'] in zxmap: out += [';ZX', zxmap[m['s']]]; nz += 1
        elif not re.search(r'[ぁ-んァ-ヶ一-龯]', m['s']): out.append(m['s'])     # 일본어 없는 메시지는 그대로
        out.append('')
    open(p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print('고유 메시지', n, 'ZX 번역 재사용', nz)
