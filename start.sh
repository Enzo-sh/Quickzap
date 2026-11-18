#!/usr/bin/env bash
# Starts Quickzap (Linux / macOS). The first time, the installation wizard opens in the browser.
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Python 3.9 or later (python3) is missing."; exit 1; }
exec python3 -m quickzap "$@"
