import os, json, time, hmac, hashlib, socket, threading, queue
from datetime import datetime, timezone
from pathlib import Path
import sys
import yaml, psutil, math
from collections import Counter

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import win32evtlog, win32con
import pywintypes          # NEW: needed to catch specific win32 errors
import pythoncom           # NEW: for COM init in WMI thread
import wmi

# Import SOAR/response helpers.  These live alongside this file and provide
# declarative playbook loading and execution functionality.  See
# ``response.py`` for details.
from response import (
    load_playbooks,
    match_playbooks,
    execute_actions,
    default_notify_callback,
    quarantine_file,   # <-- add this
)


def rpath(rel: str) -> str:
    """Return a path to bundled resource ``rel``.

    When running under PyInstaller the temporary extraction directory lives in
    ``sys._MEIPASS``.  For normal execution we resolve relative to the current
    file's directory.  This helper is still used for bundled data such as
    playbooks.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return str(base / rel)


def config_path() -> Path:
    """Return the location of ``config.yaml``.

    The configuration should live alongside the running script or frozen
    executable so that users can edit it without rebuilding the binary.  When
    packaged with PyInstaller, ``sys.executable`` points to the compiled
    executable which we use to resolve the path.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).with_name("config.yaml")
    return Path(__file__).with_name("config.yaml")


# Load config from external file so it can be modified at runtime
CFG_PATH = config_path()
CFG = yaml.safe_load(CFG_PATH.read_text())
HMAC_KEY = os.environ.get(CFG["security"]["hmac_key_env"], "dev-change-me").encode()

# Load response playbooks once at startup.  Playbooks live under the
# ``playbooks`` directory next to ``agent.py`` and are read using
# ``rpath`` so that bundling with PyInstaller works correctly.  If the
# directory is missing or empty, the returned list will be empty and no
# automated responses will fire.
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

    # Resolve MQTT CA certificate path and warn/fallback when missing
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
        print(
            f"[warn] MQTT CA certificate not found or empty at {caf_path}. Using system trust store. "
            "Place the certificate there or update outbound.mqtt.cafile in config.yaml."
        )
        client.tls_set()
    client.connect(CFG["outbound"]["mqtt"]["host"], CFG["outbound"]["mqtt"]["port"], keepalive=30)
    client.loop_start()

    def publish(evt):
        evt["hmac"] = sign(evt)
        payload = json.dumps(evt)
        with PUB_LOCK:
            client.publish("rtm/events", payload, qos=1, retain=False)

else:
    # HTTPS (also safe for http:// — we only make an SSL context when HTTPS is used)
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
            # Fallback to system trust if no cafile provided
            SSL_CTX = ssl.create_default_context()

    def publish(evt):
        evt["hmac"] = sign(evt)
        data = json.dumps(evt).encode()
        req = urllib.request.Request(HTTPS_URL, data=data, headers={"Content-Type":"application/json"})
        if SSL_CTX is not None:
            urllib.request.urlopen(req, context=SSL_CTX, timeout=5).read()
        else:
            urllib.request.urlopen(req, timeout=5).read()

# ---------- file watcher ----------
class Burst:
    def __init__(self): self.c=0; self.t=int(time.time()); self.lock=threading.Lock()
    def hit(self):
        with self.lock:
            now=int(time.time())
            if now!=self.t: self.c=0; self.t=now
            self.c+=1; return self.c

BURST = Burst()


def calc_entropy(path: str, max_bytes: int = 65536) -> float:
    """Return an approximate Shannon entropy for the beginning of ``path``.

    Only the first ``max_bytes`` bytes are read to avoid heavy I/O.  If the
    file cannot be read, ``0.0`` is returned.
    """
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

# ---------- resource monitor (CPU/Disk) ----------
def monitor_resources():
    """Periodically sample process CPU and disk write usage.

    This function inspects all running processes and emits resource
    events when a process exceeds the configured CPU or I/O thresholds.
    Thresholds are defined in the ``agent`` section of ``config.yaml``.
    """
    cpu_thr = CFG["agent"].get("cpu_usage_threshold", 80)
    io_thr = CFG["agent"].get("io_write_threshold_bytes", 50 * 1024 * 1024)
    # Prime the CPU percentage counters to obtain meaningful values on the next call
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
        # Sleep for a short interval before sampling again
        time.sleep(5)

class FSHandler(FileSystemEventHandler):
    def on_created(self, e):
        self._emit(e, "create", path=e.src_path)

    def on_modified(self, e):
        self._emit(e, "write", path=e.src_path)

    def on_moved(self, e):
        # catch renames; look at the DESTINATION path
        if e.is_directory:
            return
        self._emit(e, "rename", path=e.dest_path, src=e.src_path)

    def _emit(self, e, subtype, path=None, src=None):
        # Ignore directory events
        if e.is_directory:
            return

        # Path we evaluate (dest for renames)
        p = path or e.src_path

        # Avoid feedback loops: ignore anything under the quarantine directory
        try:
            from response import QUARANTINE_DIR
            if str(Path(p)).lower().startswith(str(QUARANTINE_DIR).lower()):
                return
        except Exception:
            pass

        # Burst counter and extension
        count = BURST.hit()
        ext = os.path.splitext(p)[1].lower()

        # Base severity
        sev = 1
        try:
            watch_exts = set(x.lower() for x in CFG["agent"].get("ext_watchlist", []))
        except Exception:
            watch_exts = set()

        # High severity for watch-listed ransomware extensions
        if ext in watch_exts:
            sev = max(sev, 3)

        # High severity when file churn exceeds threshold
        if count > CFG["agent"].get("file_burst_threshold_per_sec", 120):
            sev = max(sev, 3)

        # --- Step 4: early bump for CREATE/RENAME inside quarantine_on_create paths ---
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
        # --- end Step 4 ---

        # Build event payload (include src for rename)
        data = {"path": p, "ext": ext, "rate": count}
        if src and subtype == "rename":
            data["src"] = src

        # Approximate Shannon entropy for create/write events to spot
        # encrypted payloads characteristic of ransomware.
        if subtype in ("create", "write"):
            data["entropy"] = round(calc_entropy(p), 2)

        EVENTS.put(ev_base("file", subtype, data, sev))


def start_file_watch():
    obs = Observer()
    h = FSHandler()
    for p in CFG["agent"]["watch_paths"]:
        try:
            obs.schedule(h, p, recursive=True)
        except Exception as e:
            print(f"[warn] cannot watch {p}: {e}")
    obs.start()
    return obs

# ---------- WMI process starts (COM-initialised thread) ----------
def watch_processes():
    # NEW: Initialize COM for this thread to avoid x_wmi_uninitialised_thread
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
                sev = 2 if name in suspicious else 1
                EVENTS.put(ev_base("process","start", {"pid":p.ProcessId,"name":name,"cmdline":p.CommandLine}, sev))
            except wmi.x_wmi_timed_out:
                continue
            except Exception as e:
                # brief backoff on unexpected WMI hiccups
                time.sleep(0.5)
    finally:
        pythoncom.CoUninitialize()

# ---------- Event Log tail (Sysmon + PowerShell) ----------
def tail_channel(channel, query="*"):
    # Guard: handle missing channels gracefully (15007)
    try:
        h = win32evtlog.EvtQuery(channel, win32evtlog.EvtQueryForwardDirection, query)
    except pywintypes.error as e:
        if getattr(e, "winerror", None) == 15007:
            print(f"[warn] Event log channel missing: {channel} — skipping.")
            return
        raise

    while not STOP.is_set():
        try:
            for ev in win32evtlog.EvtNext(h, 8, 1000):
                xml = win32evtlog.EvtRender(ev, win32evtlog.EvtRenderEventXml)
                parse_emit(channel, xml)
        except pywintypes.error as e:
            # If the handle/channel becomes invalid mid-run, bail out cleanly.
            if getattr(e, "winerror", None) == 15007:
                print(f"[warn] Channel disappeared: {channel} — exiting tail.")
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
    if "vssadmin delete shadows" in lx: subtype, sev = "vss_delete", 3
    EVENTS.put(ev_base("system", subtype, {"channel":channel, "snippet":xml[:1000]}, sev))

# ---------- dispatcher / scoring ----------
EVENTS = queue.Queue()
STOP = threading.Event()


def watch_config_and_restart():
    """Monitor the config file for changes and restart the agent when modified."""
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
            score = 0
            if evt["type"] == "file" and evt["data"].get("rate", 0) >= CFG["agent"]["file_burst_threshold_per_sec"]:
                score += 40
            # Entropy-based detection of encrypted payloads
            if evt["type"] == "file" and evt["data"].get("entropy", 0) >= CFG["agent"].get("entropy_threshold", 7.5):
                score += 40
                evt["signals"]["ioc"].append("high_entropy")
            if evt["type"] == "process" and evt["data"].get("name") in [
                "powershell.exe",
                "wscript.exe",
                "cscript.exe",
                "mshta.exe",
                "mssecsvc.exe",
                "tasksche.exe",
                "taskdl.exe",
                "taskse.exe",
            ]:
                score += 30
            if evt["subtype"] in ["service_install", "vss_delete"]:
                score += 50
            # Resource events contribute moderately to the score
            if evt["type"] == "resource":
                # high CPU/disk write events are considered early indicators of encryption or abuse
                score += 20
            evt["signals"]["score"] = min(100, score)
            if score >= 70:
                evt["severity"] = max(evt["severity"], 3)

            # Dedicated detection of WannaCry-style indicators
            indicator = None
            if evt["type"] == "file" and evt["data"].get("ext") in {".wnry", ".wncry", ".wcry"}:
                indicator = {"indicator": "file_extension", "path": evt["data"].get("path")}
            if evt["type"] == "process" and evt["data"].get("name") in {"mssecsvc.exe", "tasksche.exe", "taskdl.exe", "taskse.exe"}:
                indicator = {"indicator": "process", "name": evt["data"].get("name"), "pid": evt["data"].get("pid")}
            if indicator:
                wc_evt = ev_base("ransomware", "wannacry", indicator, 4)
                EVENTS.put(wc_evt)

            # --- Quarantine on CREATE/RENAME/WRITE inside configured paths (no playbook needed) ---
            try:
                qcfg  = (CFG.get("agent") or {}).get("quarantine_on_create") or {}
                enable = bool(qcfg.get("enable"))
                if enable and evt.get("type") == "file" and evt.get("subtype") in ("create", "rename", "write"):
                    data   = evt.get("data") or {}
                    path   = (data.get("path") or "")
                    ext    = (data.get("ext")  or "").lower()
                    exts   = set(x.lower() for x in (qcfg.get("exts")  or []))
                    bases  = [b.lower() for b in (qcfg.get("paths") or [])]

                    if path:
                        plower = path.lower()

                        # Skip if already inside your quarantine folder (prevents loops)
                        try:
                            from response import QUARANTINE_DIR
                            if plower.startswith(str(QUARANTINE_DIR).lower()):
                                raise StopIteration
                        except Exception:
                            pass

                        # If extensions list is empty -> match all; else require membership
                        ext_ok  = (not exts) or (ext in exts)
                        path_ok = (not bases) or any(plower.startswith(base) for base in bases)

                        if ext_ok and path_ok:
                            # Ensure it shows up with MIN_SEVERITY filters
                            evt["severity"] = max(evt.get("severity", 1), 3)
                            quarantine_file(path)
            except StopIteration:
                pass
            except Exception:
                # Never let response actions crash the dispatcher
                pass
            # --- end quarantine-on-create ---

            # --- Built-in quarantine for high-severity watched extensions (bypass playbooks) ---
            try:
                if evt.get("type") == "file" and evt.get("severity", 1) >= 3:
                    data = evt.get("data") or {}
                    path = data.get("path")
                    ext  = (data.get("ext") or "").lower()
                    watch_exts = set(x.lower() for x in CFG["agent"].get("ext_watchlist", []))
                    if path and ext in watch_exts:
                        quarantine_file(path)
            except Exception:
                # Never let response actions crash the dispatcher
                pass
            # --- end built-in quarantine ---

            # Execute SOAR playbooks when applicable.  Any exceptions raised
            # during playbook matching or execution are swallowed to prevent
            # disruption of the dispatcher loop.
            try:
                triggered = match_playbooks(PLAYBOOKS, evt)
                if triggered:
                    execute_actions(evt, triggered, notify_callback=default_notify_callback)
            except Exception:
                pass

            try:
                publish(evt)
            except Exception:
                # TODO: add retry/backoff or spool-to-disk for robustness
                pass
        except queue.Empty:
            pass

def main():
    obs = start_file_watch()
    threads = [
        threading.Thread(target=watch_processes, daemon=True),
        threading.Thread(target=tail_channel, args=("Microsoft-Windows-Sysmon/Operational", "*"), daemon=True),
        threading.Thread(target=tail_channel, args=("Microsoft-Windows-PowerShell/Operational", "*"), daemon=True),
        threading.Thread(target=monitor_resources, daemon=True),
        threading.Thread(target=dispatcher, daemon=True),
        threading.Thread(target=watch_config_and_restart, daemon=True),
    ]
    for t in threads: t.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        STOP.set(); obs.stop(); obs.join()

if __name__ == "__main__":
    main()
