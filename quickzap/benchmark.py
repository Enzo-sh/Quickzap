"""Benchmark and diagnostics for the local model.

Measures load time, time to first token (TTFT), tokens/s, memory (RAM/VRAM), and stability, and separates
errors by phase: installation, model loading, and generation. No external dependencies."""
import statistics
import time
from datetime import datetime, timezone

from . import __version__, hardware
from .diagnostics import explain
from .ollama import OllamaClient, OllamaError, normalize_model

SHORT_PROMPT = "Respond with only the word OK."
LONG_PROMPT = "Write a text of about 150 words explaining how photosynthesis works."
STABILITY_TOKENS = 128
WINDOW = 16          # tokens per window to measure speed throughout generation
STABLE_RATIO = 0.7   # stable if the slowest window performs at least 70% of the median (heuristic)


def stability_stats(stamps, window=WINDOW):
    """stamps: arrival times (s) of each token. Returns per-window rates or None if there is too little data."""
    rates = []
    for i in range(0, len(stamps) - window, window):
        dt = stamps[i + window] - stamps[i]
        if dt > 0:
            rates.append(window / dt)
    if len(rates) < 2:
        return None
    med = statistics.median(rates)
    return {"windows": len(rates), "tps_min": round(min(rates), 1), "tps_median": round(med, 1),
            "tps_max": round(max(rates), 1), "stable": min(rates) >= STABLE_RATIO * med}


def _generate(client, model, prompt, options, keep_alive):
    """Generates a reply measuring TTFT and the arrival time of each token. Returns a metrics dict."""
    t0 = time.perf_counter()
    stamps, parts, last = [], [], {}
    for chunk in client.chat(model, [{"role": "user", "content": prompt}], options, keep_alive):
        if chunk.get("error"):
            raise OllamaError(chunk["error"])
        piece = (chunk.get("message") or {}).get("content", "")
        if piece:
            stamps.append(time.perf_counter() - t0)
            parts.append(piece)
        if chunk.get("done"):
            last = chunk
            break
    n, ns = last.get("eval_count"), last.get("eval_duration")
    return {"reply": "".join(parts).strip(), "ttft_ms": round(stamps[0] * 1000) if stamps else None,
            "tokens": n or len(stamps), "tps": round(n / (ns / 1e9), 1) if n and ns else None,
            "total_ms": round((time.perf_counter() - t0) * 1000), "stamps": stamps}


def _memory(client, model):
    mem = {"model_gb": None, "vram_gb": None, "ram_gb": None, "gpu_percent": None}
    for m in client.running():
        if normalize_model(m.get("name", "")) == normalize_model(model) and m.get("size"):
            size, vram = m["size"], m.get("size_vram", 0)
            mem.update(model_gb=round(size / hardware.GB, 2), vram_gb=round(vram / hardware.GB, 2),
                       ram_gb=round((size - vram) / hardware.GB, 2), gpu_percent=round(100 * vram / size))
    ram = hardware.ram()
    mem.update(system_ram_used_gb=ram["used_gb"], system_ram_total_gb=ram["total_gb"])
    hardware._vram_cache["t"] = 0  # force a fresh read
    vu = hardware.vram_usage()
    mem.update(vram_used_mib=vu["used_mib"] if vu else None, vram_total_mib=vu["total_mib"] if vu else None)
    return mem


def run(client, model, keep_alive="10m", long=False, cold=True, emit=None, num_ctx=None):
    """Runs the benchmark. `emit` receives {'type': 'stage', ...} events to show progress."""
    emit = emit or (lambda event: None)
    options = {"num_ctx": num_ctx} if num_ctx else {}
    report = {"app_version": __version__, "model": model, "ollama_version": None, "ok": False,
              "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "quick": not long,
              "phases": {}, "memory": None, "stability": None, "errors": [], "hardware": hardware.snapshot()}

    def stage(name, status, **info):
        emit({"type": "stage", "stage": name, "status": status, **info})

    def fail(stage_name, phase, err):
        info = explain(str(err), phase)
        report["errors"].append(info)
        report["phases"].setdefault(stage_name, {})["ok"] = False
        stage(stage_name, "error", **info)
        return report

    # 1) Ollama connection
    stage("connection", "running")
    t = time.perf_counter()
    try:
        report["ollama_version"] = client.version()
        names = {normalize_model(m["name"]) for m in client.models()}
    except OllamaError as e:
        return fail("connection", "install", e)
    report["phases"]["connection"] = {"ok": True, "ms": round((time.perf_counter() - t) * 1000)}
    stage("connection", "ok", detail="Ollama %s" % report["ollama_version"])

    # 2) The model is downloaded
    if normalize_model(model) not in names:
        report["phases"]["model"] = {"ok": False}
        info = {"phase": "install", "title": "The model “%s” is not downloaded" % model,
                "hint": "Open the wizard (⇩ button) and download it, or run: python -m quickzap pull %s" % model,
                "technical": "model not found", "matched": True}
        report["errors"].append(info)
        stage("model", "error", **info)
        return report
    report["phases"]["model"] = {"ok": True}
    stage("model", "ok", detail=model)

    # 3) Load into memory (cold: unload first to measure the real time)
    stage("load", "running")
    try:
        if cold:
            try:
                client.unload(model)
            except OllamaError:
                pass
        t = time.perf_counter()
        client.load(model, keep_alive)
        load_s = round(time.perf_counter() - t, 2)
    except OllamaError as e:
        return fail("load", "load", e)
    report["phases"]["load"] = {"ok": True, "seconds": load_s, "cold": cold}
    stage("load", "ok", detail="%.1f s" % load_s)

    # 4) Real text generation
    stage("generation", "running")
    try:
        g = _generate(client, model, SHORT_PROMPT, {**options, "temperature": 0, "num_predict": 16}, keep_alive)
    except OllamaError as e:
        return fail("generation", "generation", e)
    g.pop("stamps")
    g["ok"] = bool(g["reply"])
    report["phases"]["generation"] = g
    if not g["ok"]:
        return fail("generation", "generation", "The model returned no text.")
    stage("generation", "ok", detail="«%s»" % g["reply"][:40], tps=g["tps"], ttft_ms=g["ttft_ms"])

    # 5) Memory
    report["memory"] = _memory(client, model)
    stage("memory", "ok")

    # 6) Stability in a longer generation (optional: may take a while on modest computers)
    if long:
        stage("stability", "running")
        try:
            s = _generate(client, model, LONG_PROMPT, {**options, "temperature": 0.7, "num_predict": STABILITY_TOKENS}, keep_alive)
        except OllamaError as e:
            return fail("stability", "generation", e)
        stats = stability_stats(s["stamps"])
        report["stability"] = {"tokens": s["tokens"], "tps": s["tps"], "total_s": round(s["total_ms"] / 1000, 1), **(stats or {"stable": None})}
        stage("stability", "ok", detail="stable" if report["stability"].get("stable") else "irregular")
    report["ok"] = True
    return report
