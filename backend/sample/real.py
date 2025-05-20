import psutil
import os
import json
import time
import ctypes
import threading
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# === CONFIGURATION ===
MONITOR_PATH = r"C:\Users\vihan\Downloads"
SOAR_ENDPOINT = "http://localhost:8001/airs/alert"  # SOAR System endpoint

alerts = []
app = FastAPI()

MALICIOUS_KEYWORDS = [
    "powershell -enc", "certutil", "bitsadmin", "invoke-webrequest",
    "regsvr32", "mshta", "rundll32", "vssadmin", "wmic shadowcopy", "bcdedit", "cipher",
    "schtasks", "attrib +h +s", "setx", "cmd /c", "base64", "goto :", "pause >nul",
    "ren *.doc *.locked", "aescrypt", "openssl", "net use", "psexec", "taskkill", "net stop"
]

# === Admin Check ===
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# === Send alert to SOAR ===
def store_alert(data):
    alerts.append(data)
    print("[ALERT]", json.dumps(data, indent=2))

    try:
        response = requests.post(SOAR_ENDPOINT, json=data)
        if response.status_code == 200:
            print("[SOAR] Action taken:", response.json()["soar_actions"])
        else:
            print(f"[SOAR ERROR] Status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[SOAR] Failed to connect: {e}")

# === Scan for Ransomware in BAT ===
def scan_bat_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().lower()
            matched = [kw for kw in MALICIOUS_KEYWORDS if kw in content]
            return {
                "malicious_score": len(matched),
                "matched_keywords": matched
            }
    except Exception as e:
        return {
            "malicious_score": -1,
            "error": str(e),
            "matched_keywords": []
        }

# === BAT Execution Detector ===
def detect_bat_processes():
    seen_pids = set()
    while True:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any(arg.endswith('.bat') for arg in proc.info['cmdline']):
                    if proc.info['pid'] not in seen_pids:
                        seen_pids.add(proc.info['pid'])
                        alert = {
                            "event_type": "bat_execution",
                            "pid": proc.info['pid'],
                            "process_name": proc.info['name'],
                            "cmdline": proc.info['cmdline'],
                            "admin_privileges": is_admin(),
                            "timestamp": time.time()
                        }
                        store_alert(alert)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        time.sleep(3)

# === Watchdog for File Monitoring ===
class FileEventHandler(FileSystemEventHandler):
    def on_moved(self, event):
        if event.is_directory:
            return
        old_ext = os.path.splitext(event.src_path)[1]
        new_ext = os.path.splitext(event.dest_path)[1]
        if old_ext != new_ext:
            alert = {
                "event_type": "file_format_change",
                "old_path": event.src_path,
                "new_path": event.dest_path,
                "old_extension": old_ext,
                "new_extension": new_ext,
                "timestamp": time.time()
            }
            store_alert(alert)

    def on_created(self, event):
        if event.is_directory:
            return
        filepath = event.src_path
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".bat":
            result = scan_bat_file(filepath)
            alert = {
                "event_type": "new_bat_created",
                "file_path": filepath,
                "malicious_score": result.get("malicious_score"),
                "matched_keywords": result.get("matched_keywords"),
                "timestamp": time.time()
            }
            store_alert(alert)

# === Start File Watch ===
def start_file_observer(path):
    event_handler = FileEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path=path, recursive=True)
    observer.start()
    #  Do not block with observer.join()

# === API Endpoint ===
@app.get("/alerts")
def get_alerts():
    return JSONResponse(content={"alerts": alerts})

# === Start Background Threads ===
@app.on_event("startup")
def start_monitoring():
    threading.Thread(target=detect_bat_processes, daemon=True).start()
    threading.Thread(target=start_file_observer, args=(MONITOR_PATH,), daemon=True).start()
