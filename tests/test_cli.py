import getpass
import io
import json
import platform
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from quickzap import __main__ as cli, reports, server
from tests.test_api import MODEL, ServerCase


def run_cli(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(list(argv))
    return code, buf.getvalue()


class CliTests(ServerCase):
    def test_bench_saves_a_shareable_report_and_compare_builds_a_table(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(server, "internet_now", return_value=False):
            out = Path(tmp) / "report.json"
            code, text = run_cli("bench", "--quality", "--out", str(out))
            self.assertEqual(code, 0, text)
            for fragment in ("Model load", "Text generation", "Stability", "Quality:", "Summary:", "tokens/s"):
                self.assertIn(fragment, text)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(report["ok"] and report["online"] is False)
            self.assertIn("startup_ms", report)
            self.assertEqual(report["quality"]["total"], 8)
            blob = json.dumps(report)                                   # the report contains no personal data
            for private in {getpass.getuser(), platform.node(), str(Path.home())} - {"", "root", "/root"}:
                self.assertNotIn(private, blob)
            code, table = run_cli("bench-compare", str(out))
            self.assertEqual(code, 0)
            self.assertIn(MODEL, table)
            self.assertIn("50.0", table)
            self.assertIn("verified", table)                         # tested without Internet

    def test_bench_quick_and_failure_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, text = run_cli("bench", "--quick", "--no-save")
            self.assertEqual(code, 0)
            self.assertNotIn("Stability", text)
            self.fake.fail_load = "model requires more system memory (10.0 GiB) than is available (6.0 GiB)"
            code, text = run_cli("bench", "--no-save")
            self.assertEqual(code, 1)
            self.assertIn("Error (load)", text)

    def test_hardware_command_and_json(self):
        code, text = run_cli("hardware")
        self.assertEqual(code, 0)
        self.assertIn("CPU", text)
        self.assertIn("Recommended", text)
        self.assertIn("cpu", json.loads(run_cli("hardware", "--json")[1]))

    def test_recommend_includes_quantization(self):
        code, text = run_cli("recommend")
        self.assertRegex(text, r"\(Q4\)")
        self.assertRegex(run_cli("recommend", "--plain")[1].strip(), r"^[\w.:-]+$")

    def test_compare_ignores_failed_reports(self):
        ok = {"ok": True, "created": "2026-11-15T10:00:00Z", "model": "m:1b",
              "hardware": {"cpu": {"name": "CPU X"}, "ram": {"total_gb": 16}, "gpus": []},
              "phases": {"load": {"seconds": 2.5}, "generation": {"ttft_ms": 300, "tps": 12.3}},
              "memory": {"vram_gb": 0, "ram_gb": 1.2}, "stability": {"stable": True}, "online": True}
        bad = dict(ok, ok=False)
        table = reports.compare_markdown([ok, bad])
        self.assertIn("CPU X", table)
        self.assertIn("12.3", table)
        self.assertIn("1 report(s) with errors", table)
        self.assertEqual(table.count("| CPU X |"), 1)


if __name__ == "__main__":
    unittest.main()


class PortTests(unittest.TestCase):
    def test_busy_port_gives_a_helpful_message_instead_of_a_traceback(self):
        import socket
        busy = socket.socket(); busy.bind(("127.0.0.1", 0)); busy.listen(1)
        port = busy.getsockname()[1]
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = server.serve(port=port, open_browser=False)
            self.assertEqual(code, 1)
            self.assertIn("--port %d" % (port + 1), buf.getvalue())
        finally:
            busy.close()

    def test_port_flag_works_without_subcommand(self):
        with mock.patch("quickzap.server.serve", return_value=0) as run:
            self.assertEqual(cli.main(["--port", "9001", "--no-browser"]), 0)
        run.assert_called_once_with(port=9001, open_browser=False)
