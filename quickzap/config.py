"""Rutas y valores por defecto. Los ajustes del usuario viven en SQLite (ver db.py)."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("QUICKZAP_DATA", ROOT / "data"))

DEFAULTS = {
    "model": "qwen2.5:7b",
    "temperature": 0.7,
    "personality": "Amable, claro y directo.",
    "context_messages": 20,
    "ollama_host": os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
    "keep_alive": "10m",
    "num_ctx": 4096,  # contexto acotado: memoria predecible en equipos modestos
}

# Instrucciones del sistema: separadas del historial y de cualquier contenido externo.
SYSTEM_PROMPT = (
    "Sos Quickzap, un asistente conversacional que corre en la computadora del usuario. "
    "Respondé en el mismo idioma en que te escriben (por defecto, español). "
    "Cuando incluyas funciones o código, escribilos en bloques de código Markdown indicando el lenguaje "
    "(por ejemplo ```python o ```javascript), sin texto explicativo dentro del bloque. "
    "Personalidad: {personality} "
    "Si no sabés algo o no estás seguro, decilo con claridad en lugar de inventar datos, "
    "cifras, citas o referencias. Fecha de hoy: {today}."
)

MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,100}$")
KEEP_ALIVE_RE = re.compile(r"^(-1|0|\d{1,4}[smh])$")
