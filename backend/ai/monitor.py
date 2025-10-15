import psutil
import time
import joblib
import os
import math
import collections
import pandas as pd
import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import winreg  # For registry checks on Windows

from src.pe_feature_extractor import extract_pe_features   # static PE feature extractor

# ======== GLOBALS ========
MODELS = Path("models")

# Load behavior model + metadata
behavior_model = joblib.load(MODELS / "behavior_model.pkl")
behavior_meta = json.loads((MODELS / "behavior_meta.json").read_text())
beh_cols = behavior_meta["feature_names"]

# Load PE model + metadata
pe_model = joblib.load(MODELS / "pe_model.pkl")
pe_meta = json.loads((MODELS / "pe_meta.json").read_text())
pe_cols = pe_meta["feature_names"]

# Cache PE scores
recent_file_scores = {}  # {filepath: (score, ts)}

# Honeypot folders to monitor
HONEYPOT_FOLDERS = [
    str(Path.home() / "Desktop"),
    str(Path.home() / "Documents"),
    str(Path.home() / "Downloads"),
]

# ======== FILE ACTIVITY HANDLER ========
class FileActivityHandler(FileSystemEventHandler):
    def __init__(self, folder):
        super().__init__()
        self.folder = folder
        self.event_count = 0

    def on_any_event(self, event):
        self.event_count += 1

        # NEW: when an executable file appears/changes, score with PE model
        if event.is_directory:
            return
        if event.event_type in ("created", "modified") and event.src_path.lower().endswith(
            (".exe", ".dll", ".msi", ".bat", ".ps1", ".vbs", ".scr", ".bin", ".com", ".cmd")
        ):
            try:
                df = extract_pe_features(event.src_path, pe_cols)
                pe_prob = pe_model.predict_proba(df)[0, 1]
                recent_file_scores[event.src_path] = (float(pe_prob), time.time())
                print(f"[PE Score] {os.path.basename(event.src_path)} -> {pe_prob:.2f}")
            except Exception as e:
                print(f"[PE Scan Error] {event.src_path}: {e}")

# ======== FEATURE FUNCTIONS ========
def get_process_count_change(interval=1):
    count1 = len(psutil.pids())
    time.sleep(interval)
    count2 = len(psutil.pids())
    return count2 - count1

def file_entropy(file_path):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        if not data:
            return 0
        entropy = 0
        for x in range(256):
            p_x = data.count(bytes([x])) / len(data)
            if p_x > 0:
                entropy -= p_x * math.log2(p_x)
        return entropy
    except:
        return 0

def avg_entropy_in_folder(folder):
    try:
        files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        if not files:
            return 0
        entropies = [file_entropy(f) for f in files]
        return sum(entropies) / len(entropies)
    except:
        return 0

def extension_anomaly_score(folder):
    try:
        exts = [os.path.splitext(f)[1] for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        counter = collections.Counter(exts)
        if not counter:
            return 0
        rare_exts = [ext for ext, count in counter.items() if count < 3]
        return len(rare_exts) / len(exts)
    except:
        return 0

def check_registry_modifications():
    suspicious_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "DisableTaskMgr"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "DisableRegistryTools")
    ]
    for hive, path, key in suspicious_keys:
        try:
            reg = winreg.OpenKey(hive, path)
            val, _ = winreg.QueryValueEx(reg, key)
            if int(val) == 1:
                return 1
        except FileNotFoundError:
            continue
    return 0

def thread_creation_rate(interval=1):
    threads_before = sum(p.num_threads() for p in psutil.process_iter(['num_threads']))
    time.sleep(interval)
    threads_after = sum(p.num_threads() for p in psutil.process_iter(['num_threads']))
    return threads_after - threads_before

# ======== MONITOR FUNCTION ========
def monitor_system(interval=2):
    handlers = []
    observer = Observer()

    # Attach a handler for each honeypot folder
    for folder in HONEYPOT_FOLDERS:
        if os.path.exists(folder):
            handler = FileActivityHandler(folder)
            handlers.append(handler)
            observer.schedule(handler, folder, recursive=True)
            print(f"🔍 Watching folder: {folder}")
        else:
            print(f"⚠️ Skipping missing folder: {folder}")

    observer.start()

    prev_sent = psutil.net_io_counters().bytes_sent
    prev_recv = psutil.net_io_counters().bytes_recv

    try:
        while True:
            cpu = psutil.cpu_percent(interval=interval)
            file_rate = sum(h.event_count for h in handlers) / interval
            for h in handlers:
                h.event_count = 0

            net = psutil.net_io_counters()
            sent_rate = (net.bytes_sent - prev_sent) / interval
            recv_rate = (net.bytes_recv - prev_recv) / interval
            prev_sent = net.bytes_sent
            prev_recv = net.bytes_recv
            net_usage = sent_rate + recv_rate

            proc_change = get_process_count_change(0)
            avg_entropy = sum(avg_entropy_in_folder(h.folder) for h in handlers) / max(1, len(handlers))
            ext_anomaly = sum(extension_anomaly_score(h.folder) for h in handlers) / max(1, len(handlers))
            reg_mod = check_registry_modifications()
            thread_rate = thread_creation_rate(0)

            # === Behavior model prediction ===
            beh_row = {c: 0 for c in beh_cols}
            beh_row.update({
                "cpu": cpu,
                "file_rate": file_rate,
                "net_usage": net_usage,
                "proc_change": proc_change,
                "avg_entropy": avg_entropy,
                "ext_anomaly": ext_anomaly,
                "reg_mod": reg_mod,
                "thread_rate": thread_rate,
            })
            beh_df = pd.DataFrame([[beh_row.get(c, 0) for c in beh_cols]], columns=beh_cols)
            probs = behavior_model.predict_proba(beh_df)[0]
            beh_prob = probs[1] if len(probs) > 1 else probs[0]

            # === Get recent PE score (last 60s) ===
            now = time.time()
            pe_probs = [p for (p, ts) in recent_file_scores.values() if now - ts < 60]
            pe_prob = max(pe_probs) if pe_probs else 0.0

            # === Hybrid fusion ===
            W_BEH, W_PE = 0.6, 0.4
            hybrid_score = W_BEH * beh_prob + W_PE * pe_prob
            THRESHOLD = 0.75

            # === Rule-based detection ===
            suspicious = (
                cpu > 90 and file_rate > 20 or
                avg_entropy > 7.5 or
                ext_anomaly > 0.3 or
                reg_mod == 1 or
                proc_change > 15 or
                thread_rate > 50
            )

            if hybrid_score >= THRESHOLD or suspicious:
                print(f"⚠️ ALERT: Potential ransomware! "
                      f"(hybrid={hybrid_score:.2f} | beh={beh_prob:.2f} | pe={pe_prob:.2f}) "
                      f"CPU={cpu:.2f}% | Files/s={file_rate:.2f} | Net={(net_usage/1e6):.2f}MB/s")
            else:
                print(f"✅ Safe (hybrid={hybrid_score:.2f}) "
                      f"CPU={cpu:.2f}% | Files/s={file_rate:.2f} | Net={(net_usage/1e6):.2f}MB/s")

    finally:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    monitor_system()
