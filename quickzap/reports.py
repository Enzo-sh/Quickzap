"""Informes de benchmark: nombres de archivo, tabla comparativa y documentación de modelos."""
import re

from . import hardware


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:40] or "x"


def default_filename(report):
    gpus = report["hardware"].get("gpus") or []
    machine = gpus[0]["name"] if gpus else report["hardware"]["cpu"]["name"]
    return "%s_%s_%s.json" % (report["created"][:10], slug(machine), slug(report["model"]))


def _dash(v, fmt="%s"):
    return "—" if v is None else fmt % v


def row(report):
    hw, ph = report["hardware"], report["phases"]
    gpu = (hw.get("gpus") or [None])[0]
    mem, st, q = report.get("memory") or {}, report.get("stability"), report.get("quality")
    return [report["created"][:10], hw["cpu"]["name"], _dash(hw["ram"].get("total_gb"), "%s GB"),
            "%s (%.0f GB)" % (gpu["name"], gpu["vram_total_mib"] / 1024) if gpu else "sin GPU",
            report["model"], _dash(ph.get("load", {}).get("seconds"), "%.1f"), _dash(ph.get("generation", {}).get("ttft_ms")),
            _dash(ph.get("generation", {}).get("tps"), "%.1f"), _dash(mem.get("vram_gb"), "%.1f"), _dash(mem.get("ram_gb"), "%.1f"),
            "—" if not st or st.get("stable") is None else ("sí" if st["stable"] else "no"),
            "—" if not q else "%d/%d" % (q["score"], q["total"]),
            _dash(report.get("install_seconds"), "%d"), _dash(report.get("startup_ms")),
            "verificado" if report.get("online") is False and report["ok"] else "—"]


HEADERS = ["Fecha", "CPU", "RAM", "GPU", "Modelo", "Carga (s)", "1.er token (ms)", "Tokens/s", "VRAM modelo (GB)",
           "RAM modelo (GB)", "Estable", "Calidad", "Instalación (s)", "Inicio (ms)", "Sin Internet"]


def compare_markdown(reports):
    ok = [r for r in reports if r.get("ok")]
    rows = sorted((row(r) for r in ok), key=lambda x: (x[1], x[4]))
    lines = ["| " + " | ".join(HEADERS) + " |", "|" + "---|" * len(HEADERS)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    skipped = len(reports) - len(ok)
    if skipped:
        lines.append("\n_%d informe(s) con errores no se incluyen en la tabla._" % skipped)
    return "\n".join(lines)


def models_markdown():
    """Tabla de modelos compatibles. docs/MODELS.md se genera con: python -m quickzap models --markdown"""
    lines = ["| Modelo | Parámetros | Descarga Q4 (por defecto) | Q5 | Q8 | Memoria estimada Q4 / Q5 / Q8 | Licencia | Nota |",
             "|---|---|---|---|---|---|---|---|"]
    for f in hardware.FAMILIES:
        tags = ["`%s`" % hardware.tag_for(f["id"], q) for q in hardware.QUANTS]
        sizes = " / ".join("%.1f" % hardware.need_gb(f["params_b"], q) for q in hardware.QUANTS)
        dl = "~%.1f GB" % (f["params_b"] * hardware.QUANTS["q4_K_M"]["bpp"])
        lines.append("| %s | %.1fB | %s %s | %s | %s | %s GB | %s | %s |" % (
            f["label"], f["params_b"], tags[0], dl, tags[1], tags[2], sizes, f["license"], f["note"]))
    return "\n".join(lines)
