#!/usr/bin/env bash
# Inicia Quickzap (Linux / macOS). La primera vez se abre el asistente de instalacion en el navegador.
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Falta Python 3.9 o superior (python3)."; exit 1; }
exec python3 -m quickzap "$@"
