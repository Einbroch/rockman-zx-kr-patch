"""부팅 → 새 게임 → A 연타로 첫 조작 지점까지 → START 서브 화면 캡처. to_sub.py 롬 이름 [연타프레임]"""
import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import emutest
from desmume.controls import Keys
rom,name=sys.argv[1],sys.argv[2]; N=int(sys.argv[3]) if len(sys.argv)>3 else 17000
e=emutest.Emu(rom); e.e.reset(); e.run(600)
for _ in range(3): e.press(Keys.KEY_START,after=120)
e.press(Keys.KEY_A,after=180)
f=0
while f<N:
    e.press(Keys.KEY_A,hold=4,after=16); f+=20
e.run(120); e.shot(f'{name}00'); e.save(f'{name}_play')
e.press(Keys.KEY_START,after=150); e.shot(f'{name}01')
for k in ['RI','RI','D','D']:
    e.press(emutest.KEYS[k],after=40); e.shot(f'{name}{len(e.shots):02d}')
e.save(f'{name}_sub'); e.grid(name,cols=6)
sys.stdout.flush(); os._exit(0)
