import unittest

from quickzap import benchmark, evals
from quickzap.diagnostics import explain
from quickzap.ollama import OllamaClient
from tests.fake_ollama import FakeOllama

MODEL = "qwen2.5:7b"


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeOllama([MODEL]).start()
        self.client = OllamaClient("http://127.0.0.1:%d" % self.fake.port)

    def tearDown(self):
        try:
            self.fake.stop()
        except Exception:
            pass

    def test_full_report(self):
        events = []
        r = benchmark.run(self.client, MODEL, long=True, emit=events.append)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["ollama_version"], "0.0.0-fake")
        g = r["phases"]["generation"]
        self.assertTrue(g["ok"] and g["reply"])                    # real text generation
        self.assertEqual(g["tps"], 50.0)                           # eval_count / eval_duration from Ollama
        self.assertIsNotNone(g["ttft_ms"])
        self.assertEqual(r["memory"]["gpu_percent"], 100)
        self.assertAlmostEqual(r["memory"]["model_gb"], 4.66, places=1)
        self.assertEqual(r["memory"]["ram_gb"], 0.0)
        self.assertEqual(r["stability"]["tokens"], 128)
        self.assertIn("hardware", r)
        self.assertEqual([e["stage"] for e in events if e["status"] == "ok"],
                         ["connection", "model", "load", "generation", "memory", "stability"])

    def test_quick_mode_skips_stability(self):
        r = benchmark.run(self.client, MODEL)
        self.assertTrue(r["ok"])
        self.assertIsNone(r["stability"])
        self.assertTrue(r["quick"])

    def test_load_time_and_ttft_are_measured(self):
        self.fake.load_delay, self.fake.first_token_delay = 0.25, 0.2
        r = benchmark.run(self.client, MODEL)
        self.assertGreaterEqual(r["phases"]["load"]["seconds"], 0.25)
        self.assertTrue(r["phases"]["load"]["cold"])
        self.assertGreaterEqual(r["phases"]["generation"]["ttft_ms"], 200)

    def test_cold_load_unloads_first(self):
        self.fake.loaded = MODEL
        benchmark.run(self.client, MODEL, cold=True)
        self.assertEqual(self.fake.loaded, MODEL)  # it was unloaded and loaded again

    def test_ollama_down_is_install_error(self):
        self.fake.down = True
        r = benchmark.run(self.client, MODEL)
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["phase"], "install")

    def test_unreachable_ollama_is_install_error(self):
        self.fake.stop()
        events = []
        r = benchmark.run(self.client, MODEL, emit=events.append)
        self.assertEqual(r["errors"][0]["phase"], "install")
        self.assertIn("Ollama", r["errors"][0]["title"])
        self.assertEqual(events[-1]["status"], "error")

    def test_missing_model_is_install_error_with_hint(self):
        r = benchmark.run(self.client, "otro:1b")
        self.assertEqual(r["errors"][0]["phase"], "install")
        self.assertIn("python -m quickzap pull otro:1b", r["errors"][0]["hint"])

    def test_out_of_memory_is_load_error(self):
        self.fake.fail_load = "model requires more system memory (10.0 GiB) than is available (6.0 GiB)"
        r = benchmark.run(self.client, MODEL)
        self.assertEqual(r["errors"][0]["phase"], "load")
        self.assertIn("memory", r["errors"][0]["title"])
        self.assertNotIn("generation", r["phases"])

    def test_crash_during_generation_is_generation_error(self):
        self.fake.chat_error = "llama runner process has terminated: exit status 2"
        r = benchmark.run(self.client, MODEL)
        self.assertEqual(r["errors"][0]["phase"], "generation")
        self.assertIn("load", r["phases"])         # load did work
        self.assertTrue(r["phases"]["load"]["ok"])

    def test_stability_stats(self):
        steady = [i * 0.01 for i in range(64)]
        self.assertTrue(benchmark.stability_stats(steady)["stable"])
        slowing = steady[:32] + [steady[31] + (i + 1) * 0.06 for i in range(32)]
        s = benchmark.stability_stats(slowing)
        self.assertFalse(s["stable"])
        self.assertLess(s["tps_min"], s["tps_max"])
        self.assertIsNone(benchmark.stability_stats([0.0, 0.1, 0.2]))


class ExplainTests(unittest.TestCase):
    def test_classification(self):
        cases = [("write /x: no space left on device", "download"), ("dial tcp: i/o timeout", "download"),
                 ("Access is denied", "install"), ("CUDA error: out of memory", "load"),
                 ("pull model manifest: file does not exist", "download"), ("something odd", "generation")]
        for text, phase in cases:
            self.assertEqual(explain(text)["phase"], phase, text)
        self.assertTrue(explain("no space left on device")["hint"])
        self.assertFalse(explain("something odd")["matched"])
        self.assertIn("doctor", explain("something odd")["hint"])   # there is always a hint, even if the error is not recognized


class StubClient:
    def __init__(self, answers):
        self.answers = answers

    def chat(self, model, messages, options=None, keep_alive="10m"):
        prompt = messages[-1]["content"]
        reply = next((a for key, a in self.answers.items() if key in prompt), "Yes.")
        yield {"message": {"content": reply}}
        yield {"done": True}


GOOD = {"17 times 23": "391", "Ana is": "16", "capital of France": "Paris",
        "gravity": "Gravity is the force that attracts bodies toward the Earth.",
        "three colors": "red, green, blue", "only the word OK": "OK",
        "2087": "I don't know: that year has not happened yet.", "Quantum Neurophysics": "I have no information about that article; it may not exist."}


class EvalTests(unittest.TestCase):
    def test_good_model_scores_full(self):
        r = evals.run(StubClient(GOOD), "m")
        self.assertEqual((r["score"], r["total"]), (8, 8), [x for x in r["results"] if not x["ok"]])

    def test_hallucinating_model_is_penalized(self):
        bad = dict(GOOD, **{"Quantum Neurophysics": "Smith, J. et al. (2031). Journal of Gastro-Neuroscience, 12(3).",
                            "2087": "The winner was Marie Dupont.", "17 times 23": "392"})
        r = evals.run(StubClient(bad), "m")
        failed = {x["id"] for x in r["results"] if not x["ok"]}
        self.assertEqual(failed, {"arithmetic", "honesty", "no-fabrication"})

    def test_sycophantic_all_yes_scores_zero(self):
        self.assertEqual(evals.run(StubClient({}), "m")["score"], 0)


if __name__ == "__main__":
    unittest.main()
