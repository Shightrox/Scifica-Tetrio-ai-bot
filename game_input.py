"""Short, focus-guarded physical-key taps. No global hold or blind macro."""
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
    def __init__(self,target):self.target=target;self.down=set();self.lock=threading.Lock()
    def event(self,vk,up=False):
        scan=user.MapVirtualKeyW(vk,0)
        flags=8|(1 if vk in (0x25,0x27,0x28) else 0)|(2 if up else 0)
        data=INPUT(type=1,u=UNION(ki=KEYBDINPUT(0,scan,flags,0,0)))
        return user.SendInput(1,C.byref(data),C.sizeof(INPUT))==1
    def tap(self,vk):
        target=self.target()
        if not target or user.GetForegroundWindow()!=target or 'TETR.IO' not in title(target).upper():return False
        if any(user.GetAsyncKeyState(k)&0x8000 for k in (0x10,0x11,0x12,0x5b,0x5c)):return False
        with self.lock:
            if self.down:return False
            if not self.event(vk):return False
            self.down.add(vk)
        def finish():
            time.sleep(.012)
            with self.lock:
                if vk in self.down:self.event(vk,True);self.down.discard(vk)
        threading.Thread(target=finish,daemon=True).start()
        return True
    def release(self):
        with self.lock:
            for vk in self.down:self.event(vk,True)
            self.down.clear()
