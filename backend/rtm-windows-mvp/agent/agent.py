import os, json, time, hmac, hashlib, socket, threading, queue
from datetime import datetime, timezone
from pathlib import Path
import sys
import yaml, psutil

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import win32evtlog, win32con
import wmi

def rpath(rel: str) -> str:
    """
    Resolve a path that works both for normal Python and a PyInstaller-frozen EXE.
    For bundled data (via --add-data), the files are under sys._MEIPASS.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return str(base / rel)

# --- Load config next to agent.py / agent.exe (bundled by --add-data) ---
CFG = yaml.safe_load(Path(rpath("config.yaml")).read_text())
HMAC_KEY = os.environ.get(CFG["security"]["hmac_key_env"], "dev-change-me").encode()

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
    if caf_path.exists():
        client.tls_set(ca_certs=str(caf_path))
    else:
        print(
            f"Warning: MQTT CA certificate not found at {caf_path}. Using system trust store. "
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
    CAFILE = CFG["outbound"]["https"].get("cafile")
    SSL_CTX = None
    if HTTPS_URL.lower().startswith("https://"):
        if CAFILE and os.path.exists(CAFILE):
            SSL_CTX = ssl.create_default_context(cafile=CAFILE)
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

class FSHandler(FileSystemEventHandler):
    def on_created(self, e): self._emit(e, "create")
    def on_modified(self, e): self._emit(e, "write")
    def _emit(self, e, subtype):
        if e.is_directory: return
        count = BURST.hit()
        ext = os.path.splitext(e.src_path)[1].lower()
        sev = 1
        if ext in set(CFG["agent"]["ext_watchlist"]): sev = max(sev,2)
        if count > CFG["agent"]["file_burst_threshold_per_sec"]: sev = max(sev,3)
        EVENTS.put(ev_base("file", subtype, {"path":e.src_path,"ext":ext,"rate":count}, sev))

def start_file_watch():
    obs = Observer()
    h = FSHandler()
    for p in CFG["agent"]["watch_paths"]:
        obs.schedule(h, p, recursive=True)
    obs.start()
    return obs

# ---------- WMI process starts ----------
def watch_processes():
    c = wmi.WMI()
    watcher = c.watch_for(notification_type="Creation", wmi_class="Win32_Process")
    suspicious = {"powershell.exe","wscript.exe","cscript.exe","cmd.exe","mshta.exe"}
    while not STOP.is_set():
        try:
            p = watcher(timeout_ms=1000)
            if not p: continue
            name = (p.Caption or "").lower()
            sev = 2 if name in suspicious else 1
            EVENTS.put(ev_base("process","start", {"pid":p.ProcessId,"name":name,"cmdline":p.CommandLine}, sev))
        except wmi.x_wmi_timed_out:
            continue
        except Exception:
            time.sleep(0.5)

# ---------- Event Log tail (Sysmon + PowerShell) ----------
def tail_channel(channel, query="*"):
    h = win32evtlog.EvtQuery(channel, win32evtlog.EvtQueryForwardDirection, query)
    while not STOP.is_set():
        try:
            for ev in win32evtlog.EvtNext(h, 8, 1000):
                xml = win32evtlog.EvtRender(ev, win32evtlog.EvtRenderEventXml)
                parse_emit(channel, xml)
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

def dispatcher():
    while not STOP.is_set():
        try:
            evt = EVENTS.get(timeout=1)
            score = 0
            if evt["type"]=="file" and evt["data"].get("rate",0) >= CFG["agent"]["file_burst_threshold_per_sec"]: score += 40
            if evt["type"]=="process" and evt["data"].get("name") in ["powershell.exe","wscript.exe","cscript.exe","mshta.exe"]: score += 30
            if evt["subtype"] in ["service_install","vss_delete"]: score += 50
            evt["signals"]["score"] = min(100, score)
            if score >= 70: evt["severity"] = max(evt["severity"], 3)
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
        threading.Thread(target=tail_channel, args=("Microsoft-Windows-Sysmon/Operational","*"), daemon=True),
        threading.Thread(target=tail_channel, args=("Microsoft-Windows-PowerShell/Operational","*"), daemon=True),
        threading.Thread(target=dispatcher, daemon=True),
    ]
    for t in threads: t.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        STOP.set(); obs.stop(); obs.join()

if __name__ == "__main__":
    main()