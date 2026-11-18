"""Paths and default values. User settings live in SQLite (see db.py)."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("QUICKZAP_DATA", ROOT / "data"))

DEFAULTS = {
    "model": "qwen2.5:7b",
    "temperature": 0.7,
    "personality": "Friendly, clear, and direct.",
    "context_messages": 20,
    "ollama_host": os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
    "keep_alive": "10m",
    "num_ctx": 4096,  # bounded context: predictable memory on modest computers
}

# System instructions: kept separate from history and any external content.
SYSTEM_PROMPT = (
    "You are Quickzap, a conversational assistant that runs on the user's computer. "
    "Respond in the same language the user writes in (default: English). "
    "When including functions or code, write them in Markdown code blocks with the language specified "
    "(for example ```python or ```javascript), with no explanatory text inside the block. "
    "Personalidad: {personality} "
    "If you do not know something or are not sure, say so clearly instead of making up data, "
    "figures, quotes, or references. Today's date: {today}."
)

MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,100}$")
KEEP_ALIVE_RE = re.compile(r"^(-1|0|\d{1,4}[smh])$")
