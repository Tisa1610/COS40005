# backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from pathlib import Path
import os, json, hmac, hashlib, threading, time, random
from datetime import datetime
import psutil
import uvicorn
import yaml

# -------------------------------------------------------
# Paths / Config
# -------------------------------------------------------
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "agent" / "config.yaml"   # your file

def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

CONFIG = load_config()

# HMAC key name comes from config.security.hmac_key_env (default below)
HMAC_ENV_NAME = (CONFIG.get("security", {}) or {}).get("hmac_key_env", "RTM_HMAC_KEY")
HMAC_KEY = os.environ.get(HMAC_ENV_NAME, "dev-change-me").encode()

# -------------------------------------------------------
# FastAPI + CORS
# -------------------------------------------------------
app = FastAPI(title="RTM Collector + Metrics (single service on 8000)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*",  # dev convenience
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------
# Models
# -------------------------------------------------------
class SystemMetrics(BaseModel):
    cpu_usage: float
    ram_usage: float
    temperature: float
    packet_count: int

class Alert(BaseModel):
    timestamp: str
    level: str          # INFO | WARNING | ERROR | CRITICAL
    message: str
    source: str = "backend"  # 'backend' (local monitor) or 'agent'
    details: Dict[str, Any] = {}

# -------------------------------------------------------
# Alerts buffer
# -------------------------------------------------------
alerts: List[Alert] = []
ALERT_LIMIT = 200

def add_alert(level: str, message: str, source: str = "backend", details: Dict[str, Any] = None):
    alert = Alert(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        level=level,
        message=message,
        source=source,
        details=details or {},
    )
    alerts.append(alert)
    if len(alerts) > ALERT_LIMIT:
        del alerts[: len(alerts) - ALERT_LIMIT]

# -------------------------------------------------------
# Health
# -------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

# -------------------------------------------------------
# Metrics (psutil + simple mock values)
# -------------------------------------------------------
@app.get("/metrics", response_model=SystemMetrics)
def get_metrics():
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory().percent
    temp = round(random.uniform(40, 85), 2)       # replace with real sensor if available
    packet_count = random.randint(10, 200)        # replace with NIC counters if desired
    return SystemMetrics(cpu_usage=cpu, ram_usage=ram, temperature=temp, packet_count=packet_count)

# -------------------------------------------------------
# Alerts (for UI)
# -------------------------------------------------------
@app.get("/alerts", response_model=List[Alert])
def get_alerts():
    # newest last so UI can append; change to reversed(alerts) if you want newest first
    return alerts

# -------------------------------------------------------
# Agent ingest (HMAC-verified)
# -------------------------------------------------------
def compute_hmac(payload: Dict[str, Any], key: bytes) -> str:
    body = dict(payload)
    body.pop("hmac", None)
    msg = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

@app.post("/ingest")
async def ingest(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    given = payload.get("hmac")
    expected = compute_hmac(payload, HMAC_KEY)
    if not given or not hmac.compare_digest(given, expected):
        raise HTTPException(status_code=401, detail="HMAC verification failed")

    # Normalize agent event → Alert visible in UI
    etype = payload.get("type", "event")
    subtype = payload.get("subtype", "unknown")
    sev = int(payload.get("severity", 1))
    score = int(payload.get("signals", {}).get("score", 0))
    host = payload.get("host", {}).get("name") or payload.get("host", {}).get("id", "unknown-host")

    level = "INFO"
    if sev >= 3:
        level = "ERROR"
    elif sev == 2:
        level = "WARNING"

    msg = f"{host}: {etype}/{subtype} (sev={sev}, score={score})"
    add_alert(level, msg, source="agent", details=payload)
    return {"status": "ok"}

# -------------------------------------------------------
# Config API (used by Settings page)
# -------------------------------------------------------
@app.get("/api/config")
def api_get_config():
    cfg = load_config()
    # Don’t leak secrets; keep the env var name only
    if "security" in cfg:
        cfg["security"] = {"hmac_key_env": cfg["security"].get("hmac_key_env", "RTM_HMAC_KEY")}
    return cfg

@app.put("/api/config")
async def api_put_config(request: Request):
    try:
        new_cfg = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Basic validation for https mode
    outbound = (new_cfg.get("outbound") or {})
    mode = outbound.get("mode", "https")
    if mode == "https":
        url = ((outbound.get("https") or {}).get("url") or "")
        if not url.startswith("http://") and not url.startswith("https://"):
            raise HTTPException(status_code=400, detail="Collector URL must start with http(s)://")
        if not url.endswith("/ingest"):
            raise HTTPException(status_code=400, detail="Collector URL should end with /ingest")

    save_config(new_cfg)
    # refresh in-memory config + HMAC key (in case user changed env name)
    global CONFIG, HMAC_ENV_NAME, HMAC_KEY
    CONFIG = new_cfg
    HMAC_ENV_NAME = (CONFIG.get("security", {}) or {}).get("hmac_key_env", "RTM_HMAC_KEY")
    HMAC_KEY = os.environ.get(HMAC_ENV_NAME, "dev-change-me").encode()
    return {"status": "saved"}

@app.post("/api/agent/reload")
def api_agent_reload():
    # Stub: in a full build, signal the Windows service / agent to reload config.
    return {"status": "reload_queued"}

# -------------------------------------------------------
# Background local monitor (generates sample alerts)
# -------------------------------------------------------
def monitor_system():
    while True:
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        temp = round(random.uniform(40, 85), 2)
        packet_count = random.randint(10, 200)

        if cpu > 85:
            add_alert("WARNING", f"High CPU usage: {cpu}%", source="backend", details={"cpu": cpu})
        if ram > 90:
            add_alert("WARNING", f"High RAM usage: {ram}%", source="backend", details={"ram": ram})
        if temp > 80:
            add_alert("ERROR", f"High temperature detected: {temp}°C", source="backend", details={"temp": temp})
        if packet_count > 150:
            add_alert("WARNING", f"High network traffic: {packet_count} packets", source="backend", details={"packets": packet_count})

        time.sleep(5)

@app.on_event("startup")
def startup_event():
    add_alert("INFO", "Backend started", source="backend")
    threading.Thread(target=monitor_system, daemon=True).start()

# -------------------------------------------------------
# Entry
# -------------------------------------------------------
if __name__ == "__main__":
    # Single service: run everything on 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
