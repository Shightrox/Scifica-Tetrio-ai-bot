import sys,time,ctypes as C
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import game_input as G
events=[]
def send(n,p,size):
 d=p._obj;events.append((d.type,d.u.ki.wScan,d.u.ki.dwFlags,size));return 1
assert C.sizeof(G.INPUT)==(40 if C.sizeof(C.c_void_p)==8 else 28)
with patch.object(G.user,'SendInput',send),patch.object(G.user,'GetForegroundWindow',lambda:7),patch.object(G.user,'GetAsyncKeyState',lambda k:0),patch.object(G,'title',lambda h:'TETR.IO — local test'):
 g=G.GameInput(lambda:7);assert g.tap(0x25);time.sleep(.035)
 assert len(events)==2 and events[0][2]==9 and events[1][2]==11
 assert not g.down
 assert g.tap(0x58);g.release();time.sleep(.025)
 assert len(events)==4 and events[2][2]==8 and events[3][2]==10
 assert g.tap(0x28);time.sleep(.035)
 assert len(events)==6 and events[4][2]==9 and events[5][2]==11
 with patch.object(G.user,'GetForegroundWindow',lambda:8):assert not g.tap(0x20)
 with patch.object(G,'title',lambda h:'Editor'):assert not g.tap(0x20)
 with patch.object(G.user,'GetAsyncKeyState',lambda k:0x8000):assert not g.tap(0x20)
 assert len(events)==6
print('PASS: native INPUT layout, scan-code taps/key-up, no stuck keys, focus/title/modifier guards (SendInput mocked; no real keys sent)')
