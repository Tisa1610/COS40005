# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List  # Python 3.8+ compatible typing
import psutil
import time
from datetime import datetime
import random
import threading
import uvicorn

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

@app.on_event("startup")
def startup_event():
    # Seed a few alerts so the table isn't empty on first load (optional)
    add_alert("INFO", "Backend started")
    threading.Thread(target=monitor_system, daemon=True).start()

# So you can run: python backend/main.py
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
