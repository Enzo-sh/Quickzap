import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from quickzap import db, installer, server
from quickzap.ollama import PullProgress
from tests.fake_ollama import FakeOllama
from tests import test_api


class InstallerUnitTests(unittest.TestCase):
    def test_windows_install_via_winget(self):
        calls = []

        def fake_run(cmd, parser=None):
            calls.append(cmd)
            yield {"type": "log", "text": "winget trabajando"}
            return 0

        with mock.patch("platform.system", return_value="Windows"), \
             mock.patch("shutil.which", return_value="C:/winget.exe"), \
             mock.patch.object(installer, "_run", fake_run), \
             mock.patch.object(installer, "find_ollama", return_value="C:/ollama.exe"):
            events = list(installer.install_ollama())
        self.assertEqual(events[-1], {"type": "done"})
        self.assertIn("Ollama.Ollama", calls[0])
        self.assertIn("--accept-package-agreements", calls[0])

    def test_winget_failure_is_reported(self):
        def fake_run(cmd, parser=None):
            yield {"type": "log", "text": "x"}
            return 1

        with mock.patch("platform.system", return_value="Windows"), \
             mock.patch("shutil.which", return_value="C:/winget.exe"), \
             mock.patch.object(installer, "_run", fake_run), \
             mock.patch.object(installer, "find_ollama", return_value=None):
            with self.assertRaises(installer.InstallError):
                list(installer.install_ollama())

    def test_linux_gives_manual_command_instead_of_sudo(self):
        with mock.patch("platform.system", return_value="Linux"):
            with self.assertRaises(installer.InstallError) as ctx:
                list(installer.install_ollama())
        self.assertIn("install.sh", str(ctx.exception))

    def test_only_one_install_at_a_time(self):
        self.assertTrue(installer._lock.acquire(blocking=False))
        try:
            with self.assertRaises(installer.InstallError):
                list(installer.install_ollama())
        finally:
            installer._lock.release()

    def test_start_ollama_without_install_and_with_timeout(self):
        host = "http://127.0.0.1:1"  # puerto cerrado
        with mock.patch.object(installer, "find_ollama", return_value=None):
            self.assertFalse(installer.start_ollama(host)["ok"])
        with mock.patch.object(installer, "find_ollama", return_value="/x/ollama"), \
             mock.patch("subprocess.Popen") as popen:
            result = installer.start_ollama(host, timeout=1)
        self.assertEqual(popen.call_args[0][0], ["/x/ollama", "serve"])
        self.assertFalse(result["ok"])
        self.assertIn("no respondió", result["error"])

    def test_start_ollama_noop_when_already_running(self):
        fake = FakeOllama().start()
        try:
            with mock.patch("subprocess.Popen") as popen:
                self.assertTrue(installer.start_ollama("http://127.0.0.1:%d" % fake.port)["ok"])
            popen.assert_not_called()
        finally:
            fake.stop()


class ProgressTests(unittest.TestCase):
    def test_pull_progress_is_cumulative_and_monotonic(self):
        pp = PullProgress()
        self.assertIsNone(pp.update({"status": "pulling manifest"})["percent"])
        self.assertEqual(pp.update({"status": "p", "digest": "a", "total": 800, "completed": 400})["percent"], 50)
        r = pp.update({"status": "p", "digest": "a", "total": 800, "completed": 800})
        self.assertEqual(r["percent"], 99)                       # nunca 100 hasta que Ollama diga success
        self.assertEqual(pp.update({"status": "p", "digest": "b", "total": 200, "completed": 0})["percent"], 99)
        r = pp.update({"status": "p", "digest": "b", "total": 200, "completed": 200})
        self.assertEqual((r["completed"], r["total"]), (1000, 1000))
        self.assertEqual(pp.update({"status": "success"})["percent"], 100)

    def test_pull_progress_ignores_regressions_in_a_layer(self):
        pp = PullProgress()
        pp.update({"status": "p", "digest": "a", "total": 100, "completed": 60})
        self.assertEqual(pp.update({"status": "p", "digest": "a", "total": 100, "completed": 10})["percent"], 60)

    def test_winget_progress_parser(self):
        e = installer.parse_winget_progress("  ██████▒▒▒▒▒▒  200 MB /  800 MB")
        self.assertEqual((e["type"], e["percent"]), ("progress", 25))
        self.assertIn("200 MB de 800 MB", e["text"])
        done = installer.parse_winget_progress("  ████████████  800 MB /  800 MB")
        self.assertIsNone(done["percent"])                       # terminó de bajar: ahora instala
        self.assertIn("Instalando", done["text"])
        self.assertIsNone(installer.parse_winget_progress("Encontrado Ollama [Ollama.Ollama] Versión 0.9"))

    def test_run_turns_winget_output_into_progress_events(self):
        out = "Encontrado Ollama\n  ███▒▒▒  100 MB / 400 MB\r  ██████  300 MB / 400 MB\nCorrecto\n"
        proc = mock.Mock(); proc.stdout = io.StringIO(out); proc.wait.return_value = 0
        with mock.patch("subprocess.Popen", return_value=proc):
            gen = installer._run(["winget"], installer.parse_winget_progress)
            events = []
            try:
                while True:
                    events.append(next(gen))
            except StopIteration as stop:
                code = stop.value
        self.assertEqual(code, 0)
        # dos avances en la misma línea (separados por \r): se informa el más reciente
        self.assertEqual([e["type"] for e in events], ["log", "progress", "log"])
        self.assertEqual(events[1]["percent"], 75)

    def test_direct_download_reports_every_percent(self):
        class FakeResp(io.BytesIO):
            headers = {"Content-Length": str(4 << 20)}
            def __enter__(self): return self
            def __exit__(self, *a): return False
        resp = FakeResp(b"x" * (4 << 20))
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch("urllib.request.urlopen", return_value=resp), \
             mock.patch("tempfile.gettempdir", return_value=tmp):
            gen = installer._download_windows_installer()
            events = []
            try:
                while True:
                    events.append(next(gen))
            except StopIteration as stop:
                dest = stop.value
            self.assertTrue(Path(dest).is_file())
        self.assertEqual([e["percent"] for e in events], [25, 50, 75, 100])
        self.assertIn("de 4 MB", events[-1]["text"])

    def test_install_ends_with_100_percent_then_done(self):
        def fake_run(cmd, parser=None):
            yield {"type": "progress", "percent": 50, "text": "x"}
            return 0
        with mock.patch("platform.system", return_value="Windows"), mock.patch("shutil.which", return_value="w"), \
             mock.patch.object(installer, "_run", fake_run), mock.patch.object(installer, "find_ollama", return_value="o"):
            events = list(installer.install_ollama())
        self.assertEqual(events[-2], {"type": "progress", "percent": 100, "text": "Ollama instalado"})
        self.assertEqual(events[-1], {"type": "done"})


class SetupEndpointTests(test_api.ServerCase):
    def test_detect_shape(self):
        _, d = self.call("GET", "/api/setup/detect")
        self.assertTrue(d["ollama_running"])
        self.assertIn("qwen2.5:7b", d["installed_models"])
        self.assertTrue({f["id"] for f in d["catalog"]} >= {"qwen2.5:7b", "qwen2.5:3b"})
        self.assertTrue(all(len(f["variants"]) == 3 and all("fit" in v for v in f["variants"]) for f in d["catalog"]))
        self.assertIn("cpu", d["hardware"])
        self.assertEqual(d["recommended"], d["recommendation"]["model"])

    def test_install_streams_events_and_errors(self):
        def ok_install():
            yield {"type": "log", "text": "paso 1"}
            yield {"type": "done"}

        def bad_install():
            raise installer.InstallError("sin permisos")
            yield  # pragma: no cover

        with mock.patch.object(installer, "install_ollama", ok_install):
            ev = self.stream("/api/setup/install-ollama", {})
        self.assertEqual([e["type"] for e in ev], ["log", "done"])
        with mock.patch.object(installer, "install_ollama", bad_install):
            ev = self.stream("/api/setup/install-ollama", {})
        self.assertEqual((ev[-1]["type"], ev[-1]["phase"]), ("error", "install"))
        self.assertIn("permisos", ev[-1]["message"].lower())
        self.assertTrue(ev[-1]["hint"])

    def test_install_closes_clean_even_when_body_is_never_read(self):
        # /api/setup/install-ollama no consume el cuerpo del POST: si el servidor cierra la
        # conexión con esos bytes sin leer, macOS responde RST (no FIN) y el cliente pierde
        # la respuesta entera con ConnectionResetError 54. El drenaje debe correr igual.
        def ok_install():
            yield {"type": "log", "text": "paso 1"}
            yield {"type": "done"}

        drained = []
        original = server.Handler._drain_body

        def spy(self):
            drained.append(True)
            original(self)

        with mock.patch.object(installer, "install_ollama", ok_install), \
             mock.patch.object(server.Handler, "_drain_body", spy):
            ev = self.stream("/api/setup/install-ollama", {})
        self.assertEqual([e["type"] for e in ev], ["log", "done"])
        self.assertTrue(drained)

    def test_start_endpoint(self):
        _, r = self.call("POST", "/api/setup/start-ollama", {})
        self.assertTrue(r["ok"])


if __name__ == "__main__":
    unittest.main()
