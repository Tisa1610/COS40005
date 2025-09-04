# backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import os, json, hmac, hashlib, threading, time, random
from datetime import datetime
import psutil
import uvicorn

# ------------------ FastAPI app + CORS ------------------
app = FastAPI(title="RTM Collector + Metrics")

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ Models ------------------
class SystemMetrics(BaseModel):
    cpu_usage: float
    ram_usage: float
    temperature: float
    packet_count: int

class Alert(BaseModel):
    timestamp: str
    level: str        # INFO | WARNING | ERROR | CRITICAL
    message: str
    source: str = "backend"   # 'backend' (local monitor) or 'agent'
    details: Dict[str, Any] = {}

# ------------------ In-memory state ------------------
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

# ------------------ Health ------------------
@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

# ------------------ Metrics (mocked + psutil) ------------------
@app.get("/metrics", response_model=SystemMetrics)
def get_metrics():
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory().percent
    temp = round(random.uniform(40, 85), 2)        # replace with real sensor if you have one
    packet_count = random.randint(10, 200)         # replace with real NIC counters if desired
    return SystemMetrics(cpu_usage=cpu, ram_usage=ram, temperature=temp, packet_count=packet_count)

# ------------------ Alerts (UI consumes this) ------------------
@app.get("/alerts", response_model=List[Alert])
def get_alerts():
    # newest last so UI can append; change to reversed(alerts) if you want newest first
    return alerts

# ------------------ Agent collector (/ingest) ------------------
# HMAC matches your agent: sha256(JSON-without-hmac, sorted keys, separators (',',':'))
def compute_hmac(payload: Dict[str, Any], key: bytes) -> str:
    body = dict(payload)
    body.pop("hmac", None)
    msg = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

HMAC_KEY = os.environ.get("RTM_HMAC_KEY", "dev-change-me").encode()

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

    # Normalize into an Alert the UI can show
    etype = payload.get("type", "event")
    subtype = payload.get("subtype", "unknown")
    sev = int(payload.get("severity", 1))
    score = int(payload.get("signals", {}).get("score", 0))
    host = payload.get("host", {}).get("name") or payload.get("host", {}).get("id", "unknown-host")

    # Map severity to level text
    level = "INFO"
    if sev >= 3:
        level = "ERROR"
    elif sev == 2:
        level = "WARNING"

    msg = f"{host}: {etype}/{subtype} (sev={sev}, score={score})"
    add_alert(level, msg, source="agent", details=payload)

    return {"status": "ok"}

# ------------------ Background local monitor (optional) ------------------
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

if __name__ == "__main__":
    # IMPORTANT: run on 8010 so the UI can connect there
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True)
