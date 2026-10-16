from __future__ import annotations

import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _Handler(SimpleHTTPRequestHandler):
    cache_root = Path('.')

    def do_GET(self):
        # /tiles/<provider>/<z>/<x>/<y>.png
        if self.path.startswith('/tiles/'):
            rel = self.path[len('/tiles/'):].split('?', 1)[0]
            target = (self.cache_root / rel).resolve()
            root = self.cache_root.resolve()
            if target.is_file() and str(target).startswith(str(root)):
                data = target.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                # QWebEngine loads map.html from file:// while cached tiles are
                # served by this local HTTP server. Explicit CORS is required
                # for the dedicated Map tab (and any second map instance).
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', '*')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'public, max-age=86400')
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_response(404)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.end_headers()
            return
        self.send_response(404)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def log_message(self, *args):
        return


class LocalTileServer:
    def __init__(self, root: Path, host='127.0.0.1', port=0):
        self.root = Path(root)
        self.host = host
        self.server = ThreadingHTTPServer((host, port), _Handler)
        _Handler.cache_root = self.root
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        return f'http://{self.host}:{self.port}'

    def close(self):
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
