"""어드벤트 원고에서 줄 폭 초과 줄을 찾아 보여 준다(build_zx 의 폭 규칙을 그대로 import)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_zx as bz
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
jp = json.load(open(f'{ROOT}/data/zxa_jp.json', encoding='utf-8'))
tr = bz.load_translations('zxa', jp)
for (name, i), t in sorted(tr.items()):
    src = jp[name + '.bin']['msgs'][i]['s']
    lim = bz.width_limit(name, src)
    for ln in t.replace('{p}\n', '\n').split('\n'):
        w = bz.line_widths(ln)[0]
        if w > lim: print(name, i, w, lim, ln)
