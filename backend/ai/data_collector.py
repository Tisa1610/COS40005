import psutil
import time
import os
import math
import collections
import pandas as pd
import argparse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import winreg  


class FileActivityHandler(FileSystemEventHandler):
    def __init__(self):
        self.event_count = 0

    def on_any_event(self, event):
        self.event_count += 1


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
    files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    if not files:
        return 0
    entropies = [file_entropy(f) for f in files]
    return sum(entropies) / len(entropies)

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


def collect_data(duration=60, interval=2, label=0, folder='monitor_folder'):
    os.makedirs(folder, exist_ok=True)
    handler = FileActivityHandler()
    observer = Observer()
    observer.schedule(handler, folder, recursive=True)
    observer.start()

    prev_sent = psutil.net_io_counters().bytes_sent
    prev_recv = psutil.net_io_counters().bytes_recv

    data = []
    try:
        for _ in range(int(duration / interval)):
            cpu = psutil.cpu_percent(interval=interval)
            file_rate = handler.event_count / interval
            handler.event_count = 0

            net = psutil.net_io_counters()
            sent_rate = (net.bytes_sent - prev_sent) / interval
            recv_rate = (net.bytes_recv - prev_recv) / interval
            prev_sent = net.bytes_sent
            prev_recv = net.bytes_recv
            net_usage = sent_rate + recv_rate

            proc_change = get_process_count_change(0)  # Already in loop
            avg_entropy = avg_entropy_in_folder(folder)
            ext_anomaly = extension_anomaly_score(folder)
            reg_mod = check_registry_modifications()
            thread_rate = thread_creation_rate(0)

            data.append([
                cpu, file_rate, net_usage, proc_change, avg_entropy,
                ext_anomaly, reg_mod, thread_rate, label
            ])

            print(f"CPU: {cpu:.2f}% | Files/s: {file_rate:.2f} | Net: {(net_usage/1e6):.2f} MB/s | "
                  f"Proc Δ: {proc_change} | Entropy: {avg_entropy:.2f} | ExtAnom: {ext_anomaly:.2f} | "
                  f"RegMod: {reg_mod} | Thread Δ: {thread_rate}")

    finally:
        observer.stop()
        observer.join()

    df = pd.DataFrame(data, columns=[
        "cpu", "file_rate", "net_usage", "proc_change",
        "avg_entropy", "ext_anomaly", "reg_mod", "thread_rate", "label"
    ])
    df.to_csv("system_data.csv", mode='a', index=False, header=not os.path.exists("system_data.csv"))
    print("Data collection complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ransomware Detection Data Collector")
    parser.add_argument("--duration", type=int, default=60, help="Total collection duration in seconds")
    parser.add_argument("--interval", type=int, default=2, help="Interval between measurements in seconds")
    parser.add_argument("--label", type=int, default=0, help="Label for data: 0 = normal, 1 = ransomware")
    parser.add_argument("--folder", type=str, default="monitor_folder", help="Folder to monitor for file activity")
    args = parser.parse_args()

    print(f"Collecting data... Duration={args.duration}s, Interval={args.interval}s, Label={args.label}")
    collect_data(duration=args.duration, interval=args.interval, label=args.label, folder=args.folder)
