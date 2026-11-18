"""Hardware detection and model recommendation.

The memory rules are documented HEURISTICS (not minimum requirements): they are calibrated with
real benchmarks contributed by users (see docs/BENCHMARKS.md). No external dependencies.
"""
import ctypes
import os
import platform
import re
import shutil
import subprocess
import time
from functools import lru_cache

GB = 1024 ** 3

# ---- quantizations and model families -----------------------------------------------------------
# bytes per parameter (adjusted to the sizes published by Ollama: e.g. qwen2.5:7b Q4_K_M ≈ 4.7 GB)
QUANTS = {
    "q4_K_M": {"bpp": 0.615, "label": "Q4 · balanced (recommended)", "short": "Q4"},
    "q5_K_M": {"bpp": 0.715, "label": "Q5 · higher quality, ~15% more memory", "short": "Q5"},
    "q8_0": {"bpp": 1.065, "label": "Q8 · nearly lossless, ~75% more memory", "short": "Q8"},
}
FAMILIES = [
    {"id": "qwen2.5:0.5b", "label": "Qwen 2.5 · 0.5B", "params_b": 0.49, "license": "Apache-2.0",
     "note": "Minimal. Only for very limited computers; basic answers."},
    {"id": "qwen2.5:1.5b", "label": "Qwen 2.5 · 1.5B", "params_b": 1.54, "license": "Apache-2.0",
     "note": "Very lightweight, for modest computers."},
    {"id": "qwen2.5:3b", "label": "Qwen 2.5 · 3B", "params_b": 3.09, "license": "Qwen Research",
     "note": "Fast and accurate in Spanish. Good choice without a powerful GPU."},
    {"id": "llama3.2:3b", "label": "Llama 3.2 · 3B", "params_b": 3.21, "license": "Llama 3.2 Community",
     "note": "Lightweight alternative from Meta."},
    {"id": "qwen2.5:7b", "label": "Qwen 2.5 · 7B", "params_b": 7.62, "license": "Apache-2.0",
     "note": "Very good quality/speed balance."},
    {"id": "llama3.1:8b", "label": "Llama 3.1 · 8B", "params_b": 8.03, "license": "Llama 3.1 Community",
     "note": "Alternative from Meta, very capable in conversation."},
    {"id": "qwen2.5:14b", "label": "Qwen 2.5 · 14B", "params_b": 14.7, "license": "Apache-2.0",
     "note": "Higher quality; requires a large GPU or plenty of RAM."},
]
# Preference order for recommendations (Qwen performs well in Spanish). The others remain as alternatives.
RECOMMEND_ORDER = ["qwen2.5:14b", "qwen2.5:7b", "qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5:0.5b"]
CPU_ONLY_MAX_PARAMS_B = 3.5   # without a GPU speed drops with size: a model ≤ 3.5B is preferred
RESERVE_VRAM_GB = 0.7         # the desktop and browser also use VRAM
RESERVE_RAM_GB = 4.0          # operating system + browser
FIT_LABELS = {"gpu": "Fits in your GPU", "hybrid": "GPU + RAM (slower)",
              "cpu": "CPU only (slow)", "no": "Exceeds your computer's resources"}


# ---- pure parsers (testable with sample text) ----------------------------------------------------
def parse_meminfo(text):
    vals = {m.group(1): int(m.group(2)) * 1024 for m in re.finditer(r"^(\w+):\s+(\d+) kB", text, re.M)}
    if "MemTotal" not in vals:
        return None
    return {"total": vals["MemTotal"], "available": vals.get("MemAvailable", vals.get("MemFree", 0))}


def parse_vm_stat(text, total_bytes):
    page = re.search(r"page size of (\d+) bytes", text)
    size = int(page.group(1)) if page else 4096
    pages = sum(int(m.group(1)) for m in re.finditer(r"Pages (?:free|inactive|speculative):\s+(\d+)\.", text))
    return {"total": total_bytes, "available": pages * size}


def parse_nvidia_smi(csv):
    out = []
    for line in csv.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and parts[1].isdigit():
            out.append({"name": parts[0], "vram_total_mib": int(parts[1]), "vram_used_mib": int(parts[2]) if parts[2].isdigit() else None,
                        "driver": parts[3] if len(parts) > 3 else None})
    return out


# ---- detection ----------------------------------------------------------------------------------
def _nvidia_smi():
    exe = shutil.which("nvidia-smi")
    if not exe and platform.system() == "Windows":
        for cand in (r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
            if os.path.isfile(cand):
                exe = cand
                break
    return exe


def _query_nvidia():
    exe = _nvidia_smi()
    if not exe:
        return []
    try:
        res = subprocess.run([exe, "--query-gpu=name,memory.total,memory.used,driver_version",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
        return parse_nvidia_smi(res.stdout)
    except (OSError, subprocess.SubprocessError):
        return []


@lru_cache(maxsize=1)
def cpu_info():
    system, name = platform.system(), None
    try:
        if system == "Windows":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                name = winreg.QueryValueEx(k, "ProcessorNameString")[0]
        elif system == "Linux":
            with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
                m = re.search(r"^model name\s*:\s*(.+)$", f.read(), re.M)
                name = m.group(1) if m else None
        elif system == "Darwin":
            name = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=3).stdout
    except (OSError, ImportError, subprocess.SubprocessError):
        pass
    return {"name": re.sub(r"\s+", " ", (name or platform.processor() or platform.machine()).strip()),
            "threads": os.cpu_count(), "arch": platform.machine()}


def ram():
    """Total/available RAM in GB (None if it could not be read)."""
    system, raw = platform.system(), None
    try:
        if system == "Windows":
            class MEMSTAT(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MEMSTAT(); st.dwLength = ctypes.sizeof(MEMSTAT)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            raw = {"total": st.ullTotalPhys, "available": st.ullAvailPhys}
        elif system == "Linux":
            with open("/proc/meminfo", encoding="utf-8") as f:
                raw = parse_meminfo(f.read())
        elif system == "Darwin":
            total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=3).stdout)
            raw = parse_vm_stat(subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=3).stdout, total)
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        raw = None
    if not raw or not raw["total"]:
        return {"total_gb": None, "available_gb": None, "used_gb": None}
    t, a = raw["total"] / GB, raw["available"] / GB
    return {"total_gb": round(t, 1), "available_gb": round(a, 1), "used_gb": round(t - a, 1)}


@lru_cache(maxsize=1)
def _static_gpus():
    gpus = _query_nvidia()
    if gpus:
        return tuple({"name": g["name"], "vram_total_mib": g["vram_total_mib"], "driver": g.get("driver"),
                      "vendor": "nvidia", "estimated": False} for g in gpus)
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        total = ram()["total_gb"]
        if total:  # unified memory: the GPU can use ~2/3 of the RAM (estimate)
            return ({"name": "Apple Silicon (unified memory)", "vram_total_mib": int(total * 1024 * 0.66),
                     "driver": None, "vendor": "apple", "estimated": True},)
    return ()


_vram_cache = {"t": 0.0, "v": None}


def vram_usage():
    """Used/total VRAM of the best NVIDIA GPU, in MiB (2 s cache; None if unavailable)."""
    if time.time() - _vram_cache["t"] > 2:
        gpus = _query_nvidia()
        best = max(gpus, key=lambda g: g["vram_total_mib"]) if gpus else None
        _vram_cache.update(t=time.time(), v={"used_mib": best["vram_used_mib"], "total_mib": best["vram_total_mib"]} if best and best["vram_used_mib"] is not None else None)
    return _vram_cache["v"]


def vram_mib():
    gpus = _static_gpus()
    return max((g["vram_total_mib"] for g in gpus), default=None)


def snapshot():
    """Snapshot of the computer with no personal data (no user or machine name)."""
    gpus = list(_static_gpus())
    return {"os": "%s %s" % (platform.system(), platform.release()), "cpu": cpu_info(), "ram": ram(), "gpus": gpus,
            "vram_mib": max((g["vram_total_mib"] for g in gpus), default=None),
            "unified": bool(gpus and gpus[0]["vendor"] == "apple")}


# ---- matching models to resources ----------------------------------------------------------------
def tag_for(family_id, quant):
    return family_id if quant == "q4_K_M" else "%s-instruct-%s" % (family_id, quant)


def need_gb(params_b, quant):
    """Estimated memory: weights + KV-cache (4k context) + buffers."""
    return params_b * QUANTS[quant]["bpp"] + 0.6 + 0.06 * params_b


def assess(hw, params_b, quant):
    need = need_gb(params_b, quant)
    vram = (hw.get("vram_mib") or 0) / 1024
    vram_budget = max(0.0, vram - RESERVE_VRAM_GB) if vram else 0.0
    r = hw.get("ram") or {}
    total, avail = r.get("total_gb") or 8.0, r.get("available_gb") or 4.0
    ram_budget = max(0.0, min(total - RESERVE_RAM_GB, avail - 1.0))
    if hw.get("unified"):
        return "gpu" if need <= min(vram_budget, ram_budget + 2.0) else "no"
    if vram_budget and need <= vram_budget:
        return "gpu"
    if vram_budget and need <= vram_budget + ram_budget * 0.8:
        return "hybrid"
    return "cpu" if need <= ram_budget else "no"


def catalog(hw=None):
    hw = hw or snapshot()
    out = []
    for fam in FAMILIES:
        variants = [{"quant": q, "quant_label": info["label"], "name": tag_for(fam["id"], q),
                     "size_gb": round(fam["params_b"] * info["bpp"], 1), "need_gb": round(need_gb(fam["params_b"], q), 1),
                     "fit": assess(hw, fam["params_b"], q)} for q, info in QUANTS.items()]
        for v in variants:
            v["fit_label"] = FIT_LABELS[v["fit"]]
        out.append({**fam, "variants": variants})
    return out


def _gpu_text(hw):
    g = (hw.get("gpus") or [None])[0]
    return "%s · %.0f GB of VRAM" % (g["name"], g["vram_total_mib"] / 1024) if g else None


def recommend(hw=None):
    hw = hw or snapshot()
    by_id = {f["id"]: f for f in FAMILIES}
    gpu = _gpu_text(hw)
    for fid in RECOMMEND_ORDER:
        if assess(hw, by_id[fid]["params_b"], "q4_K_M") == "gpu":
            need = need_gb(by_id[fid]["params_b"], "q4_K_M")
            return {"model": fid, "quant": "q4_K_M", "fit": "gpu", "warning": None, "vram_mib": hw.get("vram_mib"),
                    "reason": "%s: this model fits entirely in the GPU (≈%.1f GB needed)." % (gpu, need)}
    for fid in RECOMMEND_ORDER:
        fam = by_id[fid]
        if fam["params_b"] <= CPU_ONLY_MAX_PARAMS_B and assess(hw, fam["params_b"], "q4_K_M") == "cpu":
            why = "No compatible GPU" if not hw.get("vram_mib") else "Your GPU is too small for larger models"
            return {"model": fid, "quant": "q4_K_M", "fit": "cpu", "warning": None, "vram_mib": hw.get("vram_mib"),
                    "reason": "%s: a lightweight model that runs well on CPU is recommended." % why}
    return {"model": "qwen2.5:0.5b", "quant": "q4_K_M", "fit": "no", "vram_mib": hw.get("vram_mib"),
            "reason": "Your computer has very little free memory.",
            "warning": "Not even the smallest model fits comfortably. Close other programs before trying."}
