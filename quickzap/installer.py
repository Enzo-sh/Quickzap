"""Detección, instalación e inicio de Ollama para el asistente de la interfaz.
Solo ejecuta comandos fijos (nunca texto que venga del navegador)."""
import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from . import hardware
from .ollama import OllamaClient, OllamaError

DOWNLOAD_PAGE = "https://ollama.com/download"
WINDOWS_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"
LINUX_INSTALL_CMD = "curl -fsSL https://ollama.com/install.sh | sh"
_lock = threading.Lock()


class InstallError(Exception):
    pass


def _no_window():
    return 0x08000000 if platform.system() == "Windows" else 0  # CREATE_NO_WINDOW


def find_ollama():
    found = shutil.which("ollama")
    if found:
        return found
    system = platform.system()
    candidates = []
    if system == "Windows":
        candidates.append(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe")
    elif system == "Darwin":
        candidates.append(Path("/Applications/Ollama.app/Contents/Resources/ollama"))
    else:
        candidates += [Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama")]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def can_auto_install():
    system = platform.system()
    if system == "Windows":
        return True  # winget o descarga directa del instalador oficial
    if system == "Darwin":
        return shutil.which("brew") is not None
    return False  # Linux: el instalador oficial necesita sudo; se muestra el comando


def detect(settings):
    client = OllamaClient(settings["ollama_host"])
    running, version, installed = False, None, []
    try:
        version = client.version()
        running = True
        installed = [m["name"] for m in client.models()]
    except OllamaError:
        pass
    path = find_ollama()
    auto = can_auto_install()
    hw = hardware.snapshot()
    rec = hardware.recommend(hw)
    return {
        "os": platform.system(), "ollama_installed": bool(path) or running, "ollama_path": path,
        "ollama_running": running, "ollama_version": version,
        "can_auto_install": auto,
        "manual_install": None if auto else (LINUX_INSTALL_CMD if platform.system() == "Linux" else None),
        "download_page": DOWNLOAD_PAGE,
        "hardware": hw, "vram_mib": hw["vram_mib"], "recommended": rec["model"], "recommendation": rec,
        "catalog": hardware.catalog(hw), "installed_models": installed,
    }


_UNITS = {"KB": 1e3, "MB": 1e6, "GB": 1e9}
_BYTES_RE = re.compile(r"([\d.]+)\s*(KB|MB|GB)\s*/\s*([\d.]+)\s*(KB|MB|GB)", re.I)


def _mb(n):
    return "%.1f GB" % (n / 1e9) if n >= 1e9 else "%d MB" % round(n / 1e6)


def parse_winget_progress(line):
    """winget imprime '123 MB / 800 MB' mientras descarga. Devuelve un evento de progreso o None."""
    m = _BYTES_RE.search(line)
    if not m:
        return None
    done = float(m.group(1)) * _UNITS[m.group(2).upper()]
    total = float(m.group(3)) * _UNITS[m.group(4).upper()]
    if not total:
        return None
    pct = min(100, int(100 * done / total))
    if pct >= 100:
        return {"type": "progress", "percent": None, "text": "Instalando Ollama…"}
    return {"type": "progress", "percent": pct, "text": "Descargando Ollama · %s de %s" % (_mb(done), _mb(total))}


def _run(cmd, progress_parser=None):
    """Ejecuta un comando fijo y emite su salida como eventos de log/progreso. Devuelve el código de salida."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", creationflags=_no_window())
    for raw in proc.stdout:
        line = raw.replace("\r", "\n").strip().splitlines()
        if not line:
            continue
        line = line[-1]
        event = progress_parser(line) if progress_parser else None
        if event:
            yield event
        elif line.strip(" -\\|/█▒"):
            yield {"type": "log", "text": line}
    return proc.wait()


def _download_windows_installer():
    dest = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
    with urllib.request.urlopen(WINDOWS_INSTALLER_URL, timeout=30) as r, open(dest, "wb") as f:
        total, done, last = int(r.headers.get("Content-Length") or 0), 0, -1
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            pct = int(100 * done / total) if total else None
            if pct != last:
                last = pct
                yield {"type": "progress", "percent": pct,
                       "text": "Descargando instalador de Ollama · %s%s" % (_mb(done), " de " + _mb(total) if total else "")}
    return dest


def install_ollama():
    """Generador de eventos {'type': 'log'|'done'}. Lanza InstallError si no se puede."""
    if not _lock.acquire(blocking=False):
        raise InstallError("Ya hay una instalación en curso.")
    try:
        system = platform.system()
        if system == "Windows":
            winget = shutil.which("winget")
            if winget:
                yield {"type": "log", "text": "Instalando Ollama con winget…"}
                code = yield from _run([winget, "install", "-e", "--id", "Ollama.Ollama",
                                        "--accept-package-agreements", "--accept-source-agreements"],
                                       parse_winget_progress)
                if code != 0 and not find_ollama():
                    raise InstallError("winget terminó con el código %s." % code)
            else:
                try:
                    installer = yield from _download_windows_installer()
                except OSError as e:
                    raise InstallError("No se pudo descargar el instalador: %s" % e)
                yield {"type": "progress", "percent": None, "text": "Instalando Ollama…"}
                code = yield from _run([str(installer), "/SILENT"])
                if code != 0 and not find_ollama():
                    raise InstallError("El instalador terminó con el código %s." % code)
        elif system == "Darwin" and shutil.which("brew"):
            yield {"type": "progress", "percent": None, "text": "Instalando Ollama con Homebrew…"}
            code = yield from _run(["brew", "install", "ollama"])
            if code != 0:
                raise InstallError("brew terminó con el código %s." % code)
        else:
            raise InstallError("En este sistema hay que instalar Ollama a mano: %s" % (
                LINUX_INSTALL_CMD if system == "Linux" else DOWNLOAD_PAGE))
        if not find_ollama():
            raise InstallError("La instalación terminó pero no se encontró Ollama.")
        yield {"type": "progress", "percent": 100, "text": "Ollama instalado"}
        yield {"type": "done"}
    finally:
        _lock.release()


def start_ollama(host, timeout=30):
    """Inicia 'ollama serve' en segundo plano y espera a que responda. Devuelve {'ok', 'error'}."""
    client = OllamaClient(host)
    try:
        client.version()
        return {"ok": True}
    except OllamaError:
        pass
    path = find_ollama()
    if not path:
        return {"ok": False, "error": "Ollama no está instalado."}
    kwargs = {"creationflags": _no_window() | 0x00000200} if platform.system() == "Windows" else {"start_new_session": True}
    try:
        subprocess.Popen([path, "serve"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, **kwargs)
    except OSError as e:
        return {"ok": False, "error": "No se pudo iniciar Ollama: %s" % e}
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            client.version()
            return {"ok": True}
        except OllamaError:
            time.sleep(0.5)
    return {"ok": False, "error": "Ollama no respondió en %d segundos." % timeout}
