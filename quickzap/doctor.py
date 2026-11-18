"""End-to-end checks (Python, Ollama, model, load, generation, memory) based on the benchmark."""
import sys

from . import benchmark, config, db
from .ollama import OllamaClient

OK, BAD = "[OK]", "[X] "
PHASE = {"install": "Installation", "download": "Download", "load": "Model load", "generation": "Generation"}


def run(out=print):
    failed = False

    def check(ok, text, hint=None):
        nonlocal failed
        out("%s %s" % (OK if ok else BAD, text))
        if not ok:
            failed = True
            if hint:
                out("     -> " + hint)
        return ok

    check(sys.version_info >= (3, 9), "Python %d.%d" % sys.version_info[:2], "Python 3.9 or later is required.")
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        db.init()
        s = db.get_settings()
        check(True, "Local database: %s" % (config.DATA_DIR / "quickzap.db"))
    except Exception as e:  # noqa: BLE001
        check(False, "Local database: %s" % e)
        return 1

    report = benchmark.run(OllamaClient(s["ollama_host"]), s["model"], s["keep_alive"], cold=False, num_ctx=s["num_ctx"])
    ph = report["phases"]
    if "connection" in ph and ph["connection"].get("ok"):
        check(True, "Ollama %s running" % report["ollama_version"])
    if ph.get("model", {}).get("ok"):
        check(True, "Model “%s” installed" % s["model"])
    if ph.get("load", {}).get("ok"):
        check(True, "Model loaded in %.1f s" % ph["load"]["seconds"])
    g = ph.get("generation", {})
    if g.get("ok"):
        check(True, "Text generation: “%s” (%s tokens/s, first token in %s ms)" % (g["reply"][:40], g["tps"], g["ttft_ms"]))
    mem = report.get("memory") or {}
    if mem.get("gpu_percent") is not None:
        check(mem["gpu_percent"] > 0, "Model in memory: %s GB · %d%% on GPU" % (mem["model_gb"], mem["gpu_percent"]),
              "Runs on CPU only (slower). Try a smaller model or update the GPU drivers.")
    for err in report["errors"]:
        check(False, "%s: %s" % (PHASE.get(err["phase"], err["phase"]), err["title"]), err["hint"])
    out("\nAll set. Start Quickzap with: python -m quickzap" if not failed else "\nThere are issues to fix.")
    return 1 if failed else 0
