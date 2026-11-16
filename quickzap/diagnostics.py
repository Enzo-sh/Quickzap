"""Traduce errores técnicos de Ollama a mensajes comprensibles y los clasifica por fase:
install (Ollama o modelo sin instalar), download (descarga), load (carga en memoria) y generation."""
import re

RULES = [
    (r"no se pudo conectar|connection refused|actively refused|connectex|no route to host|unreachable",
     "install", "No se pudo conectar con Ollama",
     "Ollama no está iniciado. Tocá «Iniciar Ollama» o abrí la aplicación de Ollama."),
    (r"requires more system memory|out of memory|cudamalloc|insufficient memory|unable to allocate|memory layout cannot be allocated|exceeds available",
     "load", "El modelo no entra en la memoria de tu equipo",
     "Elegí un modelo más chico o la cuantización Q4, y cerrá otros programas que usen mucha memoria."),
    (r"no space left|enospc|not enough space|disk full|insufficient disk|espacio en disco",
     "download", "No hay espacio suficiente en el disco",
     "Liberá espacio (un modelo ocupa varios GB) y tocá Reintentar."),
    (r"timed? ?out|timeout|eof|connection reset|dial tcp|no such host|temporary failure|tls|network is unreachable|se interrumpió",
     "download", "Se cortó la conexión a Internet",
     "Revisá tu conexión y tocá Reintentar: la descarga continúa desde donde quedó."),
    (r"pull model manifest|manifest.*(not found|does not exist)|file does not exist|model .* not found",
     "download", "No encontré ese modelo en la biblioteca de Ollama",
     "Revisá el nombre del modelo (por ejemplo qwen2.5:7b) y probá de nuevo."),
    (r"permission denied|access is denied|acceso denegado|sin permiso|administrator|not permitted",
     "install", "Faltan permisos",
     "Aceptá el permiso de Windows cuando lo pida, o instalá Ollama a mano desde ollama.com/download."),
]
DEFAULT_HINT = "Probá de nuevo. Si sigue fallando, ejecutá «python -m quickzap doctor» y mirá docs/TROUBLESHOOTING.md."


def explain(message, phase=None):
    """Devuelve {'phase', 'title', 'hint', 'technical', 'matched'}."""
    text = str(message or "")
    for pattern, rule_phase, title, hint in RULES:
        if re.search(pattern, text, re.I):
            return {"phase": rule_phase if phase in (None, "generation", "load") else phase, "title": title,
                    "hint": hint, "technical": text, "matched": True}
    return {"phase": phase or "generation", "title": "Ocurrió un error", "hint": DEFAULT_HINT,
            "technical": text, "matched": False}
