import os, json, time, hmac, hashlib, socket, threading, queue
from datetime import datetime, timezone
from pathlib import Path
import sys
import yaml, psutil, math
from collections import Counter, defaultdict

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import win32evtlog, win32con
import pywintypes
import pythoncom
import wmi

from response import (
    load_playbooks,
    match_playbooks,
    execute_actions,
    default_notify_callback,
    quarantine_file,
)


def rpath(rel: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return str(base / rel)


def config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).with_name("config.yaml")
    return Path(__file__).with_name("config.yaml")


CFG_PATH = config_path()
CFG = yaml.safe_load(CFG_PATH.read_text())
HMAC_KEY = os.environ.get(CFG["security"]["hmac_key_env"], "dev-change-me").encode()
PLAYBOOKS = load_playbooks(rpath("playbooks"))

def iso_now():
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

def sign(d):
    body = d.copy(); body.pop("hmac", None)
    msg = json.dumps(body, separators=(',',':'), sort_keys=True).encode()
    return hmac.new(HMAC_KEY, msg, hashlib.sha256).hexdigest()

def ev_base(etype, subtype, data, sev=1):
    return {
        "schema_version":"1.0",
        "source":"host",
        "host": {"id":CFG["agent"]["id"], "name":CFG["agent"]["name"],
                 "ip":socket.gethostbyname(socket.gethostname())},
        "time": iso_now(),
        "type": etype, "subtype": subtype, "severity": sev,
        "data": data, "signals": {"ioc":[], "score":0}, "hmac":""
    }

# ---------- outbound ----------
PUB_LOCK = threading.Lock()
if CFG["outbound"]["mode"] == "mqtt":
    import paho.mqtt.client as mqtt

    config_dir = Path(rpath("config.yaml")).parent
    caf_conf = CFG["outbound"]["mqtt"].get("cafile", "tls/ca.crt")
    caf_path = Path(caf_conf)
    if not caf_path.is_absolute():
        caf_path = (config_dir / caf_path).resolve()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"agent-{CFG['agent']['id']}")
    client.username_pw_set(CFG["outbound"]["mqtt"]["username"], CFG["outbound"]["mqtt"]["password"])
    if caf_path.exists() and caf_path.stat().st_size > 0:
        client.tls_set(ca_certs=str(caf_path))
    else:
        print(f"[warn] MQTT CA certificate not found or empty at {caf_path}. Using system trust store.")
        client.tls_set()
    client.connect(CFG["outbound"]["mqtt"]["host"], CFG["outbound"]["mqtt"]["port"], keepalive=30)
    client.loop_start()

    def publish(evt):
        evt["hmac"] = sign(evt)
        payload = json.dumps(evt)
        with PUB_LOCK:
            client.publish("rtm/events", payload, qos=1, retain=False)

else:
    import ssl, urllib.request

    HTTPS_URL = CFG["outbound"]["https"]["url"]
    CAFILE_CONF = CFG["outbound"]["https"].get("cafile")
    SSL_CTX = None
    if HTTPS_URL.lower().startswith("https://"):
        caf_path = None
        if CAFILE_CONF:
            caf_path = Path(CAFILE_CONF)
            if not caf_path.is_absolute():
                caf_path = (Path(rpath("config.yaml")).parent / caf_path).resolve()
        if caf_path and caf_path.exists() and caf_path.stat().st_size > 0:
            SSL_CTX = ssl.create_default_context(cafile=str(caf_path))
        else:
            SSL_CTX = ssl.create_default_context()

    def publish(evt):
        evt["hmac"] = sign(evt)
        data = json.dumps(evt).encode()
        req = urllib.request.Request(HTTPS_URL, data=data, headers={"Content-Type":"application/json"})
        if SSL_CTX is not None:
            urllib.request.urlopen(req, context=SSL_CTX, timeout=5).read()
        else:
            urllib.request.urlopen(req, timeout=5).read()

# ---------- NEW: File Activity Tracker ----------
class FileActivityTracker:
    """Track file operations per process to detect mass encryption"""
    def __init__(self, window_seconds=60):
        self.window = window_seconds
        self.renames = defaultdict(list)  # {pid: [(old, new, time), ...]}
        self.modifications = defaultdict(list)  # {pid: [(path, time), ...]}
        self.lock = threading.Lock()
    
    def track_rename(self, pid, old_path, new_path):
        if not pid:
            return
        with self.lock:
            now = time.time()
            self.renames[pid].append((old_path, new_path, now))
            self._cleanup(pid, now)
    
    def track_modification(self, pid, path):
        if not pid:
            return
        with self.lock:
            now = time.time()
            self.modifications[pid].append((path, now))
            self._cleanup(pid, now)
    
    def _cleanup(self, pid, now):
        """Remove entries outside the time window"""
        self.renames[pid] = [(o, n, t) for o, n, t in self.renames[pid] 
                             if now - t < self.window]
        self.modifications[pid] = [(p, t) for p, t in self.modifications[pid] 
                                    if now - t < self.window]
    
    def get_rename_count(self, pid):
        with self.lock:
            return len(self.renames.get(pid, []))
    
    def get_modification_count(self, pid):
        with self.lock:
            return len(self.modifications.get(pid, []))
    
    def check_extension_changes(self, pid):
        """Count how many times process changed file extensions"""
        with self.lock:
            renames = self.renames.get(pid, [])
            ext_changes = 0
            for old, new, _ in renames:
                old_ext = os.path.splitext(old)[1].lower()
                new_ext = os.path.splitext(new)[1].lower()
                if old_ext != new_ext and old_ext and new_ext:
                    ext_changes += 1
            return ext_changes

FILE_TRACKER = FileActivityTracker()

# ---------- burst counter ----------
class Burst:
    def __init__(self): self.c=0; self.t=int(time.time()); self.lock=threading.Lock()
    def hit(self):
        with self.lock:
            now=int(time.time())
            if now!=self.t: self.c=0; self.t=now
            self.c+=1; return self.c

BURST = Burst()


def calc_entropy(path: str, max_bytes: int = 65536) -> float:
    """Return Shannon entropy for the beginning of a file"""
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes)
        if not data:
            return 0.0
        freq = Counter(data)
        length = len(data)
        return -sum((c / length) * math.log2(c / length) for c in freq.values())
    except Exception:
        return 0.0


def advanced_entropy_check(path: str) -> dict:
    """Enhanced entropy analysis with multiple samples from different file positions"""
    try:
        file_size = os.path.getsize(path)
        if file_size == 0:
            return {"is_suspicious": False, "avg_entropy": 0.0, "samples": []}
        
        # Sample from beginning, middle, and end
        sample_positions = [0, file_size // 2, max(0, file_size - 65536)]
        entropies = []
        
        with open(path, "rb") as f:
            for pos in sample_positions:
                if pos >= file_size:
                    continue
                f.seek(pos)
                data = f.read(min(65536, file_size - pos))
                if data:
                    freq = Counter(data)
                    length = len(data)
                    ent = -sum((c/length) * math.log2(c/length) for c in freq.values())
                    entropies.append(ent)
        
        if not entropies:
            return {"is_suspicious": False, "avg_entropy": 0.0, "samples": []}
        
        avg_ent = sum(entropies) / len(entropies)
        # Encrypted files typically have high entropy across ALL samples
        is_suspicious = avg_ent > 7.3 and min(entropies) > 7.0
        
        return {
            "is_suspicious": is_suspicious,
            "avg_entropy": round(avg_ent, 2),
            "samples": [round(e, 2) for e in entropies],
            "min_entropy": round(min(entropies), 2)
        }
    except Exception:
        return {"is_suspicious": False, "avg_entropy": 0.0, "samples": []}


def detect_ransom_note(path: str) -> bool:
    """Check if file matches known ransom note patterns"""
    try:
        filename = Path(path).name.upper()
        note_patterns = CFG["agent"].get("ransomware_markers", {}).get("notes", [
            "README.txt", "HOW_TO_DECRYPT.txt", "DECRYPT_INSTRUCTIONS.html",
            "!!!READ_ME!!!.txt", "YOUR_FILES_ARE_ENCRYPTED.txt",
            "HELP_DECRYPT.txt", "HELP_RESTORE_FILES.txt", "HOW_TO_BACK_FILES.txt"
        ])
        
        for pattern in note_patterns:
            if pattern.upper() in filename:
                return True
        return False
    except Exception:
        return False


# ---------- resource monitor ----------
def monitor_resources():
    cpu_thr = CFG["agent"].get("cpu_usage_threshold", 80)
    io_thr = CFG["agent"].get("io_write_threshold_bytes", 50 * 1024 * 1024)
    
    for proc in psutil.process_iter():
        try:
            proc.cpu_percent(interval=None)
        except Exception:
            continue
    
    while not STOP.is_set():
        for proc in psutil.process_iter(['pid','name','cpu_percent','io_counters']):
            try:
                cpu = proc.cpu_percent(interval=None)
                if cpu >= cpu_thr:
                    EVENTS.put(ev_base("resource", "high_cpu", {
                        "pid": proc.info['pid'],
                        "name": proc.info.get('name', ''),
                        "cpu": cpu
                    }, 2))
                io = proc.info.get('io_counters')
                if io and hasattr(io, 'write_bytes') and io.write_bytes >= io_thr:
                    EVENTS.put(ev_base("resource", "high_disk_write", {
                        "pid": proc.info['pid'],
                        "name": proc.info.get('name', ''),
                        "bytes": io.write_bytes
                    }, 2))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        time.sleep(5)


# ---------- NEW: Enhanced file watcher ----------
class EnhancedFSHandler(FileSystemEventHandler):
    def on_created(self, e):
        self._emit(e, "create", path=e.src_path)

    def on_modified(self, e):
        self._emit(e, "write", path=e.src_path)

    def on_moved(self, e):
        if e.is_directory:
            return
        self._emit(e, "rename", path=e.dest_path, src=e.src_path)

    def _get_process_from_path(self, path):
        """Try to identify which process has the file open"""
        try:
            for proc in psutil.process_iter(['pid', 'open_files']):
                try:
                    open_files = proc.open_files()
                    if open_files:
                        for f in open_files:
                            if f.path.lower() == path.lower():
                                return proc.info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return None

    def _emit(self, e, subtype, path=None, src=None):
        if e.is_directory:
            return

        p = path or e.src_path

        # Avoid feedback loops
        try:
            from response import QUARANTINE_DIR
            if str(Path(p)).lower().startswith(str(QUARANTINE_DIR).lower()):
                return
        except Exception:
            pass

        # Track process activity
        pid = self._get_process_from_path(p)
        if pid:
            if subtype == "rename":
                FILE_TRACKER.track_rename(pid, src or p, p)
            else:
                FILE_TRACKER.track_modification(pid, p)
            
            # Check for mass file operations by single process
            mod_count = FILE_TRACKER.get_modification_count(pid)
            rename_count = FILE_TRACKER.get_rename_count(pid)
            ext_changes = FILE_TRACKER.check_extension_changes(pid)
            
            # Alert on suspicious process behavior
            if mod_count > 50 or rename_count > 25 or ext_changes > 20:
                try:
                    proc = psutil.Process(pid)
                    EVENTS.put(ev_base("ransomware", "mass_file_operation", {
                        "pid": pid,
                        "name": proc.name(),
                        "modifications": mod_count,
                        "renames": rename_count,
                        "extension_changes": ext_changes,
                        "cmdline": " ".join(proc.cmdline())[:500]
                    }, 4))
                except Exception:
                    pass

        count = BURST.hit()
        ext = os.path.splitext(p)[1].lower()

        sev = 1
        try:
            watch_exts = set(x.lower() for x in CFG["agent"].get("ext_watchlist", []))
        except Exception:
            watch_exts = set()

        # Check ransom note detection
        if detect_ransom_note(p):
            sev = 4
            EVENTS.put(ev_base("ransomware", "ransom_note_detected", {
                "path": p,
                "filename": Path(p).name
            }, 4))

        if ext in watch_exts:
            sev = max(sev, 3)

        if count > CFG["agent"].get("file_burst_threshold_per_sec", 50):
            sev = max(sev, 3)

        # Early bump for quarantine_on_create paths
        try:
            qcfg = (CFG.get("agent") or {}).get("quarantine_on_create") or {}
            if qcfg.get("enable") and subtype in ("create", "rename"):
                exts  = set(x.lower() for x in (qcfg.get("exts") or []))
                bases = [b.lower() for b in (qcfg.get("paths") or [])]
                plower = str(p).lower()
                ext_ok  = (not exts) or (ext in exts)
                path_ok = (not bases) or any(plower.startswith(base) for base in bases)
                if ext_ok and path_ok:
                    sev = max(sev, 3)
        except Exception:
            pass

        data = {"path": p, "ext": ext, "rate": count}
        if pid:
            data["pid"] = pid
        if src and subtype == "rename":
            data["src"] = src

        # Enhanced entropy check for creates/writes
        if subtype in ("create", "write"):
            entropy_result = advanced_entropy_check(p)
            data["entropy"] = entropy_result["avg_entropy"]
            data["entropy_samples"] = entropy_result["samples"]
            data["min_entropy"] = entropy_result.get("min_entropy", 0)
            
            if entropy_result["is_suspicious"]:
                sev = max(sev, 3)
                data["high_entropy_detected"] = True

        EVENTS.put(ev_base("file", subtype, data, sev))


def start_file_watch():
    obs = Observer()
    h = EnhancedFSHandler()
    for p in CFG["agent"]["watch_paths"]:
        try:
            obs.schedule(h, p, recursive=True)
        except Exception as e:
            print(f"[warn] cannot watch {p}: {e}")
    obs.start()
    return obs


# ---------- WMI process starts ----------
def detect_shadow_deletion(cmdline):
    """Detect shadow copy deletion and boot configuration tampering"""
    if not cmdline:
        return False
    
    cmdline_lower = cmdline.lower()
    dangerous_commands = [
        "vssadmin delete shadows",
        "vssadmin.exe delete shadows",
        "wmic shadowcopy delete",
        "wbadmin delete catalog",
        "bcdedit /set {default} recoveryenabled no",
        "bcdedit /set {default} bootstatuspolicy ignoreallfailures",
        "wbadmin delete systemstatebackup",
        "vssadmin resize shadowstorage"
    ]
    
    for cmd in dangerous_commands:
        if cmd.lower() in cmdline_lower:
            return True
    return False


def watch_processes():
    pythoncom.CoInitialize()
    try:
        c = wmi.WMI()
        watcher = c.watch_for(notification_type="Creation", wmi_class="Win32_Process")
        suspicious = {"powershell.exe","wscript.exe","cscript.exe","cmd.exe","mshta.exe",
                      "mssecsvc.exe","tasksche.exe","taskdl.exe","taskse.exe"}
        
        while not STOP.is_set():
            try:
                p = watcher(timeout_ms=1000)
                if not p:
                    continue
                
                name = (p.Caption or "").lower()
                cmdline = p.CommandLine or ""
                pid = p.ProcessId
                sev = 2 if name in suspicious else 1
                
                # Critical: Shadow copy deletion detection
                if detect_shadow_deletion(cmdline):
                    EVENTS.put(ev_base("ransomware", "shadow_deletion_attempt", {
                        "pid": pid,
                        "name": name,
                        "cmdline": cmdline
                    }, 4))
                    sev = 4
                
                # Check for encoded/obfuscated commands
                if name in {"powershell.exe", "cmd.exe"}:
                    if any(x in cmdline.lower() for x in ["encodedcommand", "-enc", "frombase64", "invoke-expression"]):
                        sev = max(sev, 3)
                
                EVENTS.put(ev_base("process","start", {
                    "pid": pid,
                    "name": name,
                    "cmdline": cmdline[:1000]
                }, sev))
                
            except wmi.x_wmi_timed_out:
                continue
            except Exception:
                time.sleep(0.5)
    finally:
        pythoncom.CoUninitialize()


# ---------- Event Log tail ----------
def tail_channel(channel, query="*"):
    try:
        h = win32evtlog.EvtQuery(channel, win32evtlog.EvtQueryForwardDirection, query)
    except pywintypes.error as e:
        if getattr(e, "winerror", None) == 15007:
            print(f"[warn] Event log channel missing: {channel} – skipping.")
            return
        raise

    while not STOP.is_set():
        try:
            for ev in win32evtlog.EvtNext(h, 8, 1000):
                xml = win32evtlog.EvtRender(ev, win32evtlog.EvtRenderEventXml)
                parse_emit(channel, xml)
        except pywintypes.error as e:
            if getattr(e, "winerror", None) == 15007:
                print(f"[warn] Channel disappeared: {channel} – exiting tail.")
                return
            time.sleep(1)
        except Exception:
            time.sleep(1)


def parse_emit(channel, xml):
    sev, subtype = 1, "win_event"
    lx = xml.lower()
    if "eventid>1<" in lx and "sysmon" in channel.lower(): subtype, sev = "sysmon_process_create", 2
    if "eventid>11<" in lx and "sysmon" in channel.lower(): subtype, sev = "sysmon_file_create", 2
    if "eventid>13<" in lx and "sysmon" in channel.lower(): subtype, sev = "sysmon_reg_set", 2
    if "eventid>4104<" in lx: subtype, sev = "ps_scriptblock", 2
    if "eventid>7045<" in lx or "eventid>4697<" in lx: subtype, sev = "service_install", 3
    if "vssadmin delete shadows" in lx: subtype, sev = "vss_delete", 4
    EVENTS.put(ev_base("system", subtype, {"channel":channel, "snippet":xml[:1000]}, sev))


# ---------- NEW: Registry monitoring ----------
def monitor_registry():
    """Monitor Windows registry for persistence mechanisms"""
    try:
        import winreg
    except ImportError:
        return
    
    pythoncom.CoInitialize()
    try:
        persistence_keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
        ]
        
        baseline = {}
        for hive, subkey in persistence_keys:
            try:
                key = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
                values = {}
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        values[name] = value
                        i += 1
                    except WindowsError:
                        break
                winreg.CloseKey(key)
                baseline[subkey] = values
            except Exception:
                pass
        
        while not STOP.is_set():
            time.sleep(10)
            for hive, subkey in persistence_keys:
                try:
                    key = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            if name not in baseline.get(subkey, {}):
                                EVENTS.put(ev_base("system", "registry_persistence", {
                                    "key": subkey,
                                    "name": name,
                                    "value": str(value)[:500]
                                }, 3))
                                baseline.setdefault(subkey, {})[name] = value
                            i += 1
                        except WindowsError:
                            break
                    winreg.CloseKey(key)
                except Exception:
                    pass
    finally:
        pythoncom.CoUninitialize()


# ---------- dispatcher / scoring ----------
EVENTS = queue.Queue()
STOP = threading.Event()


def calculate_threat_score(evt):
    """Enhanced weighted threat scoring system"""
    score = 0
    indicators = []
    
    # File-based indicators
    if evt["type"] == "file":
        rate = evt["data"].get("rate", 0)
        entropy = evt["data"].get("entropy", 0)
        min_entropy = evt["data"].get("min_entropy", 0)
        ext = evt["data"].get("ext", "")
        
        # Rapid file modifications (strongest single indicator)
        if rate >= CFG["agent"].get("file_burst_threshold_per_sec", 50):
            score += 50
            indicators.append("file_burst")
        
        # High entropy across all samples (encrypted content)
        if entropy >= CFG["agent"].get("entropy_threshold", 7.3) and min_entropy > 7.0:
            score += 40
            indicators.append("high_entropy_all_samples")
        elif entropy >= CFG["agent"].get("entropy_threshold", 7.3):
            score += 25
            indicators.append("high_entropy")
        
        # Suspicious extension
        watch_exts = set(x.lower() for x in CFG["agent"].get("ext_watchlist", []))
        if ext in watch_exts:
            score += 35
            indicators.append("suspicious_extension")
    
    # Process-based indicators
    if evt["type"] == "process":
        name = evt["data"].get("name", "").lower()
        cmdline = evt["data"].get("cmdline", "").lower()
        
        # Known ransomware executables (WannaCry indicators)
        if name in {"mssecsvc.exe", "tasksche.exe", "taskdl.exe", "taskse.exe"}:
            score += 60
            indicators.append("known_ransomware_process")
        
        # Script interpreters (potential dropper/executor)
        if name in {"powershell.exe", "wscript.exe", "cscript.exe", "mshta.exe"}:
            score += 25
            indicators.append("script_interpreter")
            
            # Obfuscation/encoding
            if any(x in cmdline for x in ["encodedcommand", "-enc", "frombase64", "invoke-expression"]):
                score += 20
                indicators.append("obfuscated_script")
    
    # System modification indicators
    if evt["subtype"] in ["vss_delete", "service_install"]:
        score += 55
        indicators.append(evt["subtype"])
    
    if evt["subtype"] == "shadow_deletion_attempt":
        score += 60
        indicators.append("shadow_deletion")
    
    # Resource abuse
    if evt["type"] == "resource":
        score += 15
        indicators.append("resource_spike")
    
    # Ransomware-specific detections
    if evt["type"] == "ransomware":
        if evt["subtype"] == "mass_file_operation":
            score += 65
        elif evt["subtype"] == "ransom_note_detected":
            score += 70
        else:
            score += 60
        indicators.append(f"ransomware_{evt['subtype']}")
    
    # Registry persistence
    if evt["subtype"] == "registry_persistence":
        score += 30
        indicators.append("registry_persistence")
    
    evt["signals"]["ioc"].extend(indicators)
    evt["signals"]["score"] = min(100, score)
    
    # Auto-escalate severity based on score
    if score >= 80:
        evt["severity"] = max(evt["severity"], 4)
    elif score >= 60:
        evt["severity"] = max(evt["severity"], 3)
    elif score >= 40:
        evt["severity"] = max(evt["severity"], 2)
    
    return score


def watch_config_and_restart():
    try:
        last = CFG_PATH.stat().st_mtime
    except FileNotFoundError:
        last = None
    while not STOP.is_set():
        try:
            current = CFG_PATH.stat().st_mtime
            if last is not None and current != last:
                print("[info] config.yaml changed; restarting...")
                os.execv(sys.executable, [sys.executable] + sys.argv)
            last = current
        except FileNotFoundError:
            pass
        time.sleep(1)


def dispatcher():
    while not STOP.is_set():
        try:
            evt = EVENTS.get(timeout=1)

            # Compute your weighted threat score (keeps your new logic)
            calculate_threat_score(evt)

            # Legacy WannaCry indicators (kept for compatibility)
            indicator = None
            if evt["type"] == "file" and evt["data"].get("ext") in {".wnry", ".wncry", ".wcry"}:
                indicator = {"indicator": "file_extension", "path": evt["data"].get("path")}
            if evt["type"] == "process" and evt["data"].get("name") in {"mssecsvc.exe", "tasksche.exe", "taskdl.exe", "taskse.exe"}:
                indicator = {"indicator": "process", "name": evt["data"].get("name"), "pid": evt["data"].get("pid")}
            if indicator:
                wc_evt = ev_base("ransomware", "wannacry", indicator, 4)
                EVENTS.put(wc_evt)

            # --- Quarantine on CREATE/RENAME/WRITE inside configured paths ---
            try:
                qcfg   = (CFG.get("agent") or {}).get("quarantine_on_create") or {}
                enable = bool(qcfg.get("enable"))
                if enable and evt.get("type") == "file" and evt.get("subtype") in ("create", "rename", "write"):
                    data  = evt.get("data") or {}
                    path  = (data.get("path") or "")
                    ext   = (data.get("ext")  or "").lower()
                    exts  = set(x.lower() for x in (qcfg.get("exts")  or []))
                    bases = [b.lower() for b in (qcfg.get("paths") or [])]

                    if path:
                        plower = path.lower()

                        # Skip if inside quarantine folder already
                        try:
                            from response import QUARANTINE_DIR
                            if plower.startswith(str(QUARANTINE_DIR).lower()):
                                raise StopIteration
                        except Exception:
                            pass

                        ext_ok  = (not exts) or (ext in exts)
                        path_ok = (not bases) or any(plower.startswith(base) for base in bases)

                        if ext_ok and path_ok:
                            # Ensure it shows up with min severity filters
                            evt["severity"] = max(evt.get("severity", 1), 3)
                            quarantine_file(path)
            except StopIteration:
                # Intentionally skip if the file is already quarantined
                pass
            except Exception:
                # Never let response actions crash the dispatcher
                pass
            # --- end quarantine-on-create ---

            # --- Built-in quarantine for high-severity watched extensions ---
            try:
                if evt.get("type") == "file" and evt.get("severity", 1) >= 3:
                    data = evt.get("data") or {}
                    path = data.get("path")
                    ext  = (data.get("ext") or "").lower()
                    watch_exts = set(x.lower() for x in CFG["agent"].get("ext_watchlist", []))
                    if path and ext in watch_exts:
                        quarantine_file(path)
            except Exception:
                # Keep dispatcher resilient
                pass
            # --- end built-in quarantine ---

            # Execute SOAR playbooks (this is where your start_backup action runs)
            try:
                triggered = match_playbooks(PLAYBOOKS, evt)
                if triggered:
                    execute_actions(evt, triggered, notify_callback=default_notify_callback)
            except Exception:
                pass

            # Publish out (HTTPS/MQTT), errors swallowed to keep loop alive
            try:
                publish(evt)
            except Exception:
                pass

        except queue.Empty:
            pass
