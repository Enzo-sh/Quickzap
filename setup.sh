#!/usr/bin/env bash
# Instala y configura Ollama + un modelo para Quickzap (Linux / macOS).
# Uso: ./setup.sh [modelo|auto]
set -euo pipefail
cd "$(dirname "$0")"
MODEL="${1:-auto}"
step() { printf '\n==> %s\n' "$1"; }

step "1/5 Python 3.9 o superior"
command -v python3 >/dev/null || { echo "Falta python3. Instalalo con tu gestor de paquetes."; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' || { echo "Se necesita Python 3.9+."; exit 1; }
PY=python3

step "2/5 Ollama"
if ! command -v ollama >/dev/null; then
  case "$(uname -s)" in
    Linux)  curl -fsSL https://ollama.com/install.sh | sh ;;
    Darwin) if command -v brew >/dev/null; then brew install ollama; else echo "Instala Ollama desde https://ollama.com/download y reintenta."; exit 1; fi ;;
    *) echo "Sistema no soportado por este script."; exit 1 ;;
  esac
fi
echo "Ollama: $(command -v ollama)"

step "3/5 Iniciando el servicio de Ollama"
up() { curl -fs --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; }
if ! up; then
  nohup ollama serve >"${TMPDIR:-/tmp}/ollama.log" 2>&1 &
  for _ in $(seq 1 30); do up && break; sleep 1; done
  up || { echo "Ollama no respondio. Revisa ${TMPDIR:-/tmp}/ollama.log"; exit 1; }
fi

step "4/5 Descargando el modelo"
[ "$MODEL" = "auto" ] && MODEL="$($PY -m quickzap recommend --plain)"
echo "Modelo: $MODEL"
$PY -m quickzap pull "$MODEL"

step "5/5 Verificacion"
$PY -m quickzap doctor

mkdir -p data && printf '{"install_seconds": %d}\n' "$SECONDS" > data/install_timing.json   # para los informes de benchmark
printf '\nListo. Inicia Quickzap con:  python3 -m quickzap\n'
