"""Local HTTP server: serves the interface and exposes the API (/api/...). Standard library only."""
import json
import re
import socket
import sys
import threading
import time
import traceback
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import benchmark, config, db, diagnostics, evals, hardware, installer
from .ollama import OllamaClient, OllamaError, PullProgress, normalize_model, valid_model_name

MAX_BODY = 1_000_000
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}
_online = {"t": 0.0, "v": None, "busy": False}  # v=None: not known yet


def _probe_internet():
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=1.5).close()
        ok = True
    except OSError:
        ok = False
    _online.update(t=time.time(), v=ok, busy=False)


def internet_now():
    """Synchronous check (console only: the server uses internet_available)."""
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=1.5).close()
        return True
    except OSError:
        return False


def internet_available():
    """Never blocks: returns the last result (or None if not known yet) and refreshes in the background."""
    if time.time() - _online["t"] > 15 and not _online["busy"]:
        _online["busy"] = True
        threading.Thread(target=_probe_internet, daemon=True).start()
    return _online["v"]


def build_messages(settings, history):
    """System instructions + conversation context (RAG and memory will come in later stages)."""
    system = config.SYSTEM_PROMPT.format(personality=settings["personality"], today=date.today().isoformat())
    return [{"role": "system", "content": system}] + history


def friendly_error(err, model):
    text = str(err)
    if err.unreachable:
        return "Could not connect to Ollama. Is it running? Try “ollama serve” or open the wizard (⇩)."
    if err.status == 404 or "not found" in text.lower():
        return "The model “%s” is not installed. Download it with: python -m quickzap pull %s" % (model, model)
    info = diagnostics.explain(text)
    return "%s. %s" % (info["title"], info["hint"]) if info["matched"] else text


class Handler(BaseHTTPRequestHandler):
    server_version = "Quickzap/0.1"

    def log_message(self, fmt, *args):
        pass  # silent; real errors are printed in _dispatch

    # ---- infrastructure ----
    def do_GET(self): self._dispatch("GET")
    def do_POST(self): self._dispatch("POST")
    def do_DELETE(self): self._dispatch("DELETE")

    def _dispatch(self, method):
        self._body_done = False
        try:
            host = self.headers.get("Host", "")
            if urlparse("//" + host).hostname not in ALLOWED_HOSTS:
                return self._json({"error": "Host not allowed."}, 403)
            origin = self.headers.get("Origin")
            if method != "GET" and origin and urlparse(origin).netloc != host:
                return self._json({"error": "Origin not allowed."}, 403)
            path = urlparse(self.path).path
            for m, pattern, fn in ROUTES:
                match = m == method and re.fullmatch(pattern, path)
                if match:
                    return fn(self, *match.groups())
            self._json({"error": "Not found."}, 404)
        except ConnectionError:
            pass  # the browser closed the connection
        except ValueError as e:
            self._json({"error": str(e)}, 400)
        except OllamaError as e:
            self._json({"error": friendly_error(e, db.get_settings()["model"])}, 502)
        except Exception:
            traceback.print_exc()
            self._json({"error": "Internal server error."}, 500)
        finally:
            self._drain_body()

    def _drain_body(self):
        """Discards the request body that no handler read. If left unread when closing
        the connection, macOS sends an RST instead of a FIN and the client loses the already
        sent response (ConnectionResetError 54 on /api/setup/install-ollama, the only streaming
        POST that does not go through _body). Reading those bytes ensures a clean shutdown on all three systems."""
        if getattr(self, "_body_done", False):
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if 0 < length <= MAX_BODY:
                self.rfile.read(length)
        except (OSError, ValueError):
            pass  # the connection is already closed: shut down anyway

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("Request too large.")
        self._body_done = True  # nothing left for the shutdown drain to discard
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object.")
        return data

    def _json(self, obj, status=200):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _start_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

    def _emit(self, obj):
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode() + b"\n")
        self.wfile.flush()

    # ---- routes ----
    def page(self):
        raw = (config.ROOT / "web" / "index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(raw)

    def status(self):
        s = db.get_settings()
        client = OllamaClient(s["ollama_host"])
        out = {"ollama": {"running": False, "host": client.host, "version": None},
               "model": {"name": s["model"], "installed": False},
               "installed": [], "loaded": [], "online": internet_available(),
               "recommended": hardware.recommend()["model"], "settings": s}
        try:
            out["ollama"]["version"] = client.version()
            out["ollama"]["running"] = True
            out["installed"] = client.models()
            out["loaded"] = client.running()
            names = {normalize_model(m["name"]) for m in out["installed"]}
            out["model"]["installed"] = normalize_model(s["model"]) in names
        except OllamaError as e:
            out["ollama"]["error"] = str(e)
        self._json(out)

    def get_settings(self): self._json(db.get_settings())
    def set_settings(self): self._json(db.update_settings(self._body()))

    def select_model(self):
        name = self._body().get("model")
        if not valid_model_name(name):
            raise ValueError("Invalid model name.")
        db.update_settings({"model": name})
        self._json({"ok": True, "model": name})

    def pull_model(self):
        name = self._body().get("model")
        if not valid_model_name(name):
            raise ValueError("Invalid model name.")
        client = OllamaClient(db.get_settings()["ollama_host"])
        progress = PullProgress()
        self._start_stream()
        try:
            for chunk in client.pull(name):
                if chunk.get("error"):
                    raise OllamaError(chunk["error"])
                self._emit({"type": "progress", **progress.update(chunk)})
            self._emit({"type": "done", "model": name})
        except OllamaError as e:
            info = diagnostics.explain(str(e), "download")
            self._emit({"type": "error", "message": friendly_error(e, name) if not info["matched"] else info["title"],
                        "hint": info["hint"], "phase": info["phase"]})

    # ---- installation wizard ----
    def setup_detect(self):
        self._json(installer.detect(db.get_settings()))

    def setup_install(self):
        self._start_stream()
        try:
            for event in installer.install_ollama():
                self._emit(event)
        except installer.InstallError as e:
            info = diagnostics.explain(str(e), "install")
            self._emit({"type": "error", "message": str(e) if not info["matched"] else info["title"],
                        "hint": info["hint"], "phase": "install"})

    def setup_start(self):
        self._json(installer.start_ollama(db.get_settings()["ollama_host"]))

    # ---- benchmark and statistics ----
    def benchmark_run(self):
        body = self._body()
        s = db.get_settings()
        name = body.get("model") or s["model"]
        if not valid_model_name(name):
            raise ValueError("Invalid model name.")
        client = OllamaClient(s["ollama_host"])
        self._start_stream()
        report = benchmark.run(client, name, s["keep_alive"], long=bool(body.get("long")), emit=self._emit, num_ctx=s["num_ctx"])
        report["online"] = internet_available()
        if body.get("quality") and report["ok"]:
            report["quality"] = evals.run(client, name, s["keep_alive"], emit=self._emit)
        db.save_benchmark(report)
        self._emit({"type": "report", "report": report})

    def benchmark_history(self):
        self._json(db.latest_benchmarks())

    def stats(self):
        s = db.get_settings()
        client = OllamaClient(s["ollama_host"])
        out = {"model": s["model"], "ollama": {"running": False, "version": None}, "online": internet_available(),
               "loaded": None, "system": {"ram": hardware.ram(), "vram": hardware.vram_usage(), "cpu": hardware.cpu_info()["name"]},
               "chat": db.metrics_summary(), "data": db.counts(), "benchmarks": db.latest_benchmarks()}
        try:
            out["ollama"] = {"running": True, "version": client.version()}
            for m in client.running():
                if m.get("size"):
                    size, vram = m["size"], m.get("size_vram", 0)
                    out["loaded"] = {"name": m["name"], "model_gb": round(size / hardware.GB, 2), "vram_gb": round(vram / hardware.GB, 2),
                                     "ram_gb": round((size - vram) / hardware.GB, 2), "gpu_percent": round(100 * vram / size)}
                    break
        except OllamaError:
            pass
        self._json(out)

    def list_convs(self): self._json(db.list_conversations())

    def get_conv(self, cid):
        conv = db.get_conversation(int(cid))
        self._json(conv or {"error": "Not found."}, 200 if conv else 404)

    def delete_conv(self, cid):
        ok = db.delete_conversation(int(cid))
        self._json({"ok": ok}, 200 if ok else 404)

    def chat(self):
        body = self._body()
        text = str(body.get("message", "")).strip()
        if not text:
            raise ValueError("The message is empty.")
        if len(text) > 8000:
            raise ValueError("The message is too long (maximum 8000 characters).")
        s = db.get_settings()
        cid = body.get("conversation_id")
        if cid is None:
            cid = db.create_conversation(text[:60], s["model"])
        elif not isinstance(cid, int) or not db.conversation_exists(cid):
            raise ValueError("The conversation does not exist.")
        db.add_message(cid, "user", text)
        messages = build_messages(s, db.history(cid, s["context_messages"]))

        self._start_stream()
        self._emit({"type": "meta", "conversation_id": cid, "model": s["model"]})
        reply, t0, first = [], time.perf_counter(), None
        stream = OllamaClient(s["ollama_host"]).chat(
            s["model"], messages, {"temperature": s["temperature"], "num_ctx": s["num_ctx"]}, s["keep_alive"])
        try:
            for chunk in stream:
                if chunk.get("error"):
                    raise OllamaError(chunk["error"])
                piece = (chunk.get("message") or {}).get("content", "")
                if piece:
                    if first is None:
                        first = time.perf_counter() - t0
                    reply.append(piece)
                    self._emit({"type": "token", "text": piece})
                if chunk.get("done"):
                    n, ns = chunk.get("eval_count"), chunk.get("eval_duration")
                    tps = round(n / (ns / 1e9), 1) if n and ns else None
                    ttft = round(first * 1000) if first is not None else None
                    total = round((time.perf_counter() - t0) * 1000)
                    db.add_metric(cid, s["model"], ttft, total, n, tps)
                    self._emit({"type": "done", "tokens": n, "tps": tps, "ttft_ms": ttft, "total_ms": total})
                    break
        except OllamaError as e:
            self._emit({"type": "error", "message": friendly_error(e, s["model"])})
        finally:
            stream.close()  # closes the connection to Ollama and stops generation
            if reply:
                db.add_message(cid, "assistant", "".join(reply), s["model"])


ROUTES = [
    ("GET", r"/(index\.html)?", lambda h, *_: h.page()),
    ("GET", r"/api/status", Handler.status),
    ("GET", r"/api/settings", Handler.get_settings),
    ("POST", r"/api/settings", Handler.set_settings),
    ("POST", r"/api/models/select", Handler.select_model),
    ("POST", r"/api/models/pull", Handler.pull_model),
    ("GET", r"/api/setup/detect", Handler.setup_detect),
    ("POST", r"/api/setup/install-ollama", Handler.setup_install),
    ("POST", r"/api/setup/start-ollama", Handler.setup_start),
    ("POST", r"/api/benchmark", Handler.benchmark_run),
    ("GET", r"/api/benchmarks", Handler.benchmark_history),
    ("GET", r"/api/stats", Handler.stats),
    ("GET", r"/api/conversations", Handler.list_convs),
    ("GET", r"/api/conversations/(\d+)", Handler.get_conv),
    ("DELETE", r"/api/conversations/(\d+)", Handler.delete_conv),
    ("POST", r"/api/chat", Handler.chat),
]


def make_server(host="127.0.0.1", port=8765):
    db.init()
    internet_available()  # starts the background check so the status is ready
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    return httpd


def serve(host="127.0.0.1", port=8765, open_browser=True):
    try:
        httpd = make_server(host, port)
    except OSError:
        print("Could not use port %d: another copy of Quickzap is probably already open.\n"
              "Close it, or start this one on a different port: python -m quickzap --port %d" % (port, port + 1))
        return 1
    url = "http://%s:%d/" % ("localhost" if host == "127.0.0.1" else host, httpd.server_address[1])
    print("Quickzap at %s" % url)
    print("Keep this window open while using Quickzap. To exit: Ctrl+C or close the window.")
    if open_browser:
        threading.Timer(0.8, webbrowser.open, [url]).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nGoodbye.")
    finally:
        httpd.server_close()
    return 0
