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
 assert g.tap(0x41);time.sleep(.035)
 assert len(events)==8 and events[6][1]==G.user.MapVirtualKeyW(0x41,0) and events[6][2]==8 and events[7][2]==10
 with patch.object(G.user,'GetForegroundWindow',lambda:8):assert not g.tap(0x20)
 with patch.object(G,'title',lambda h:'Editor'):assert not g.tap(0x20)
 with patch.object(G.user,'GetAsyncKeyState',lambda k:0x8000):assert not g.tap(0x20)
 assert len(events)==8
 # Continuous Down has one keydown, renewed by fresh frames. Watchdog expiry
 # and focus/modifier changes release it even if the controller stops ticking.
 def await_release():
  deadline=time.monotonic()+.5
  while g.down and time.monotonic()<deadline:time.sleep(.005)
  assert not g.down,'watchdog left a key held'
 events.clear();assert g.hold_down()
 for _ in range(5):
  time.sleep(.04);assert g.hold_down()
 assert len(events)==1 and g.down=={0x28}
 assert not g.tap(0x58),'rotation cannot race with held Down'
 g.release();time.sleep(.025)
 assert len(events)==2 and events[0][2]==9 and events[1][2]==11
 events.clear();assert g.hold_down();await_release();assert len(events)==2
 for guard in ('focus','modifier','title','target'):
  events.clear();assert g.hold_down()
  obj,name,replacement={
   'focus':(G.user,'GetForegroundWindow',lambda:8),
   'modifier':(G.user,'GetAsyncKeyState',lambda k:0x8000),
   'title':(G,'title',lambda h:'Editor'),
   'target':(g,'target',lambda:8),
  }[guard]
  with patch.object(obj,name,replacement):await_release()
  assert len(events)==2,guard
 # An old tap's release thread must not release a newer Down lease.
 events.clear();assert g.tap(0x28);g.release();assert g.hold_down();time.sleep(.04)
 assert g.down=={0x28} and len(events)==3
 g.release();assert len(events)==4
 with patch.object(G.user,'SendInput',lambda *a:0):
  assert not g.hold_down() and not g.tap(0x20) and not g.down
print('PASS: native INPUT layout, scan-code taps/key-up, no stuck keys, focus/title/modifier guards (SendInput mocked; no real keys sent)')
print('PASS: held Down renewal, independent expiry/focus/modifier release, old-worker isolation and failed input')
