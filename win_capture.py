"""Reusable DIB capture buffers; no screenshot encoding or disk writes."""
import ctypes as C
from ctypes import wintypes as W
import numpy as np

user=C.WinDLL('user32',use_last_error=True)
gdi=C.WinDLL('gdi32',use_last_error=True)
H=C.c_void_p
user.GetDC.argtypes=[H];user.GetDC.restype=H
user.ReleaseDC.argtypes=[H,H]
gdi.CreateCompatibleDC.argtypes=[H];gdi.CreateCompatibleDC.restype=H
gdi.CreateDIBSection.argtypes=[H,H,W.UINT,C.POINTER(H),H,W.DWORD];gdi.CreateDIBSection.restype=H
gdi.SelectObject.argtypes=[H,H];gdi.SelectObject.restype=H
gdi.DeleteObject.argtypes=[H];gdi.DeleteDC.argtypes=[H]
gdi.BitBlt.argtypes=[H,C.c_int,C.c_int,C.c_int,C.c_int,H,C.c_int,C.c_int,W.DWORD]
user.SetWindowDisplayAffinity.argtypes=[H,W.DWORD];user.SetWindowDisplayAffinity.restype=W.BOOL
user.GetAncestor.argtypes=[H,W.UINT];user.GetAncestor.restype=H
user.GetWindowLongPtrW.argtypes=[H,C.c_int];user.GetWindowLongPtrW.restype=C.c_ssize_t
user.SetWindowLongPtrW.argtypes=[H,C.c_int,C.c_ssize_t];user.SetWindowLongPtrW.restype=C.c_ssize_t
user.SetWindowPos.argtypes=[H,H,C.c_int,C.c_int,C.c_int,C.c_int,W.UINT]
user.GetForegroundWindow.restype=H
user.GetWindowTextW.argtypes=[H,W.LPWSTR,C.c_int]
user.WindowFromPoint.argtypes=[W.POINT];user.WindowFromPoint.restype=H
user.IsWindow.argtypes=[H];user.IsWindowVisible.argtypes=[H]
user.IsIconic.argtypes=[H]
user.GetWindowRect.argtypes=[H,C.POINTER(W.RECT)]
user.RegisterHotKey.argtypes=[H,C.c_int,W.UINT,W.UINT]
user.UnregisterHotKey.argtypes=[H,C.c_int]
user.PeekMessageW.argtypes=[C.POINTER(W.MSG),H,W.UINT,W.UINT,W.UINT]
user.CallWindowProcW.argtypes=[H,H,W.UINT,W.WPARAM,W.LPARAM];user.CallWindowProcW.restype=C.c_ssize_t

def dpi_aware():
    try:
        user.SetProcessDpiAwarenessContext.argtypes=[H]
        user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
    except (AttributeError,OSError):
        user.SetProcessDPIAware()

def virtual_screen():
    return tuple(user.GetSystemMetrics(i) for i in (76,77,78,79))


def monitor_work_areas():
    class MonitorInfo(C.Structure):
        _fields_=[('size',W.DWORD),('monitor',W.RECT),('work',W.RECT),('flags',W.DWORD)]
    areas=[]
    callback_type=C.WINFUNCTYPE(W.BOOL,H,H,C.POINTER(W.RECT),W.LPARAM)
    @callback_type
    def collect(monitor,dc,rect,data):
        info=MonitorInfo();info.size=C.sizeof(info)
        if user.GetMonitorInfoW(monitor,C.byref(info)):
            b=info.work;areas.append((b.left,b.top,b.right,b.bottom))
        return True
    user.GetMonitorInfoW.argtypes=[H,C.POINTER(MonitorInfo)]
    user.EnumDisplayMonitors.argtypes=[H,C.POINTER(W.RECT),callback_type,W.LPARAM]
    user.EnumDisplayMonitors(None,None,collect,0)
    return areas

def hwnd(window):
    window.update_idletasks()
    return user.GetAncestor(window.winfo_id(),2)

def exclude(window):
    return bool(user.SetWindowDisplayAffinity(hwnd(window),0x11))

def click_through(window):
    handle=hwnd(window)
    style=user.GetWindowLongPtrW(handle,-20)
    user.SetWindowLongPtrW(handle,-20,style|0x80000|0x20|0x08000000|0x80)

def title(handle):
    b=C.create_unicode_buffer(512);user.GetWindowTextW(handle,b,len(b));return b.value

class Capture:
    def __init__(self):
        self.screen=user.GetDC(None)
        self.dc=gdi.CreateCompatibleDC(self.screen)
        self.bitmap=None;self.previous=None;self.size=None;self.array=None
        if not self.screen or not self.dc: raise C.WinError(C.get_last_error())

    def grab(self,x,y,w,h):
        w,h=int(w),int(h)
        if w<1 or h<1: raise ValueError('Empty capture rectangle')
        if self.size!=(w,h):
            if self.bitmap:
                gdi.SelectObject(self.dc,self.previous);gdi.DeleteObject(self.bitmap)
            # BITMAPINFOHEADER: negative height gives top-down BGRA rows.
            header=C.create_string_buffer(40)
            import struct
            struct.pack_into('<IiiHHIIiiII',header,0,40,w,-h,1,32,0,w*h*4,0,0,0,0)
            bits=H()
            self.bitmap=gdi.CreateDIBSection(self.screen,header,0,C.byref(bits),None,0)
            if not self.bitmap: raise C.WinError(C.get_last_error())
            self.previous=gdi.SelectObject(self.dc,self.bitmap)
            self.array=np.ctypeslib.as_array((C.c_ubyte*(w*h*4)).from_address(bits.value)).reshape(h,w,4)
            self.size=(w,h)
        if not gdi.BitBlt(self.dc,0,0,w,h,self.screen,int(x),int(y),0x40CC0020):
            raise C.WinError(C.get_last_error())
        gdi.GdiFlush()
        return self.array[:,:,:3][:,:,::-1]

    def close(self):
        if self.bitmap:
            gdi.SelectObject(self.dc,self.previous);gdi.DeleteObject(self.bitmap);self.bitmap=None
        if self.dc:gdi.DeleteDC(self.dc);self.dc=None
        if self.screen:user.ReleaseDC(None,self.screen);self.screen=None
