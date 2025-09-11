# backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List  # Python 3.8+ compatible typing
import psutil
import time
from datetime import datetime
import random
import threading
import uvicorn
import os
import subprocess
import smtplib
import ssl
import json
import hmac
import hashlib
from email.message import EmailMessage
from pathlib import Path

app = FastAPI()

# Allow your React dev server (port 3000). 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SystemMetrics(BaseModel):
    cpu_usage: float
    ram_usage: float
    temperature: float
    packet_count: int

class Alert(BaseModel):
    timestamp: str
    level: str
    message: str

alerts: List[Alert] = []

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
SCAN_PATH = os.environ.get("CLAMAV_SCAN_PATH", ".")
HMAC_KEY = os.environ.get("RTM_HMAC_KEY", "dev").encode()
last_scan = 0.0

def add_alert(level: str, message: str):
    alert = Alert(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        level=level,
        message=message
    )
    alerts.append(alert)
    # keep last 200 alerts
    if len(alerts) > 200:
        alerts[:] = alerts[-200:]

    if level in {"ERROR", "CRITICAL"} and GMAIL_USER and GMAIL_APP_PASSWORD:
        send_gmail_alert(f"OTShield Alert ({level})", message, GMAIL_USER)


def send_gmail_alert(subject: str, body: str, recipient: str):
    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        alerts.append(Alert(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), level="ERROR", message=f"Email failed: {e}"))


def scan_for_malware(path: str):
    try:
        result = subprocess.run(["clamscan", "-r", path], capture_output=True, text=True)
        if "Infected files: 0" not in result.stdout:
            add_alert("CRITICAL", f"Malware detected in {path}\n{result.stdout}")
    except FileNotFoundError:
        add_alert("ERROR", "ClamAV not installed")


def verify_event(event: dict):
    sig = event.get("hmac", "")
    body = event.copy(); body.pop("hmac", None)
    msg = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    good = hmac.compare_digest(sig, hmac.new(HMAC_KEY, msg, hashlib.sha256).hexdigest())
    if not good:
        raise HTTPException(status_code=400, detail="bad hmac")


@app.post("/ingest")
async def ingest(event: dict):
    verify_event(event)
    print(json.dumps(event, ensure_ascii=False))
    return {"ok": True}

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

@app.get("/metrics", response_model=SystemMetrics)
def get_metrics():
    cpu = psutil.cpu_percent(interval=0.1)  # short interval for a non-zero reading
    ram = psutil.virtual_memory().percent
    temp = round(random.uniform(40, 85), 2)
    packet_count = random.randint(10, 200)
    return SystemMetrics(cpu_usage=cpu, ram_usage=ram, temperature=temp, packet_count=packet_count)

@app.get("/alerts", response_model=List[Alert])
def get_alerts():
    return alerts

def monitor_system():
    global last_scan
    while True:
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        temp = round(random.uniform(40, 85), 2)
        packet_count = random.randint(10, 200)

        if cpu > 85:
            add_alert("WARNING", f"High CPU usage: {cpu}%")
        if ram > 90:
            add_alert("WARNING", f"High RAM usage: {ram}%")
        if temp > 80:
            add_alert("ERROR", f"High temperature detected: {temp}°C")
        if packet_count > 150:
            add_alert("WARNING", f"High network traffic: {packet_count} packets")

        if time.time() - last_scan > 60:
            scan_for_malware(SCAN_PATH)
            last_scan = time.time()

        # Example anomaly check
        try:
            for p in psutil.process_iter(['pid', 'name', 'username']):
                info = p.info
                if info.get('username') == 'root' and 'kernel_task' in (info.get('name') or ''):
                    add_alert("ERROR", f"Unknown high-privilege process detected: {info['name']} (User: {info['username']})")
        except Exception:
            # Some platforms restrict process details; ignore
            pass

        time.sleep(5)


def start_agent():
    try:
        import importlib.util

        agent_path = Path(__file__).with_name("agent") / "agent.py"
        spec = importlib.util.spec_from_file_location("rtm_agent", agent_path)
        agent = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent)
        agent.main()
    except Exception as e:
        add_alert("ERROR", f"Agent failed to start: {e}")

@app.on_event("startup")
def startup_event():
    # Seed a few alerts so the table isn't empty on first load (optional)
    add_alert("INFO", "Backend started")
    threading.Thread(target=monitor_system, daemon=True).start()
    threading.Thread(target=start_agent, daemon=True).start()

# So you can run: python backend/main.py
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
