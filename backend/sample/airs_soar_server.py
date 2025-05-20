from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import json
import os

app = FastAPI()

# === Log Files ===
AIRS_LOG_FILE = "airs_log.json"
SOAR_LOG_FILE = "soar_log.json"

# Create log files if they don't exist
for file in [AIRS_LOG_FILE, SOAR_LOG_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump([], f)

# === Alert Schema ===
class Alert(BaseModel):
    event_type: str
    timestamp: float
    pid: int | None = None
    process_name: str | None = None
    cmdline: list[str] | None = None
    admin_privileges: bool | None = None
    old_path: str | None = None
    new_path: str | None = None
    old_extension: str | None = None
    new_extension: str | None = None
    file_path: str | None = None
    malicious_score: int | None = None
    matched_keywords: list[str] | None = None

# === Append Alert or Response to File ===
def append_log(filepath, data):
    with open(filepath, "r+") as f:
        log = json.load(f)
        log.append(data)
        f.seek(0)
        json.dump(log, f, indent=2)

# === SOAR Playbook ===
def run_playbook(alert: Alert):
    actions = []

    if alert.event_type == "bat_execution":
        if alert.admin_privileges:
            actions.append("Isolate system: High-risk admin .bat execution")
        else:
            actions.append("Log .bat usage for audit")

    elif alert.event_type == "new_bat_created":
        if alert.malicious_score and alert.malicious_score > 2:
            actions.append("Quarantine .bat file")
            actions.append("Forward for sandbox analysis")
        else:
            actions.append("Flag for review")

    elif alert.event_type == "file_format_change":
        actions.append("Trigger backup snapshot")
        actions.append("Notify SOC team")

    else:
        actions.append("Unknown event type - log only")

    return actions

# === AIRS Endpoint to Receive Alerts ===
@app.post("/airs/alert")
async def receive_alert(alert: Alert):
    alert_data = alert.dict()
    alert_data["received_at"] = datetime.utcnow().isoformat()
    append_log(AIRS_LOG_FILE, alert_data)

    # Trigger SOAR playbook
    actions = run_playbook(alert)
    soar_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": alert.event_type,
        "actions_taken": actions
    }
    append_log(SOAR_LOG_FILE, soar_entry)

    return {"status": "received", "soar_actions": actions}

# === Log Viewing Endpoints ===
@app.get("/airs/log")
def view_airs_log():
    with open(AIRS_LOG_FILE) as f:
        return json.load(f)

@app.get("/soar/log")
def view_soar_log():
    with open(SOAR_LOG_FILE) as f:
        return json.load(f)
