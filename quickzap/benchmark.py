"""Benchmark y diagnóstico del modelo local.

Mide carga, tiempo hasta el primer token (TTFT), tokens/s, memoria (RAM/VRAM) y estabilidad, y separa los
errores por fase: instalación, carga del modelo y generación. Sin dependencias externas."""
import statistics
import time
from datetime import datetime, timezone

from . import __version__, hardware
from .diagnostics import explain
from .ollama import OllamaClient, OllamaError, normalize_model

SHORT_PROMPT = "Respondé únicamente con la palabra OK."
LONG_PROMPT = "Escribí un texto de unas 150 palabras que explique cómo funciona la fotosíntesis."
STABILITY_TOKENS = 128
WINDOW = 16          # tokens por ventana para medir la velocidad a lo largo de la generación
STABLE_RATIO = 0.7   # estable si la ventana más lenta rinde al menos el 70% de la mediana (heurística)


def stability_stats(stamps, window=WINDOW):
    """stamps: instantes (s) de llegada de cada token. Devuelve la velocidad por ventanas o None si hay pocos datos."""
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
    """Genera una respuesta midiendo TTFT y el instante de cada token. Devuelve un dict de métricas."""
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
    hardware._vram_cache["t"] = 0  # forzar lectura fresca
    vu = hardware.vram_usage()
    mem.update(vram_used_mib=vu["used_mib"] if vu else None, vram_total_mib=vu["total_mib"] if vu else None)
    return mem


def run(client, model, keep_alive="10m", long=False, cold=True, emit=None, num_ctx=None):
    """Ejecuta el benchmark. `emit` recibe eventos {'type': 'stage', ...} para mostrar el avance."""
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

    # 1) Conexión con Ollama
    stage("connection", "running")
    t = time.perf_counter()
    try:
        report["ollama_version"] = client.version()
        names = {normalize_model(m["name"]) for m in client.models()}
    except OllamaError as e:
        return fail("connection", "install", e)
    report["phases"]["connection"] = {"ok": True, "ms": round((time.perf_counter() - t) * 1000)}
    stage("connection", "ok", detail="Ollama %s" % report["ollama_version"])

    # 2) El modelo está descargado
    if normalize_model(model) not in names:
        report["phases"]["model"] = {"ok": False}
        info = {"phase": "install", "title": "El modelo «%s» no está descargado" % model,
                "hint": "Abrí el asistente (botón ⇩) y descargalo, o ejecutá: python -m quickzap pull %s" % model,
                "technical": "model not found", "matched": True}
        report["errors"].append(info)
        stage("model", "error", **info)
        return report
    report["phases"]["model"] = {"ok": True}
    stage("model", "ok", detail=model)

    # 3) Carga en memoria (en frío: se descarga primero para medir el tiempo real)
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

    # 4) Generación real de texto
    stage("generation", "running")
    try:
        g = _generate(client, model, SHORT_PROMPT, {**options, "temperature": 0, "num_predict": 16}, keep_alive)
    except OllamaError as e:
        return fail("generation", "generation", e)
    g.pop("stamps")
    g["ok"] = bool(g["reply"])
    report["phases"]["generation"] = g
    if not g["ok"]:
        return fail("generation", "generation", "El modelo no devolvió texto.")
    stage("generation", "ok", detail="«%s»" % g["reply"][:40], tps=g["tps"], ttft_ms=g["ttft_ms"])

    # 5) Memoria
    report["memory"] = _memory(client, model)
    stage("memory", "ok")

    # 6) Estabilidad en una generación más larga (opcional: puede tardar en equipos modestos)
    if long:
        stage("stability", "running")
        try:
            s = _generate(client, model, LONG_PROMPT, {**options, "temperature": 0.7, "num_predict": STABILITY_TOKENS}, keep_alive)
        except OllamaError as e:
            return fail("stability", "generation", e)
        stats = stability_stats(s["stamps"])
        report["stability"] = {"tokens": s["tokens"], "tps": s["tps"], "total_s": round(s["total_ms"] / 1000, 1), **(stats or {"stable": None})}
        stage("stability", "ok", detail="estable" if report["stability"].get("stable") else "irregular")
    report["ok"] = True
    return report
