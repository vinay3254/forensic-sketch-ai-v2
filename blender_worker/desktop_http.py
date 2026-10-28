"""Loopback transport; Blender's main-thread timer drains the request queue."""

import json
import queue
import threading
from concurrent.futures import Future, TimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class DesktopBridge:
    def __init__(self, render, port=8020, info=None):
        self.render = render
        self.info = info or {}
        self.jobs = queue.Queue(maxsize=8)
        self.pending = threading.Event()
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def reply(self, code, data, media="application/json"):
                self.send_response(code)
                self.send_header("Content-Type", media)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_GET(self):
                if self.path != "/health":
                    return self.reply(404, b'{"detail":"Not found"}')
                self.reply(200, json.dumps({**bridge.info, "status": "ok", "mode": "desktop"}).encode())

            def do_POST(self):
                if self.headers.get("Origin"):
                    return self.reply(403, b'{"detail":"Use the TRACE backend"}')
                if self.path not in ("/figure.glb", "/figure.png", "/figure.blend", "/import.glb"):
                    return self.reply(404, b'{"detail":"Not found"}')
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    return self.reply(415, b'{"detail":"JSON required"}')
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    limit = 32 * 1024 * 1024 if self.path == "/import.glb" else 8192
                    if not 0 < length <= limit:
                        raise ValueError("Invalid length")
                    params = json.loads(self.rfile.read(length))
                    if not isinstance(params, dict):
                        raise ValueError("Object required")
                except (ValueError, UnicodeError):
                    return self.reply(422, b'{"detail":"Invalid JSON object"}')
                future = Future()
                try:
                    bridge.jobs.put_nowait((future, self.path, params))
                except queue.Full:
                    return self.reply(503, b'{"detail":"Blender is busy"}')
                bridge.pending.set()
                try:
                    data, media = future.result(timeout=55)
                except TimeoutError:
                    future.cancel()
                    return self.reply(504, b'{"detail":"Blender timed out"}')
                except (ValueError, TypeError) as error:
                    return self.reply(422, json.dumps({"detail": str(error)}).encode())
                except Exception:
                    return self.reply(500, b'{"detail":"Blender export failed; see Blender console"}')
                self.reply(200, data, media)

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def start(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def drain(self):
        try:
            future, path, params = self.jobs.get_nowait()
        except queue.Empty:
            return 0.1
        if future.set_running_or_notify_cancel():
            try:
                future.set_result(self.render(path, params))
            except Exception as error:
                import traceback
                traceback.print_exc()
                future.set_exception(error)
        if self.jobs.empty():
            self.pending.clear()
        return 0.1

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
