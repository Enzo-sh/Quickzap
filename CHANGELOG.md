# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-11-15

### Added
- CPU, RAM (total and available), GPU, and VRAM detection; on Apple Silicon, unified memory is estimated.
- Model and quantization recommendation (Q4/Q5/Q8) based on available resources; never recommends a model that does not fit. Lightweight models (0.5B, 1.5B) for modest computers.
- Phase-by-phase benchmark: connection, model, cold load, real generation, memory, stability; tokens/s and time to first token.
- Errors classified into installation / download / model load / generation, with suggestions; retry at every wizard stage.
- Statistics panel (▦) and comparison of measured models.
- Per-reply metrics (tokens/s, first token, total time) saved in SQLite.
- `hardware`, `bench`, `bench-compare`, and `models` commands; 8-question quality battery (`bench --quality`).
- `num_ctx` setting (4096 by default) for predictable memory.
- Publishing documentation: README, CONTRIBUTING, troubleshooting guide, models, benchmarks, third-party licenses, secret scanner.

### Changed
- Internet status is checked in the background and never blocks `/api/status` (it could previously take up to 1.5 s offline); "checking" is shown while the status is unknown.
- The wizard's "Test" step uses the benchmark; the "The model replied: …" message is kept.
- If the port is busy, a message with the solution is shown instead of a technical error.

### Removed
- `/api/setup/test` endpoint (replaced by `/api/benchmark`).

## [0.1.0] - 2026-11-14

### Added
- Local chat with Ollama, history in SQLite, model selector, download with progress bar.
- Installation wizard (Ollama, model, test), `doctor`, `setup.ps1` / `setup.sh` installers, double-click launcher.
- Protection against cross-origin requests (Host/Origin).
