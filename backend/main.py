from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psutil
import time
from datetime import datetime
import random
import threading

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

alerts = []

def add_alert(level: str, message: str):
    alert = Alert(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        level=level,
        message=message
    )
    alerts.append(alert)
    if len(alerts) > 50:
        alerts.pop(0)

@app.get("/metrics", response_model=SystemMetrics)
def get_metrics():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    temp = round(random.uniform(40, 85), 2)
    packet_count = random.randint(10, 200)
    return SystemMetrics(cpu_usage=cpu, ram_usage=ram, temperature=temp, packet_count=packet_count)

@app.get("/alerts", response_model=list[Alert])
def get_alerts():
    return alerts

def monitor_system():
    while True:
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        temp = round(random.uniform(40, 85), 2)
        packet_count = random.randint(10, 200)

        if cpu > 85:
            add_alert("WARNING", f"High CPU usage: {cpu}%")
        if ram > 90:
            add_alert("WARNING", f"High RAM usage: {ram}%")
        if temp > 80:
            add_alert("ERROR", f"High temperature detected: {temp}°C")
        if packet_count > 100:
            add_alert("WARNING", f"High network traffic: {packet_count} packets")

        processes = [p.info for p in psutil.process_iter(['pid', 'name', 'username'])]
        for p in processes:
            if p['username'] == 'root' and 'kernel_task' in p['name']:
                add_alert("ERROR", f"Unknown high-privilege process detected: {p['name']} (User: {p['username']})")
        time.sleep(5)

@app.on_event("startup")
def startup_event():
    threading.Thread(target=monitor_system, daemon=True).start()

from typing import List

class ComplianceLog(BaseModel):
    timestamp: str
    action: str
    status: str

compliance_logs = [
    {"timestamp": "2025-05-01 10:00", "action": "Backup", "status": "Success"},
    {"timestamp": "2025-05-02 14:22", "action": "Audit", "status": "Complete"},
    {"timestamp": "2025-05-03 09:10", "action": "Integrity Check", "status": "Passed"},
]

@app.get("/logs", response_model=List[ComplianceLog])
def get_logs():
    return compliance_logs
