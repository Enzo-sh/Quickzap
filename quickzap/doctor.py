"""Verificación de extremo a extremo (Python, Ollama, modelo, carga, generación, memoria) sobre el benchmark."""
import sys

from . import benchmark, config, db
from .ollama import OllamaClient

OK, BAD = "[OK]", "[X] "
PHASE = {"install": "Instalación", "download": "Descarga", "load": "Carga del modelo", "generation": "Generación"}


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

    check(sys.version_info >= (3, 9), "Python %d.%d" % sys.version_info[:2], "Se necesita Python 3.9 o superior.")
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        db.init()
        s = db.get_settings()
        check(True, "Base de datos local: %s" % (config.DATA_DIR / "quickzap.db"))
    except Exception as e:  # noqa: BLE001
        check(False, "Base de datos local: %s" % e)
        return 1

    report = benchmark.run(OllamaClient(s["ollama_host"]), s["model"], s["keep_alive"], cold=False, num_ctx=s["num_ctx"])
    ph = report["phases"]
    if "connection" in ph and ph["connection"].get("ok"):
        check(True, "Ollama %s activo" % report["ollama_version"])
    if ph.get("model", {}).get("ok"):
        check(True, "Modelo «%s» instalado" % s["model"])
    if ph.get("load", {}).get("ok"):
        check(True, "Modelo cargado en %.1f s" % ph["load"]["seconds"])
    g = ph.get("generation", {})
    if g.get("ok"):
        check(True, "Generación de texto: «%s» (%s tokens/s, primer token en %s ms)" % (g["reply"][:40], g["tps"], g["ttft_ms"]))
    mem = report.get("memory") or {}
    if mem.get("gpu_percent") is not None:
        check(mem["gpu_percent"] > 0, "Modelo en memoria: %s GB · %d%% en GPU" % (mem["model_gb"], mem["gpu_percent"]),
              "Corre solo en CPU (más lento). Probá un modelo más chico o actualizá los drivers de la GPU.")
    for err in report["errors"]:
        check(False, "%s: %s" % (PHASE.get(err["phase"], err["phase"]), err["title"]), err["hint"])
    out("\nTodo listo. Iniciá Quickzap con: python -m quickzap" if not failed else "\nHay problemas por resolver.")
    return 1 if failed else 0
