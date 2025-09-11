## 🛡️ Real-Time Ransomware Detection & SOAR Alerting System

This project contains two main components working together to detect ransomware-related activity and respond automatically:

1. **Real-Time Monitoring Service** (`real.py`) - watches for suspicious `.bat` files, file extension changes, and running commands.
2. **SOAR System** (`airs_soar_server.py`) - a FastAPI-based endpoint that receives alerts and performs automated incident response actions (e.g. quarantine, log, or notify).

> ⚠️ Built for **Windows**, powered by `FastAPI`, `watchdog`, `psutil`, and `requests`.

---

## 📂 Features

### Real-Time Monitor (`real.py`)

* 🕵️ Monitors `.bat` file creation and renaming
* 🧠 Scans files for malicious keywords
* 🔐 Detects if user has Admin privileges
* 📤 Sends alert to SOAR system via HTTP POST
* 🌐 Exposes `/alerts` API to view alert history
* 🔍 Customizable directory monitoring using `watchdog`
* 🧬 **Entropy analysis and WannaCry detection with automated containment playbooks**

### SOAR System (`airs_soar_server.py`)

* 📉 Receives alerts from the monitoring system
* ✅ Performs mock responses (e.g., log, quarantine, alert)
* ⚙️ Easily extendable to execute real security scripts

---

## 📁 Folder Structure

```
project/
│
├── real.py                # Real-time monitoring agent
├── airs_soar_server.py    # SOAR FastAPI alert receiver
├── requirements.txt       # Python dependencies
├── README.md              # This file
```

---

## 🧪 Requirements

* Python 3.10+
* OS: Windows 10 or 11

### Install Dependencies

```bash
pip install -r requirements.txt
```

Or:

```bash
pip install fastapi watchdog psutil uvicorn requests
```

---

## 🚀 How to Run

### 1. Start SOAR Receiver (airs\_soar\_server.py)

```bash
uvicorn airs_soar_server:app --reload --port 8001
```

### 2. Start Real-Time Monitor (real.py)

```bash
uvicorn real:app --reload --port 8000
```

Make sure both are running at the same time.

### 3. Customize Monitoring Path (Optional)

By default, the monitor scans this path:

```python
MONITOR_PATH = r"C:\\Users\\vihan\\Downloads"
```

You can change it in `real.py` to any folder you want to monitor.

---

## 🛡️ SOAR System API

### `POST /airs/alert`

Receives alerts from real-time system.

**Example request from `real.py`:**

```json
{
  "event_type": "bat_execution",
  "pid": 4432,
  "process_name": "cmd.exe",
  "cmdline": ["cmd.exe", "/C", "malware.bat"],
  "admin_privileges": true,
  "timestamp": 1747703332.21
}
```

**Example response:**

```json
{
  "soar_actions": ["log", "alert"]
}
```

---

## 🌐 Monitor API

### `GET /alerts`

Returns all alerts seen by `real.py`

**Example:**

```bash
curl http://localhost:8000/alerts
```

---

## 🧪 Test Script

Create this `.bat` file in your `Downloads` folder:

```bat
powershell -enc ZXZpbA==
cipher /w:C:\
schtasks /create /tn "stealer" /tr "bad.exe"
```

You should see alerts in both terminals.

---

## ✅ Future Enhancements

* Real quarantine script (move file to secure location)
* Admin-only enforcement rules
* Add PowerShell and EXE file support
* Email/Slack/Telegram alerting
* SQLite or MongoDB backend for alert logs

---

