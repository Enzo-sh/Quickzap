"""SQLite: conversations, messages, and settings. A local file, no server."""
import json
import os
import sqlite3
import time
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, model TEXT, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL, content TEXT NOT NULL, model TEXT, created_at REAL);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS metrics(
  id INTEGER PRIMARY KEY, conversation_id INTEGER, model TEXT, ttft_ms INTEGER, total_ms INTEGER,
  tokens INTEGER, tps REAL, created_at REAL);
CREATE TABLE IF NOT EXISTS benchmarks(
  id INTEGER PRIMARY KEY, model TEXT, quick INTEGER, ok INTEGER, report TEXT NOT NULL, created_at REAL);
"""


@contextmanager
def connect():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DATA_DIR / "quickzap.db"), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    with connect() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)


# ---- settings ----------------------------------------------------------------

def get_settings():
    settings = dict(config.DEFAULTS)
    with connect() as c:
        for row in c.execute("SELECT key, value FROM settings"):
            if row["key"] in settings:
                try:
                    settings[row["key"]] = json.loads(row["value"])
                except ValueError:
                    pass
    return settings


def _validate(key, value):
    if key == "model":
        from .ollama import valid_model_name
        if not valid_model_name(value):
            raise ValueError("Invalid model name.")
    elif key == "temperature":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 2:
            raise ValueError("Temperature must be between 0 and 2.")
    elif key == "personality":
        if not isinstance(value, str) or len(value) > 500:
            raise ValueError("Personality must be text of up to 500 characters.")
    elif key == "context_messages":
        if isinstance(value, bool) or not isinstance(value, int) or not 2 <= value <= 100:
            raise ValueError("Context messages must be an integer between 2 and 100.")
    elif key == "ollama_host":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Invalid Ollama address.")
    elif key == "num_ctx":
        if isinstance(value, bool) or not isinstance(value, int) or not 512 <= value <= 32768:
            raise ValueError("Context must be an integer between 512 and 32768 tokens.")
    elif key == "keep_alive":
        if not isinstance(value, str) or not config.KEEP_ALIVE_RE.match(value):
            raise ValueError("Invalid keep_alive (e.g. 10m, 1h, -1).")
    else:
        raise ValueError("Unknown setting: %s" % key)


def update_settings(patch):
    for key, value in patch.items():
        _validate(key, value)
    with connect() as c:
        for key, value in patch.items():
            c.execute("INSERT INTO settings(key, value) VALUES(?, ?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))
    return get_settings()


# ---- conversations ------------------------------------------------------------

def create_conversation(title, model):
    now = time.time()
    with connect() as c:
        cur = c.execute("INSERT INTO conversations(title, model, created_at, updated_at) VALUES(?,?,?,?)",
                        (title, model, now, now))
        return cur.lastrowid


def conversation_exists(cid):
    with connect() as c:
        return c.execute("SELECT 1 FROM conversations WHERE id=?", (cid,)).fetchone() is not None


def add_message(cid, role, content, model=None):
    now = time.time()
    with connect() as c:
        c.execute("INSERT INTO messages(conversation_id, role, content, model, created_at) VALUES(?,?,?,?,?)",
                  (cid, role, content, model, now))
        c.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, cid))


def history(cid, limit):
    with connect() as c:
        rows = c.execute("SELECT role, content FROM (SELECT id, role, content FROM messages "
                         "WHERE conversation_id=? ORDER BY id DESC LIMIT ?) ORDER BY id", (cid, limit)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def list_conversations(limit=100):
    with connect() as c:
        rows = c.execute("SELECT id, title, model, created_at, updated_at FROM conversations "
                         "ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_conversation(cid):
    with connect() as c:
        conv = c.execute("SELECT id, title, model, created_at, updated_at FROM conversations WHERE id=?",
                         (cid,)).fetchone()
        if not conv:
            return None
        msgs = c.execute("SELECT role, content, model, created_at FROM messages "
                         "WHERE conversation_id=? ORDER BY id", (cid,)).fetchall()
    return {**dict(conv), "messages": [dict(m) for m in msgs]}


def delete_conversation(cid):
    with connect() as c:
        return c.execute("DELETE FROM conversations WHERE id=?", (cid,)).rowcount > 0


# ---- metrics and benchmarks -------------------------------------------------------

def add_metric(cid, model, ttft_ms, total_ms, tokens, tps):
    with connect() as c:
        c.execute("INSERT INTO metrics(conversation_id, model, ttft_ms, total_ms, tokens, tps, created_at) VALUES(?,?,?,?,?,?,?)",
                  (cid, model, ttft_ms, total_ms, tokens, tps, time.time()))


def metrics_summary(limit=20):
    """Averages of the latest replies (speed, time to first token, total time)."""
    with connect() as c:
        rows = c.execute("SELECT model, ttft_ms, total_ms, tokens, tps FROM metrics ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    if not rows:
        return {"count": 0, "last": None, "tps_avg": None, "ttft_ms_avg": None, "total_ms_avg": None}

    def avg(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return round(sum(vals) / len(vals), 1) if vals else None
    return {"count": len(rows), "last": dict(rows[0]), "tps_avg": avg("tps"),
            "ttft_ms_avg": avg("ttft_ms"), "total_ms_avg": avg("total_ms")}


def counts():
    with connect() as c:
        convs = c.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        msgs = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    base = config.DATA_DIR / "quickzap.db"
    size = sum(os.path.getsize(f) for f in (base, str(base) + "-wal", str(base) + "-shm") if os.path.exists(f))
    return {"conversations": convs, "messages": msgs, "db_bytes": size}


def _bench_summary(report):
    gen, mem, st = report["phases"].get("generation", {}), report.get("memory") or {}, report.get("stability") or {}
    return {"tps": gen.get("tps"), "ttft_ms": gen.get("ttft_ms"), "load_s": report["phases"].get("load", {}).get("seconds"),
            "vram_gb": mem.get("vram_gb"), "ram_gb": mem.get("ram_gb"), "gpu_percent": mem.get("gpu_percent"),
            "stable": st.get("stable"), "quality": report.get("quality")}


def save_benchmark(report):
    with connect() as c:
        c.execute("INSERT INTO benchmarks(model, quick, ok, report, created_at) VALUES(?,?,?,?,?)",
                  (report["model"], int(report.get("quick", True)), int(report["ok"]), json.dumps(report), time.time()))


def latest_benchmarks():
    """Latest successful benchmark for each model: used to compare models."""
    with connect() as c:
        rows = c.execute("SELECT report, created_at FROM benchmarks WHERE ok=1 ORDER BY id DESC").fetchall()
    seen, out = set(), []
    for r in rows:
        report = json.loads(r["report"])
        if report["model"] not in seen:
            seen.add(report["model"])
            out.append({"model": report["model"], "created_at": r["created_at"], **_bench_summary(report)})
    return out
