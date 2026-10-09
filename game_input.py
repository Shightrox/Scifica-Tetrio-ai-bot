"""Focus-guarded key taps and a renewable, watchdog-limited Down hold."""
import ctypes as C
from ctypes import wintypes as W
import threading
import time
from win_capture import user,title

class KEYBDINPUT(C.Structure):
    _fields_=[('wVk',W.WORD),('wScan',W.WORD),('dwFlags',W.DWORD),('time',W.DWORD),('dwExtraInfo',C.c_size_t)]
class MOUSEINPUT(C.Structure):
    _fields_=[('dx',W.LONG),('dy',W.LONG),('mouseData',W.DWORD),('dwFlags',W.DWORD),('time',W.DWORD),('dwExtraInfo',C.c_size_t)]
class UNION(C.Union):_fields_=[('ki',KEYBDINPUT),('mi',MOUSEINPUT)]
class INPUT(C.Structure):_fields_=[('type',W.DWORD),('u',UNION)]
user.SendInput.argtypes=[W.UINT,C.POINTER(INPUT),C.c_int];user.SendInput.restype=W.UINT
user.MapVirtualKeyW.argtypes=[W.UINT,W.UINT];user.MapVirtualKeyW.restype=W.UINT
user.GetAsyncKeyState.argtypes=[C.c_int];user.GetAsyncKeyState.restype=C.c_short
user.SetForegroundWindow.argtypes=[C.c_void_p]

class GameInput:
    def __init__(self,target):
        self.target=target;self.down=set();self.lock=threading.Lock()
        self.serial=0;self.descent_until=0;self.descent_target=None
    def event(self,vk,up=False):
        scan=user.MapVirtualKeyW(vk,0)
        flags=8|(1 if vk in (0x25,0x27,0x28) else 0)|(2 if up else 0)
        data=INPUT(type=1,u=UNION(ki=KEYBDINPUT(0,scan,flags,0,0)))
        return user.SendInput(1,C.byref(data),C.sizeof(INPUT))==1
    def allowed_target(self):
        target=self.target()
        if not target or user.GetForegroundWindow()!=target or 'TETR.IO' not in title(target).upper():return None
        if any(user.GetAsyncKeyState(k)&0x8000 for k in (0x10,0x11,0x12,0x5b,0x5c)):return None
        return target
    def tap(self,vk):
        if not self.allowed_target():return False
        with self.lock:
            if self.down:return False
            if not self.event(vk):return False
            self.down.add(vk);self.serial+=1;serial=self.serial
        def finish():
            time.sleep(.012)
            with self.lock:
                if serial==self.serial and vk in self.down:self.event(vk,True);self.down.discard(vk)
        threading.Thread(target=finish,daemon=True).start()
        return True
    def hold_down(self):
        """Called once per verified descent frame, not a timed blind macro."""
        target=self.allowed_target()
        if not target:
            self.release();return False
        with self.lock:
            if self.down=={0x28} and self.descent_target==target:
                self.descent_until=time.monotonic()+.12;return True
            if self.down:return False
            if not self.event(0x28):return False
            self.down.add(0x28);self.serial+=1;serial=self.serial
            self.descent_target=target;self.descent_until=time.monotonic()+.12
        def watchdog():
            while True:
                time.sleep(.008)
                with self.lock:
                    if serial!=self.serial or 0x28 not in self.down:return
                    if time.monotonic()>=self.descent_until or self.allowed_target()!=target:
                        self._release_locked();return
        threading.Thread(target=watchdog,daemon=True).start()
        return True
    def _release_locked(self):
        for vk in self.down:self.event(vk,True)
        self.down.clear();self.serial+=1
        self.descent_target=None;self.descent_until=0
    def release(self):
        with self.lock:
            self._release_locked()
