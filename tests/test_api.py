import http.client
import io
import json
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from unittest import mock

from quickzap import config, db, doctor, server
from tests.fake_ollama import FakeOllama

MODEL = "qwen2.5:7b"


class ServerCase(unittest.TestCase):
    """Base: Quickzap server + simulated Ollama on free ports, with a temporary database."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        config.DATA_DIR = Path(self.tmp.name)
        self.fake = FakeOllama([MODEL]).start()
        db.init()
        db.update_settings({"ollama_host": "http://127.0.0.1:%d" % self.fake.port, "model": MODEL})
        self.httpd = server.make_server(port=0)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown(); self.httpd.server_close()
        try:
            self.fake.stop()
        except Exception:
            pass
        self.tmp.cleanup()

    def req(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Content-Type": "application/json", **(headers or {})}
        c.request(method, path, json.dumps(body) if body is not None else None, h)
        r = c.getresponse()
        raw = r.read().decode()
        c.close()
        return r.status, raw

    def call(self, method, path, body=None, headers=None):
        status, raw = self.req(method, path, body, headers)
        return status, json.loads(raw)

    def stream(self, path, body):
        status, raw = self.req("POST", path, body)
        self.assertEqual(status, 200, raw)
        return [json.loads(line) for line in raw.splitlines() if line]


class ApiTest(ServerCase):
    def test_page_is_served(self):
        status, raw = self.req("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("QuickZap", raw)
        self.assertIn("Local AI", raw)

    def test_status_and_pull_flow(self):
        db.update_settings({"model": "llama3.2:3b"})
        _, st = self.call("GET", "/api/status")
        self.assertTrue(st["ollama"]["running"])
        self.assertFalse(st["model"]["installed"])
        events = self.stream("/api/models/pull", {"model": "llama3.2:3b"})
        self.assertEqual(events[-1]["type"], "done")
        percents = [e["percent"] for e in events if e["type"] == "progress" and e["percent"] is not None]
        self.assertEqual(percents[0], 0)
        self.assertIn(40, percents)                       # 400/1000 of the first layer
        self.assertEqual(percents, sorted(percents))      # never goes backwards even when another layer appears
        self.assertEqual(percents[-1], 100)
        self.assertTrue(any(e.get("total") == 1200 for e in events))
        _, st = self.call("GET", "/api/status")
        self.assertTrue(st["model"]["installed"])

    def test_chat_streams_persists_and_keeps_context(self):
        ev = self.stream("/api/chat", {"message": "hello world"})
        self.assertEqual(ev[0]["type"], "meta")
        cid = ev[0]["conversation_id"]
        text = "".join(e["text"] for e in ev if e["type"] == "token")
        self.assertEqual(text.strip(), "Echo: hello world")
        self.assertEqual(ev[-1]["type"], "done")
        self.assertEqual(ev[-1]["tps"], 50.0)
        self.stream("/api/chat", {"conversation_id": cid, "message": "second"})
        sent = self.fake.chat_calls[-1]["messages"]
        self.assertEqual(sent[0]["role"], "system")
        self.assertEqual([m["role"] for m in sent[1:]], ["user", "assistant", "user"])
        self.assertEqual(sent[1]["content"], "hello world")
        _, conv = self.call("GET", "/api/conversations/%d" % cid)
        self.assertEqual(len(conv["messages"]), 4)

    def test_context_window_is_limited(self):
        db.update_settings({"context_messages": 2})
        cid = self.stream("/api/chat", {"message": "one"})[0]["conversation_id"]
        self.stream("/api/chat", {"conversation_id": cid, "message": "dos"})
        sent = self.fake.chat_calls[-1]["messages"]
        self.assertEqual(len(sent), 3)  # system + 2 most recent messages

    def test_chat_with_missing_model_explains_how_to_fix(self):
        db.update_settings({"model": "does-not-exist:1b"})
        ev = self.stream("/api/chat", {"message": "hello"})
        self.assertEqual(ev[-1]["type"], "error")
        self.assertIn("python -m quickzap pull does-not-exist:1b", ev[-1]["message"])

    def test_ollama_down_is_reported_and_chat_fails_gracefully(self):
        self.fake.stop()
        _, st = self.call("GET", "/api/status")
        self.assertFalse(st["ollama"]["running"])
        ev = self.stream("/api/chat", {"message": "hello"})
        self.assertEqual(ev[-1]["type"], "error")
        self.assertIn("Ollama", ev[-1]["message"])

    def test_conversations_list_delete_and_model_switch_keeps_history(self):
        cid = self.stream("/api/chat", {"message": "first"})[0]["conversation_id"]
        self.fake.models.append("other:1b")
        status, _ = self.call("POST", "/api/models/select", {"model": "other:1b"})
        self.assertEqual(status, 200)
        self.stream("/api/chat", {"conversation_id": cid, "message": "second"})
        self.assertEqual(self.fake.chat_calls[-1]["model"], "other:1b")
        self.assertEqual(self.fake.chat_calls[-1]["messages"][1]["content"], "first")
        _, lst = self.call("GET", "/api/conversations")
        self.assertEqual([c["id"] for c in lst], [cid])
        self.assertEqual(self.call("DELETE", "/api/conversations/%d" % cid)[0], 200)
        self.assertEqual(self.call("GET", "/api/conversations/%d" % cid)[0], 404)

    def test_validation(self):
        self.assertEqual(self.call("POST", "/api/chat", {"message": "  "})[0], 400)
        self.assertEqual(self.call("POST", "/api/chat", {"message": "x", "conversation_id": 999})[0], 400)
        self.assertEqual(self.call("POST", "/api/settings", {"temperature": 9})[0], 400)
        self.assertEqual(self.call("POST", "/api/settings", {"nope": 1})[0], 400)
        self.assertEqual(self.call("POST", "/api/models/select", {"model": "../../etc"})[0], 400)
        status, s = self.call("POST", "/api/settings", {"temperature": 0.2})
        self.assertEqual((status, s["temperature"]), (200, 0.2))

    def test_security_host_and_origin(self):
        self.assertEqual(self.call("GET", "/api/status", headers={"Host": "evil.example.com"})[0], 403)
        self.assertEqual(self.call("POST", "/api/chat", {"message": "hello"},
                                   headers={"Origin": "http://evil.example.com"})[0], 403)

    def test_doctor_passes_against_working_ollama(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = doctor.run()
        self.assertEqual(code, 0, buf.getvalue())
        self.assertIn("100% on GPU", buf.getvalue())

    def test_doctor_fails_when_model_missing(self):
        db.update_settings({"model": "missing:1b"})
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(doctor.run(), 1)
        self.assertIn("python -m quickzap pull missing:1b", buf.getvalue())


class BenchmarkAndStatsTests(ServerCase):
    def test_benchmark_endpoint_streams_stages_and_saves_history(self):
        ev = self.stream("/api/benchmark", {"long": False})
        stages = [e["stage"] for e in ev if e["type"] == "stage" and e["status"] == "ok"]
        self.assertEqual(stages, ["connection", "model", "load", "generation", "memory"])
        report = ev[-1]["report"]
        self.assertTrue(report["ok"])
        self.assertIn("online", report)
        _, hist = self.call("GET", "/api/benchmarks")
        self.assertEqual([h["model"] for h in hist], [MODEL])
        self.assertEqual(hist[0]["tps"], 50.0)

    def test_benchmark_reports_phase_errors(self):
        self.fake.fail_load = "model requires more system memory (10.0 GiB) than is available (6.0 GiB)"
        ev = self.stream("/api/benchmark", {})
        self.assertEqual(ev[-1]["report"]["errors"][0]["phase"], "load")
        self.assertEqual(self.call("GET", "/api/benchmarks")[1], [])   # only successful benchmarks are compared

    def test_benchmark_with_quality_eval(self):
        ev = self.stream("/api/benchmark", {"quality": True})
        q = ev[-1]["report"]["quality"]
        self.assertEqual(q["total"], 8)
        self.assertEqual([e["done"] for e in ev if e["type"] == "eval"], list(range(1, 9)))

    def test_chat_records_metrics_and_stats_endpoint(self):
        self.fake.first_token_delay = 0.1
        ev = self.stream("/api/chat", {"message": "hello"})
        done = ev[-1]
        self.assertEqual(done["type"], "done")
        self.assertGreaterEqual(done["ttft_ms"], 100)
        self.assertGreaterEqual(done["total_ms"], done["ttft_ms"])
        _, st = self.call("GET", "/api/stats")
        self.assertEqual(st["model"], MODEL)
        self.assertTrue(st["ollama"]["running"])
        self.assertEqual(st["chat"]["count"], 1)
        self.assertEqual(st["chat"]["tps_avg"], 50.0)
        self.assertEqual(st["data"]["conversations"], 1)
        self.assertEqual(st["data"]["messages"], 2)
        self.assertGreater(st["data"]["db_bytes"], 0)
        self.assertEqual(st["loaded"]["gpu_percent"], 100)
        self.assertIsNotNone(st["system"]["ram"]["total_gb"])

    def test_stats_when_ollama_is_down(self):
        self.fake.stop()
        _, st = self.call("GET", "/api/stats")
        self.assertFalse(st["ollama"]["running"])
        self.assertIsNone(st["loaded"])

    def test_context_size_is_configurable_and_sent_to_ollama(self):
        self.stream("/api/chat", {"message": "one"})
        self.assertEqual(self.fake.chat_calls[-1]["options"]["num_ctx"], 4096)
        self.assertEqual(self.call("POST", "/api/settings", {"num_ctx": 2048})[0], 200)
        self.stream("/api/chat", {"message": "two"})
        self.assertEqual(self.fake.chat_calls[-1]["options"]["num_ctx"], 2048)
        self.assertEqual(self.call("POST", "/api/settings", {"num_ctx": 100})[0], 400)

    def test_download_errors_come_explained(self):
        self.fake.pull_error = "write /models/blob: no space left on device"
        ev = self.stream("/api/models/pull", {"model": "x:1b"})
        err = ev[-1]
        self.assertEqual((err["type"], err["phase"]), ("error", "download"))
        self.assertIn("space", err["message"])
        self.assertTrue(err["hint"])

    def test_internet_check_never_blocks_a_request(self):
        def slow(*a, **k):
            time.sleep(1.0)
            raise OSError("no network")
        server._online.update(t=0.0, v=None, busy=False)
        with mock.patch("socket.create_connection", slow):
            t = time.perf_counter()
            first = server.internet_available()
            elapsed = time.perf_counter() - t
            self.assertLess(elapsed, 0.3)
            self.assertIsNone(first)                       # not known yet: do not assume "offline"
            time.sleep(1.3)
            self.assertIs(server.internet_available(), False)


if __name__ == "__main__":
    unittest.main()
