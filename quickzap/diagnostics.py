"""Translates technical Ollama errors into understandable messages and classifies them by phase:
install (Ollama or model not installed), download, load (loading into memory), and generation."""
import re

RULES = [
    (r"could not connect|connection refused|actively refused|connectex|no route to host|unreachable",
     "install", "Could not connect to Ollama",
     "Ollama is not running. Click “Start Ollama” or open the Ollama app."),
    (r"requires more system memory|out of memory|cudamalloc|insufficient memory|unable to allocate|memory layout cannot be allocated|exceeds available",
     "load", "The model does not fit in your computer's memory",
     "Choose a smaller model or the Q4 quantization, and close other programs that use a lot of memory."),
    (r"no space left|enospc|not enough space|disk full|insufficient disk|disk space",
     "download", "Not enough disk space",
     "Free up space (a model takes several GB) and click Retry."),
    (r"timed? ?out|timeout|eof|connection reset|dial tcp|no such host|temporary failure|tls|network is unreachable|interrupted",
     "download", "The Internet connection was interrupted",
     "Check your connection and click Retry: the download resumes where it left off."),
    (r"pull model manifest|manifest.*(not found|does not exist)|file does not exist|model .* not found",
     "download", "Could not find that model in the Ollama library",
     "Check the model name (for example qwen2.5:7b) and try again."),
    (r"permission denied|access is denied|no permissions|not permitted|administrator",
     "install", "Missing permissions",
     "Accept the Windows permission prompt when it appears, or install Ollama manually from ollama.com/download."),
]
DEFAULT_HINT = "Try again. If it keeps failing, run “python -m quickzap doctor” and check docs/TROUBLESHOOTING.md."


def explain(message, phase=None):
    """Returns {'phase', 'title', 'hint', 'technical', 'matched'}."""
    text = str(message or "")
    for pattern, rule_phase, title, hint in RULES:
        if re.search(pattern, text, re.I):
            return {"phase": rule_phase if phase in (None, "generation", "load") else phase, "title": title,
                    "hint": hint, "technical": text, "matched": True}
    return {"phase": phase or "generation", "title": "An error occurred", "hint": DEFAULT_HINT,
            "technical": text, "matched": False}
