# Contributing to QuickZap

Thank you for wanting to help! QuickZap aims to be a fast, easy-to-install local AI assistant that is also useful on modest hardware.

## Setting Up the Environment

```bash
git clone https://github.com/Enzo-sh/Quickzap.git
cd Quickzap

python -m unittest discover -s tests -t . -v  # No dependencies or GPU required
python scripts/check_secrets.py              # Should report "No findings."
```

Browser tests are optional:

```bash
pip install playwright
playwright install chromium
python -m tests.e2e_wizard
```

## Principles

- **No external dependencies** in the application code (standard library only). If a feature genuinely requires them, they must be optional and documented in `THIRD_PARTY.md`.
- **No remote resources** in the interface (CDNs, fonts, scripts): QuickZap must work without an Internet connection.
- **Never declare a feature complete if it only has a user interface.** Every change must include tests; error cases matter just as much as successful ones.
- **Numbers must come from measurements**, not assumptions. The rules in `hardware.py` are heuristics that we want to replace with real-world data.
- User-facing messages must be clear and written in English, with a suggestion explaining what to do next.

## Pull Requests

1. One idea per PR, with a description of what changes and why.
2. `python -m unittest discover -s tests -t . -v` must pass, and `python scripts/check_secrets.py` must report no findings.
3. If visible behavior changes, update `CHANGELOG.md` (under the *Unreleased* section) and the documentation.
4. Never include API keys, personal file paths, or data from your conversations.

## Adding a Model to the Catalog

Edit `FAMILIES` in `quickzap/hardware.py` (exact Ollama name, actual parameters, and license), then regenerate the table:

```bash
python -m quickzap models --markdown
```

Paste the output into `docs/MODELS.md`.

Verify that quantization tags (`<model>-instruct-q5_K_M`, `-q8_0`) exist in the Ollama library: a test compares `docs/MODELS.md` against the catalog.

## Contributing Benchmarks

Real-world benchmarks from different computers are the most valuable contributions you can make.

Instructions and methodology are available in [docs/BENCHMARKS.md](https://github.com/Enzo-sh/Quickzap/blob/main/docs/BENCHMARKS.md).

Run:

```bash
python -m quickzap bench --quality
```

Then submit the JSON file from `benchmarks/` in a PR. The report does not contain personal data (you can open it and verify this yourself).

## Reporting an Issue

Include the output of:

```bash
python -m quickzap hardware
python -m quickzap doctor
```

Also explain what you expected to happen.

See [docs/TROUBLESHOOTING.md](https://github.com/Enzo-sh/Quickzap/blob/main/docs/TROUBLESHOOTING.md).
