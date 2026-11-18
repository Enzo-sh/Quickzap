# Benchmarks

QuickZap does not set arbitrary minimum requirements: the recommendations in [`hardware.py`](../quickzap/hardware.py) are **estimates**
and we want to replace them with **real measurements from different computers**. This document explains how to measure and how to contribute.

## What is measured

| Metric | How it is obtained |
|---|---|
| Installation time | Recorded by `setup.ps1` / `setup.sh` in `data/install_timing.json` (empty if you used the wizard) |
| Startup time | Importing the server + opening the database + binding the port (`startup_ms`) |
| Recommended model | Output of the recommendation for that hardware |
| Load time | The model is unloaded and loaded again, measuring the real time (cold) |
| Tokens per second | `eval_count / eval_duration` reported by Ollama (excludes prompt processing) |
| Time to first token | From sending the request to the first text received (with the model already loaded) |
| RAM and VRAM | Model size and GPU/RAM split according to Ollama's `/api/ps`, plus system RAM and VRAM |
| Stability | 128-token generation; speed in 16-token windows. "Stable" = slowest window ≥ 70% of the median (heuristic threshold) |
| Quality | 8 questions with verifiable answers (arithmetic, reasoning, language, format, instruction, honesty, no fabrication). It is a smoke test, **not an academic benchmark** |
| Offline operation | The report records whether there was Internet; with the network disconnected and `ok`, the "Offline" column says *verified* |

## How to run it

1. Close heavy programs and, if it is a laptop, plug it in.
2. To demonstrate offline operation, **disconnect the Internet** (the model must already be downloaded).
3. Run it, ideally 2–3 times, and keep the most representative run:

```bash
python -m quickzap bench --quality
```

It generates `benchmarks/YYYY-MM-DD_<gpu-or-cpu>_<model>.json`. It is a text file: you can open it to verify it contains no
personal data (it includes CPU, RAM, GPU, Ollama version, and results; it does **not** include user or machine names).

## Compare

```bash
python -m quickzap bench-compare "benchmarks/*.json"
```

Prints a Markdown table (only successful reports) with CPU, RAM, GPU, model, load, first token, tokens/s, model VRAM/RAM,
stability, quality, installation, startup, and offline verification.

## How to contribute

Send a *Pull Request* adding your JSON in `benchmarks/` (see [CONTRIBUTING](../CONTRIBUTING.md)). If something went wrong, the report is
useful too: errors are separated into installation, model load, and generation (those are not included in the comparison table).

With the collected data, the constants in `hardware.py` (`RESERVE_VRAM_GB`, `RESERVE_RAM_GB`, `CPU_ONLY_MAX_PARAMS_B`,
bytes per parameter) will be adjusted and an evidence-based recommendation table will be published.

## Results

There are no published reports yet. This section will be filled with the `bench-compare` table once they exist.
