"""Borderless Tk panel with native, size-preserving Windows movement."""
import ctypes as C
from ctypes import wintypes as W

from win_capture import hwnd, user

user.ShowWindow.argtypes = [C.c_void_p, C.c_int]


class WindowChrome:
    def __init__(self, root):
        self.root = root
        # Let Tk calculate a borderless client area itself. Intercepting
        # WM_NCCALCSIZE left Tk's decorated-frame dimensions out of sync.
        root.overrideredirect(True)
        self.origin = None
        self.pending = None
        self.job = None

    def configure(self):
        handle = hwnd(self.root)
        style = user.GetWindowLongPtrW(handle, -16)
        # Keep native minimize/taskbar restore, but no non-client frame.
        user.SetWindowLongPtrW(handle, -16, (style & ~0x00c40000) | 0x000a0000)
        extended = user.GetWindowLongPtrW(handle, -20)
        user.SetWindowLongPtrW(handle, -20, (extended | 0x00040000) & ~0x80)
        user.SetWindowPos(handle, None, 0, 0, 0, 0, 0x37)

    def bind(self, *widgets):
        for widget in widgets:
            widget.bind('<ButtonPress-1>', self.begin_drag)
            widget.bind('<B1-Motion>', self.drag)
            widget.bind('<ButtonRelease-1>', self.end_drag)

    def begin_drag(self, event):
        self.cancel_drag()
        rect = W.RECT()
        user.GetWindowRect(hwnd(self.root), C.byref(rect))
        self.origin = (event.x_root, event.y_root, rect.left, rect.top)

    def drag(self, event):
        if self.origin is None:
            return
        x, y, left, top = self.origin
        self.pending = (left + event.x_root - x, top + event.y_root - y)
        # Consume the newest mouse position once per UI tick, never a backlog
        # of geometry requests. Native coordinates also support left monitors.
        if self.job is None:
            self.job = self.root.after(8, self._move)

    def _move(self):
        self.job = None
        if self.pending is not None:
            left, top = self.pending
            self.pending = None
            # SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE: movement only.
            user.SetWindowPos(hwnd(self.root), None, left, top, 0, 0, 0x15)

    def end_drag(self, event):
        if self.origin is None:
            return
        self.drag(event)
        if self.job is not None:
            self.root.after_cancel(self.job)
        self._move()
        self.origin = None

    def cancel_drag(self):
        if self.job is not None:
            self.root.after_cancel(self.job)
        self.job = self.pending = self.origin = None

    def minimize(self):
        self.cancel_drag()
        user.ShowWindow(hwnd(self.root), 6)  # SW_MINIMIZE

    def restore(self):
        self.root.deiconify()
        handle = hwnd(self.root)
        if user.IsIconic(handle):
            user.ShowWindow(handle, 9)  # SW_RESTORE
        self.root.lift()
