"""상태에서 A 연타로 진행하며 주기적으로 캡처: emuhammer.py 롬 상태 이름 프레임 [캡처간격]"""
import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import emutest
from desmume.controls import Keys
rom,state,name,total=sys.argv[1],sys.argv[2],sys.argv[3],int(sys.argv[4]); step=int(sys.argv[5]) if len(sys.argv)>5 else 300
e=emutest.Emu(rom,state); f=0
while f<total:
    e.press(Keys.KEY_A,hold=4,after=16); f+=20
    if f%step==0: e.shot(f'{name}{f//step:02d}')
e.save(f'{name}_end'); e.grid(name)
emutest.shutdown() if hasattr(emutest,'shutdown') else None
sys.stdout.flush(); os._exit(0)
