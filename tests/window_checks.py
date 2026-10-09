"""Exercise real Tk/Win32 dragging; no input is sent to another application."""
import ctypes as C
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import overlay
from win_capture import W, hwnd, user


def run():
    with tempfile.TemporaryDirectory(prefix='scifica-window-') as directory:
        overlay.data_directory = lambda: Path(directory)
        app = overlay.Overlay()
        root = app.root
        chrome = app.window_chrome

        def pump(seconds=.05):
            until = time.perf_counter() + seconds
            while time.perf_counter() < until:
                root.update()
                time.sleep(.002)

        def bounds():
            rect = W.RECT()
            user.GetWindowRect(app.control_handle, C.byref(rect))
            return rect.left, rect.top, rect.right-rect.left, rect.bottom-rect.top

        def layout(widget):
            return (str(widget), widget.winfo_x(), widget.winfo_y(),
                    widget.winfo_width(), widget.winfo_height(),
                    tuple(layout(child) for child in widget.winfo_children()
                          if child.winfo_toplevel() == root))

        def contents():
            # Relative child geometry, not the top-level's screen position.
            return tuple(layout(child) for child in root.winfo_children()
                         if child.winfo_toplevel() == root)

        def pointer(x, y):
            return SimpleNamespace(x_root=x, y_root=y)

        try:
            pump(.2)
            user.SetWindowPos(app.control_handle, None, 40, 40, 0, 0, 0x15)
            pump()
            start = bounds()
            expected_layout = contents()
            assert root.overrideredirect()
            assert start[2:] == (root.winfo_width(), root.winfo_height())

            # Repeated press/motion/release, including far more input events
            # than a frame can display. Release must use the very last point.
            for n in range(40):
                left, top, width, height = bounds()
                chrome.begin_drag(pointer(left+40, top+15))
                for i in range(100):
                    chrome.drag(pointer(left+40+i, top+15+i))
                dx, dy = (17, 11) if n % 2 == 0 else (-17, -11)
                chrome.end_drag(pointer(left+40+dx, top+15+dy))
                pump(.01)
                assert bounds() == (left+dx, top+dy, width, height), bounds()
                assert contents() == expected_layout, 'child layout drifted during drag'
                assert chrome.job is None and chrome.pending is None
            assert bounds() == start

            # A negative x coordinate means a monitor to the left, not Tk's
            # geometry syntax for a distance from the right edge of a monitor.
            chrome.begin_drag(pointer(80, 55))
            chrome.end_drag(pointer(-20, 55))
            pump()
            assert bounds()[0] == -60, bounds()
            user.SetWindowPos(app.control_handle, None, 40, 40, 0, 0, 0x15)
            pump()

            # Exercise the actual title widget bindings as Tk dispatches them.
            shell = next(child for child in root.winfo_children() if child.winfo_class() == 'Frame')
            titlebar = shell.winfo_children()[0]
            titlebar.event_generate('<ButtonPress-1>', x=20, y=12, rootx=60, rooty=52)
            titlebar.event_generate('<B1-Motion>', x=30, y=22, rootx=70, rooty=62)
            titlebar.event_generate('<ButtonRelease-1>', x=30, y=22, rootx=70, rooty=62)
            pump()
            assert bounds() == (50, 50, *start[2:]), bounds()

            # Minimize/restore keeps the independent click-through layer alive.
            app.layer.deiconify()
            pump()
            for _ in range(3):
                chrome.minimize()
                pump()
                assert user.IsIconic(app.control_handle)
                assert user.IsWindowVisible(hwnd(app.layer))
                app.region = (50, 50, 200, 400)
                assert not app.panel_overlaps_capture()
                app.region = None
                app.show_controls()
                pump()
                assert not user.IsIconic(app.control_handle)
                assert bounds() == (50, 50, *start[2:])
                assert contents() == expected_layout
                style = user.GetWindowLongPtrW(app.control_handle, -16)
                extended = user.GetWindowLongPtrW(app.control_handle, -20)
                assert not style & 0x00c40000, 'native caption returned'
                assert extended & 0x40000 and not extended & 0x80, 'missing taskbar entry'
            app.layer.withdraw()

            # Root withdraw/show is used by selection and capture calibration.
            root.withdraw()
            pump()
            app.show_controls()
            pump()
            assert bounds() == (50, 50, *start[2:])
            assert contents() == expected_layout
            # A strategy change must replan without disarming or forgetting a
            # hard drop whose acknowledgement has not arrived yet.
            app.player.tap = lambda key: (_ for _ in ()).throw(AssertionError('unexpected game input'))
            app.player.start(time.perf_counter())
            pending_drop = {'action': 'DROP'}
            app.player.waiting = pending_drop
            app.advice = {'old': True}
            revision = app.player.revision
            app.change_attack_priority()
            assert app.player.enabled and app.player.recovery
            assert app.player.waiting is pending_drop and app.player.revision > revision
            assert app.advice is None and app.live_state is None and app.job is None
            app.player.stop('Check finished')
            print('PASS 40 drag cycles / 4,000 queued positions, exact release, negative x,')
            print('     title bindings, stable child layout, minimize/restore and taskbar styles')
            print('PASS strategy change preserves pending DROP evidence and armed state while replanning')
        finally:
            app.close()
            for handler in list(app.events.handlers):
                handler.close()
                app.events.removeHandler(handler)


if __name__ == '__main__':
    run()
