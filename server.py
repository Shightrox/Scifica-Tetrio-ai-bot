"""Local-only static app server. No third-party packages, uploads or keyboard injection."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import argparse
import functools
import threading
import webbrowser
import urllib.request
import sys
import subprocess
import json

ROOT = Path(__file__).resolve().parent
OVERLAY_LOCK = threading.Lock()
OVERLAY_PROCESS = None

class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        global OVERLAY_PROCESS
        expected = f'http://127.0.0.1:{self.server.server_port}'
        if (self.path != '/launch-overlay' or self.headers.get('Origin') != expected
                or self.headers.get('X-Tetris-Lab') != 'launch-overlay'
                or self.headers.get('Content-Type') != 'application/json'):
            self.send_error(403)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= 64:
                self.send_error(400)
                return
            self.rfile.read(length)
            with OVERLAY_LOCK:
                if OVERLAY_PROCESS is None or OVERLAY_PROCESS.poll() is not None:
                    python = Path(sys.executable).with_name('pythonw.exe')
                    if not python.exists(): python = Path(sys.executable)
                    with open(ROOT / 'overlay.log', 'ab') as log:
                        OVERLAY_PROCESS = subprocess.Popen([str(python), str(ROOT / 'overlay.py')],
                            cwd=ROOT, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
            payload = json.dumps({'ok': True, 'pid': OVERLAY_PROCESS.pid}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (OSError, ValueError) as exc:
            self.send_error(500, str(exc))

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Tetris-Lab', 'local-prototype-1')
        super().end_headers()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    url = f'http://127.0.0.1:{args.port}'
    handler = functools.partial(Handler, directory=str(ROOT))
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    except OSError as exc:
        if not args.no_open:
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.headers.get('X-Tetris-Lab') == 'local-prototype-1':
                        webbrowser.open(url)
                        raise SystemExit(0)
            except (OSError, urllib.error.URLError):
                pass
        raise SystemExit(f'Cannot open port {args.port}: {exc}. Try --port 8766.')
    print(f'Scifica: {url}', flush=True)
    if not args.no_open:
        threading.Timer(.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
