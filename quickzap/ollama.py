"""Cliente mínimo de la API HTTP de Ollama (solo biblioteca estándar)."""
import json
import urllib.error
import urllib.request

from .config import MODEL_RE


class OllamaError(Exception):
    def __init__(self, message, status=None, unreachable=False):
        super().__init__(message)
        self.status = status
        self.unreachable = unreachable


def normalize_host(host):
    host = (host or "").strip().rstrip("/") or "127.0.0.1:11434"
    if "://" not in host:
        host = "http://" + host
    return host.replace("//0.0.0.0", "//127.0.0.1")


def valid_model_name(name):
    return isinstance(name, str) and bool(MODEL_RE.match(name))


def normalize_model(name):
    return name if ":" in name else name + ":latest"


class OllamaClient:
    def __init__(self, host=None):
        self.host = normalize_host(host)

    def _open(self, path, payload=None, method=None, timeout=10):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            self.host + path, data=data, method=method or ("POST" if data else "GET"),
            headers={"Content-Type": "application/json"})
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            try:
                message = json.loads(body).get("error", body)
            except ValueError:
                message = body or str(e)
            raise OllamaError(message, status=e.code)
        except (urllib.error.URLError, OSError):
            raise OllamaError("No se pudo conectar con Ollama en " + self.host, unreachable=True)

    def _json(self, path, **kw):
        with self._open(path, **kw) as r:
            return json.loads(r.read().decode("utf-8"))

    def _stream(self, path, payload, timeout):
        resp = self._open(path, payload, timeout=timeout)
        try:
            for line in resp:
                line = line.strip()
                if line:
                    yield json.loads(line)
        except (OSError, ValueError) as e:
            raise OllamaError("Se interrumpió la conexión con Ollama: %s" % e, unreachable=True)
        finally:
            resp.close()

    def version(self):
        return self._json("/api/version", timeout=2).get("version")

    def models(self):
        return self._json("/api/tags", timeout=5).get("models", [])

    def running(self):
        try:
            return self._json("/api/ps", timeout=5).get("models", [])
        except OllamaError:
            return []

    def load(self, model, keep_alive="10m"):
        """Carga el modelo en memoria sin generar texto. Devuelve la respuesta de Ollama (con load_duration en ns)."""
        return self._json("/api/generate", payload={"model": model, "prompt": "", "stream": False,
                                                    "keep_alive": keep_alive}, timeout=300)

    def unload(self, model):
        self._json("/api/generate", payload={"model": model, "stream": False, "keep_alive": 0}, timeout=30)

    def chat(self, model, messages, options=None, keep_alive="10m"):
        payload = {"model": model, "messages": messages, "stream": True,
                   "options": options or {}, "keep_alive": keep_alive}
        # El timeout es por inactividad: la primera respuesta incluye la carga del modelo.
        return self._stream("/api/chat", payload, timeout=300)

    def pull(self, model):
        return self._stream("/api/pull", {"model": model, "stream": True}, timeout=300)


class PullProgress:
    """Convierte los eventos de /api/pull (uno por capa del modelo) en un porcentaje global que nunca retrocede."""

    def __init__(self):
        self.layers = {}
        self.last = 0

    def update(self, chunk):
        digest, total = chunk.get("digest"), chunk.get("total")
        if digest and total:
            done = max(chunk.get("completed") or 0, self.layers.get(digest, (0, 0))[1])
            self.layers[digest] = (total, min(done, total))
        total_all = sum(t for t, _ in self.layers.values())
        done_all = sum(c for _, c in self.layers.values())
        status = chunk.get("status", "")
        percent = None
        if status == "success":
            percent = 100
        elif total_all:
            percent = max(self.last, min(99, int(100 * done_all / total_all)))
        if percent is not None:
            self.last = percent
        return {"status": status, "percent": percent,
                "completed": done_all or None, "total": total_all or None}
