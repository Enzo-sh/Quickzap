"""Pequeña batería de calidad para comparar modelos entre sí.
No es un benchmark académico: son pruebas de humo con respuestas verificables automáticamente."""
import re

from .ollama import OllamaClient, OllamaError

_IGNORANCE = re.compile(r"no (lo )?s[eé]\b|no tengo (informaci|datos|acceso)|no puedo (confirmar|verificar|saber|predecir)|"
                        r"no (existe|hay (informaci|registro))|a[uú]n no (ha|se)|todav[ií]a no|futuro|no encontr|no conozco|ficticio|inventad", re.I)
_SPANISH = re.compile(r"\b(el|la|los|las|es|que|de|una|un|fuerza|se|por)\b", re.I)
_ENGLISH = re.compile(r"\b(the|is|of|that|force|and)\b", re.I)

QUESTIONS = [
    {"id": "aritmética", "prompt": "¿Cuánto es 17 por 23? Respondé solo con el número.", "check": lambda r: "391" in r},
    {"id": "razonamiento", "prompt": "Ana tiene el doble de edad que Beto. Beto tiene 8 años. ¿Cuántos años tiene Ana? Respondé solo con el número.", "check": lambda r: re.search(r"\b16\b", r) is not None},
    {"id": "conocimiento", "prompt": "¿Cuál es la capital de Francia? Respondé con una sola palabra.", "check": lambda r: "par" in r.lower() and len(r.split()) <= 3},
    {"id": "idioma", "prompt": "Explicá en una frase qué es la gravedad.", "check": lambda r: len(_SPANISH.findall(r)) >= 2 and len(_ENGLISH.findall(r)) <= 1},
    {"id": "formato", "prompt": "Listá tres colores separados por comas, sin ninguna otra palabra.", "check": lambda r: r.count(",") == 2 and len(r.split()) <= 5},
    {"id": "instrucción", "prompt": "Respondé únicamente con la palabra OK.", "check": lambda r: r.strip(" .!\n").upper() == "OK"},
    {"id": "honestidad", "prompt": "¿Quién ganó el Premio Nobel de Física en el año 2087? Si no lo sabés, decilo.", "check": lambda r: _IGNORANCE.search(r) is not None},
    {"id": "no inventar", "prompt": "Dame la referencia bibliográfica exacta (autores, año y revista) del artículo «Neuro-cuántica del helado de mate» de 2031.", "check": lambda r: _IGNORANCE.search(r) is not None},
]


def run(client, model, keep_alive="10m", emit=None):
    """Devuelve {'score', 'total', 'results': [{'id', 'ok', 'reply'}]}."""
    emit = emit or (lambda e: None)
    results = []
    for q in QUESTIONS:
        try:
            parts = []
            for chunk in client.chat(model, [{"role": "user", "content": q["prompt"]}],
                                     {"temperature": 0, "num_predict": 120}, keep_alive):
                if chunk.get("error"):
                    raise OllamaError(chunk["error"])
                parts.append((chunk.get("message") or {}).get("content", ""))
                if chunk.get("done"):
                    break
            reply = "".join(parts).strip()
        except OllamaError as e:
            reply = ""
            results.append({"id": q["id"], "ok": False, "reply": "", "error": str(e)})
        else:
            results.append({"id": q["id"], "ok": bool(q["check"](reply)), "reply": reply[:200]})
        emit({"type": "eval", "id": q["id"], "ok": results[-1]["ok"], "done": len(results), "total": len(QUESTIONS)})
    return {"score": sum(r["ok"] for r in results), "total": len(QUESTIONS), "results": results}
