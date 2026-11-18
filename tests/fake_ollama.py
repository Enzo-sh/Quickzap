"""Simulated Ollama (same HTTP API) to test Quickzap without a GPU or downloads."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOllama:
    def __init__(self, models=()):
        self.models = list(models)
        self.chat_calls = []
        self.loaded = None
        self.down = False             # Ollama installed but stopped
        self.pull_delay = 0.0         # seconds between download events
        self.load_delay = 0.0         # seconds it takes to load the model
        self.fail_load = None         # error message on load (e.g. out of memory)
        self.first_token_delay = 0.0  # seconds until the first token
        self.token_delay = 0.0        # seconds between tokens
        self.chat_error = None        # error in the middle of generation
        self.pull_error = None        # error during download (e.g. no disk space)
        self.size_vram = 5_000_000_000
        self.size = 5_000_000_000
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def _send(self, obj, status=200):
                raw = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _stream(self, items, delay=0.0):
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                for it in items:
                    self.wfile.write(json.dumps(it).encode() + b"\n")
                    self.wfile.flush()
                    if delay:
                        time.sleep(delay)

            def do_GET(self):
                if fake.down:
                    return self._send({"error": "down"}, 503)
                if self.path == "/api/version":
                    self._send({"version": "0.0.0-fake"})
                elif self.path == "/api/tags":
                    self._send({"models": [{"name": m, "size": 4_700_000_000} for m in fake.models]})
                elif self.path == "/api/ps":
                    self._send({"models": [{"name": fake.loaded, "size": fake.size, "size_vram": fake.size_vram}]
                                if fake.loaded else []})
                else:
                    self._send({"error": "not found"}, 404)

            def do_POST(self):
                if fake.down:
                    return self._send({"error": "down"}, 503)
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if self.path == "/api/generate":
                    return self._generate(body)
                if self.path == "/api/chat":
                    return self._chat(body)
                if self.path == "/api/pull":
                    return self._pull(body)
                self._send({"error": "not found"}, 404)

            def _generate(self, body):
                if body["model"] not in fake.models:
                    return self._send({"error": "model '%s' not found" % body["model"]}, 404)
                if body.get("keep_alive") == 0:
                    fake.loaded = None
                    return self._send({"done": True, "done_reason": "unload"})
                if fake.fail_load:
                    return self._send({"error": fake.fail_load}, 500)
                time.sleep(fake.load_delay)
                fake.loaded = body["model"]
                self._send({"done": True, "done_reason": "load", "load_duration": int(fake.load_delay * 1e9)})

            def _chat(self, body):
                fake.chat_calls.append(body)
                if body["model"] not in fake.models:
                    return self._send({"error": "model '%s' not found" % body["model"]}, 404)
                fake.loaded = body["model"]
                predict = (body.get("options") or {}).get("num_predict", 0)
                last = body["messages"][-1]["content"]
                words = ["word"] * predict if predict > 32 else ("Echo: " + last).split(" ")
                time.sleep(fake.first_token_delay)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                for i, w in enumerate(words):
                    if fake.chat_error and i == 2:
                        self.wfile.write(json.dumps({"error": fake.chat_error}).encode() + b"\n")
                        return
                    self.wfile.write(json.dumps({"message": {"role": "assistant", "content": w + " "}, "done": False}).encode() + b"\n")
                    self.wfile.flush()
                    if fake.token_delay:
                        time.sleep(fake.token_delay)
                self.wfile.write(json.dumps({"message": {"role": "assistant", "content": ""}, "done": True, "eval_count": len(words),
                                             "eval_duration": len(words) * 20_000_000}).encode() + b"\n")

            def _pull(self, body):
                name = body["model"]
                if fake.pull_error:
                    return self._stream([{"status": "pulling manifest"}, {"error": fake.pull_error}])
                big, small = "sha256:aaaa1111", "sha256:bbbb2222"
                items = [{"status": "pulling manifest"},
                         {"status": "pulling aaaa1111", "digest": big, "total": 1000, "completed": 0},
                         {"status": "pulling aaaa1111", "digest": big, "total": 1000, "completed": 400},
                         {"status": "pulling aaaa1111", "digest": big, "total": 1000, "completed": 1000},
                         {"status": "pulling bbbb2222", "digest": small, "total": 200, "completed": 0},
                         {"status": "pulling bbbb2222", "digest": small, "total": 200, "completed": 200},
                         {"status": "verifying sha256 digest"}, {"status": "writing manifest"}, {"status": "success"}]
                if name not in fake.models:
                    fake.models.append(name)
                self._stream(items, fake.pull_delay)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
