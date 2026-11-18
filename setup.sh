#!/usr/bin/env bash
# Installs and configures Ollama + a model for Quickzap (Linux / macOS).
# Usage: ./setup.sh [model|auto]
set -euo pipefail
cd "$(dirname "$0")"
MODEL="${1:-auto}"
step() { printf '\n==> %s\n' "$1"; }

step "1/5 Python 3.9 or later"
command -v python3 >/dev/null || { echo "python3 is missing. Install it with your package manager."; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' || { echo "Python 3.9+ is required."; exit 1; }
PY=python3

step "2/5 Ollama"
if ! command -v ollama >/dev/null; then
  case "$(uname -s)" in
    Linux)  curl -fsSL https://ollama.com/install.sh | sh ;;
    Darwin) if command -v brew >/dev/null; then brew install ollama; else echo "Install Ollama from https://ollama.com/download and try again."; exit 1; fi ;;
    *) echo "System not supported by this script."; exit 1 ;;
  esac
fi
echo "Ollama: $(command -v ollama)"

step "3/5 Starting the Ollama service"
up() { curl -fs --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; }
if ! up; then
  nohup ollama serve >"${TMPDIR:-/tmp}/ollama.log" 2>&1 &
  for _ in $(seq 1 30); do up && break; sleep 1; done
  up || { echo "Ollama did not respond. Check ${TMPDIR:-/tmp}/ollama.log"; exit 1; }
fi

step "4/5 Downloading the model"
[ "$MODEL" = "auto" ] && MODEL="$($PY -m quickzap recommend --plain)"
echo "Model: $MODEL"
$PY -m quickzap pull "$MODEL"

step "5/5 Verification"
$PY -m quickzap doctor

mkdir -p data && printf '{"install_seconds": %d}\n' "$SECONDS" > data/install_timing.json   # for benchmark reports
printf '\nDone. Start Quickzap with:  python3 -m quickzap\n'
