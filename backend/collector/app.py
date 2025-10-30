import os, json, hmac, hashlib, random
from datetime import datetime
from typing import Any, Dict, List, Optional
import psutil

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ─────────────────────────────────────────────────────────────────────────────
# Config (optional YAML load)
# ─────────────────────────────────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
CONF: Dict[str, Any] = {
    "watch_path": r"C:\Users\sakindu\Desktop\testing11\backend\agent\virus",
    "min_warning_severity": 2,
    "min_warning_score": 20,
    "drop_win_events": True,
}
def _load_conf():
    try:
        import yaml  # type: ignore
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                CONF.update({k: v for k, v in data.items() if v is not None})
    except Exception as e:
        print(f"[collector] config load warning: {e}")
_load_conf()

WATCH_PATH = os.path.normcase(CONF["watch_path"])
MIN_WARN_SEV = int(CONF["min_warning_severity"])
MIN_WARN_SCO = int(CONF["min_warning_score"])
DROP_WIN_EVENTS = bool(CONF["drop_win_events"])

# HMAC key (must match the agent’s)
HMAC_ENV_NAME = "RTM_HMAC_KEY"
KEY = os.environ.get(HMAC_ENV_NAME, "dev").encode()

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="RTM Collector")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000","http://127.0.0.1:3000",
        "http://localhost:3001","http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store (bigger ring buffer; tunable via env)
EVENTS: List[Dict[str, Any]] = []
EVENTS_MAX = int(os.environ.get("EVENTS_MAX", "20000"))  # was 500

# ───────────────── Helpers ─────────────────
def verify(event: Dict[str, Any]):
    sig = event.get("hmac", "")
    body = event.copy()
    body.pop("hmac", None)
    msg = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    good = hmac.compare_digest(sig, hmac.new(KEY, msg, hashlib.sha256).hexdigest())
    if not good:
        raise HTTPException(status_code=400, detail="bad hmac")

def is_windows_event(ev: Dict[str, Any]) -> bool:
    et = (ev.get("type") or "").lower()
    sub = (ev.get("subtype") or "").lower()
    ch = ((ev.get("data") or {}).get("channel") or "").lower()
    if sub == "win_event" or et == "win_event":
        return True
    if et == "system" and "windows" in ch:
        return True
    return False

def extract_path(ev: Dict[str, Any]) -> str:
    d = ev.get("data") or {}
    for k in ("path", "filepath", "file", "target", "dst", "dst_path"):
        val = d.get(k)
        if isinstance(val, str) and val.strip():
            return val
    return ""

def in_watch_path(path: str) -> bool:
    if not path:
        return False
    try:
        norm = os.path.normcase(os.path.abspath(path))
        wp = os.path.normcase(os.path.abspath(WATCH_PATH))
        return norm.startswith(wp)
    except Exception:
        return False

def classify_level(ev: Dict[str, Any]) -> str:
    sev = int(ev.get("severity", 0) or 0)
    score = int(ev.get("score", 0) or 0) or int((ev.get("signals") or {}).get("score", 0) or 0)
    return "WARNING" if (sev >= MIN_WARN_SEV and score >= MIN_WARN_SCO) else "INFO"

# ───────────────── Routes (UI needs these) ─────────────────
@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

@app.get("/metrics")
def metrics():
    return {
        "cpu_usage": psutil.cpu_percent(interval=0.1),
        "ram_usage": psutil.virtual_memory().percent,
        "temperature": round(random.uniform(40, 85), 2),
        "packet_count": random.randint(10, 200),
    }

@app.get("/api/config")
def get_config():
    # Minimal config the Settings page expects
    return {
        "outbound": {"mode": "https", "https": {"url": "http://127.0.0.1:8000/ingest"}},
        "security": {"hmac_key_env": HMAC_ENV_NAME},
    }

@app.get("/alerts")
def get_alerts(
    limit: Optional[int] = Query(default=None, ge=1, description="Return the last N events"),
    since: Optional[str] = Query(default=None, description="ISO timestamp; return events >= this time"),
    level: Optional[str] = Query(default=None, description="INFO or WARNING (case-insensitive)"),
):
    """
    Returns alerts in chronological order. If `limit` is provided, only the last N are returned.
    Optional filters (not required by UI) allow ad-hoc inspection without changing the frontend.
    """
    data = EVENTS

    # Filter since time if requested
    if since:
        try:
            t0 = datetime.fromisoformat(since.replace("Z", "+00:00"))
            data = [e for e in data if _iso_to_dt(e.get("time")) >= t0]
        except Exception:
            pass

    # Filter by level if requested
    if level:
        lv = level.strip().upper()
        data = [e for e in data if e.get("level", "").upper() == lv]

    # Apply limit (take the tail)
    if limit:
        data = data[-limit:]

    return data

def _iso_to_dt(iso: Optional[str]) -> datetime:
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except Exception:
        return datetime.min

# ───────────────── Agent ingest ─────────────────
@app.post("/ingest")
async def ingest(req: Request):
    ev = await req.json()
    verify(ev)

    if DROP_WIN_EVENTS and is_windows_event(ev):
        return {"ok": True, "dropped": "win_event"}

    path = extract_path(ev)
    if path and not in_watch_path(path):
        return {"ok": True, "dropped": "outside_watch_path"}

    ev["level"] = classify_level(ev)

    EVENTS.append(ev)
    # Trim ring buffer but keep chronological order
    if len(EVENTS) > EVENTS_MAX:
        del EVENTS[: len(EVENTS) - EVENTS_MAX]

    # compact debug print (optional)
    try:
        print(json.dumps({
            "time": ev.get("time"),
            "type": ev.get("type"), "subtype": ev.get("subtype"),
            "severity": ev.get("severity"), "score": ev.get("score"),
            "level": ev.get("level"), "path": path
        }))
    except Exception:
        pass
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
