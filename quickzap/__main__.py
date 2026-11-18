import argparse
import json
import sys
import time
from pathlib import Path

from . import benchmark, config, db, doctor, evals, hardware, reports
from .ollama import OllamaClient, OllamaError, PullProgress, valid_model_name


def pull(model):
    db.init()
    settings = db.get_settings()
    model = model or settings["model"]
    if not valid_model_name(model):
        print("Invalid model name.")
        return 2
    client = OllamaClient(settings["ollama_host"])
    try:
        client.version()
        progress, last = PullProgress(), None
        for chunk in client.pull(model):
            if chunk.get("error"):
                raise OllamaError(chunk["error"])
            info = progress.update(chunk)
            pct = info["percent"]
            if pct is None:
                line = info["status"]
            else:
                filled = pct // 5
                line = "[%s%s] %3d%%  %.1f / %.1f GB" % ("#" * filled, "-" * (20 - filled), pct,
                                                      (info["completed"] or 0) / 1e9, (info["total"] or 0) / 1e9)
            if line != last:
                print("\r" + line.ljust(60), end="", flush=True)
                last = line
        print("\nModel “%s” ready." % model)
    except OllamaError as e:
        from .diagnostics import explain
        info = explain(str(e), "download")
        print("\nError: %s\n  -> %s" % (info["title"] if info["matched"] else e, info["hint"]))
        return 1
    db.update_settings({"model": model})
    return 0


def show_hardware(as_json):
    hw = hardware.snapshot()
    if as_json:
        print(json.dumps(hw, indent=2, ensure_ascii=False))
        return 0
    r, cpu = hw["ram"], hw["cpu"]
    print("Sistema : %s" % hw["os"])
    print("CPU     : %s (%s threads)" % (cpu["name"], cpu["threads"]))
    print("RAM     : %s GB total, %s GB available" % (r["total_gb"], r["available_gb"]))
    for g in hw["gpus"] or []:
        print("GPU     : %s · %.1f GB of VRAM%s" % (g["name"], g["vram_total_mib"] / 1024, " (estimated)" if g["estimated"] else ""))
    if not hw["gpus"]:
        print("GPU     : no compatible GPU detected (CPU will be used)")
    rec = hardware.recommend(hw)
    print("\nRecommended: %s (%s) · %s" % (rec["model"], hardware.QUANTS[rec["quant"]]["short"], rec["reason"]))
    if rec["warning"]:
        print("Warning: %s" % rec["warning"])
    return 0


def bench(args):
    db.init()
    s = db.get_settings()
    model = args.model or s["model"]
    client = OllamaClient(s["ollama_host"])
    from . import server
    t = time.perf_counter()
    httpd = server.make_server(port=0)
    httpd.server_close()
    startup_ms = round((time.perf_counter() - t) * 1000)

    names = {"connection": "Ollama connection", "model": "Model downloaded", "load": "Model load",
             "generation": "Text generation", "memory": "Memory usage", "stability": "Stability"}

    def show(event):
        if event["type"] == "stage" and event["status"] in ("ok", "error"):
            print("  [%s] %s%s" % ("OK" if event["status"] == "ok" else "X ", names[event["stage"]],
                                   " — " + event["detail"] if event.get("detail") else ""))
        elif event["type"] == "eval":
            print("  quality %d/%d" % (event["done"], event["total"]), end="\r")

    print("Benchmark of “%s”%s…" % (model, " (quick)" if args.quick else " (includes stability test)"))
    report = benchmark.run(client, model, s["keep_alive"], long=not args.quick, emit=show, num_ctx=s["num_ctx"])
    report["startup_ms"] = startup_ms
    report["online"] = server.internet_now()
    timing = config.DATA_DIR / "install_timing.json"
    if timing.is_file():
        try:
            report["install_seconds"] = json.loads(timing.read_text())["install_seconds"]
        except (ValueError, KeyError, OSError):
            pass
    if args.quality and report["ok"]:
        report["quality"] = evals.run(client, model, s["keep_alive"], emit=show)
        print("  [OK] Quality: %d/%d correct answers" % (report["quality"]["score"], report["quality"]["total"]))
    for err in report["errors"]:
        print("\nError (%s): %s\n  -> %s" % (err["phase"], err["title"], err["hint"]))
    if report["ok"]:
        g, m = report["phases"]["generation"], report["memory"]
        print("\nSummary: %s tokens/s · first token %s ms · load %.1f s · model %s GB (%s%% on GPU)" % (
            g["tps"], g["ttft_ms"], report["phases"]["load"]["seconds"], m["model_gb"], m["gpu_percent"]))
        if report["stability"]:
            st = report["stability"]
            print("Stability: %s (min %s / median %s tokens/s)" % ("stable" if st.get("stable") else "irregular", st.get("tps_min"), st.get("tps_median")))
    db.save_benchmark(report)
    if not args.no_save:
        out = Path(args.out) if args.out else config.ROOT / "benchmarks" / reports.default_filename(report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("\nReport saved to %s\nYou can share it in a Pull Request (see docs/BENCHMARKS.md). It contains no personal data." % out)
    return 0 if report["ok"] else 1


def compare(files):
    loaded = []
    for pattern in files:
        for f in sorted(Path().glob(pattern)) if not Path(pattern).is_file() else [Path(pattern)]:
            try:
                loaded.append(json.loads(f.read_text(encoding="utf-8")))
            except (ValueError, OSError) as e:
                print("Could not read %s: %s" % (f, e), file=sys.stderr)
    if not loaded:
        print("No reports found.")
        return 1
    print(reports.compare_markdown(loaded))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="quickzap", description="Local AI assistant powered by Ollama.")
    p.add_argument("--port", type=int, default=8765, help="Application port (default 8765).")
    p.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    sub = p.add_subparsers(dest="cmd")
    serve = sub.add_parser("serve", help="Starts the application (default).")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--no-browser", action="store_true")
    sub.add_parser("doctor", help="Checks Ollama, the model, and the GPU.")
    pl = sub.add_parser("pull", help="Downloads a model and selects it.")
    pl.add_argument("model", nargs="?")
    rec = sub.add_parser("recommend", help="Suggests a model based on your hardware.")
    rec.add_argument("--plain", action="store_true", help="Prints only the model name.")
    hw = sub.add_parser("hardware", help="Shows detected CPU, RAM, and GPU.")
    hw.add_argument("--json", action="store_true")
    b = sub.add_parser("bench", help="Measures speed, first token, memory, and stability; saves a report.")
    b.add_argument("--model")
    b.add_argument("--quick", action="store_true", help="Skips the stability test.")
    b.add_argument("--quality", action="store_true", help="Adds the quality battery (8 questions).")
    b.add_argument("--out", help="Path of the JSON report (default: benchmarks/).")
    b.add_argument("--no-save", action="store_true")
    bc = sub.add_parser("bench-compare", help="Compares reports and generates a Markdown table.")
    bc.add_argument("files", nargs="+")
    md = sub.add_parser("models", help="Lists the compatible models (Markdown).")
    md.add_argument("--markdown", action="store_true")
    args = p.parse_args(argv)

    if args.cmd == "doctor":
        return doctor.run()
    if args.cmd == "pull":
        return pull(args.model)
    if args.cmd == "recommend":
        r = hardware.recommend()
        print(r["model"] if args.plain else "%s (%s) · %s" % (r["model"], hardware.QUANTS[r["quant"]]["short"], r["reason"]))
        return 0
    if args.cmd == "hardware":
        return show_hardware(args.json)
    if args.cmd == "bench":
        return bench(args)
    if args.cmd == "bench-compare":
        return compare(args.files)
    if args.cmd == "models":
        print(reports.models_markdown())
        return 0
    from .server import serve as run_server
    return run_server(port=getattr(args, "port", 8765), open_browser=not getattr(args, "no_browser", False))


if __name__ == "__main__":
    sys.exit(main())
