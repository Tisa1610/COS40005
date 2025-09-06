"""
response.py
---------------

This module implements a simple SOAR (Security Orchestration, Automation and
Response) framework for the real‑time monitoring agent.  Playbooks are
defined in YAML files under the ``playbooks`` directory.  Each playbook
specifies a set of trigger conditions and a list of actions to execute
whenever an event matches the triggers.  Actions include terminating
offending processes, isolating the host from the network, quarantining
files, and emitting notifications back to the collector.

The goal of this module is to provide a declarative way to respond to
suspicious activity without having to hard‑code logic into the agent.  As
threat patterns evolve, responders can simply update or add playbooks
without recompiling the agent.  This design also paves the way for more
complex orchestration in the future, such as sandbox detonation or
interacting with backup systems.

Note: Network isolation and process killing are very sensitive operations.
Use them judiciously and test extensively in a controlled environment.
During development on non‑Windows platforms these functions will do
nothing (gracefully returning) to prevent accidental disruption.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import psutil
import yaml
import os, shutil, time, json, hashlib, stat, subprocess
from datetime import datetime, timezone
from pathlib import Path

BASE_TEST_DIR  = Path(r"C:\Users\sakindu\Downloads\testing")
QUARANTINE_DIR = BASE_TEST_DIR / "RansomwareQuarantine"




def load_playbooks(playbook_dir: str) -> List[Dict[str, Any]]:
    """Load all YAML playbook files from ``playbook_dir``.

    Each YAML file should contain a top‑level ``playbooks`` list.  If a file
    cannot be parsed or does not contain any playbooks it will be ignored.

    Args:
        playbook_dir: Path to the directory containing playbook YAML files.

    Returns:
        A list of playbook dictionaries.
    """
    pb_list: List[Dict[str, Any]] = []
    try:
        pdir = Path(playbook_dir)
        if not pdir.exists():
            return pb_list
        for yaml_file in pdir.glob("*.yaml"):
            try:
                contents = yaml.safe_load(yaml_file.read_text()) or {}
                pb_entries = contents.get("playbooks") or []
                if isinstance(pb_entries, list):
                    pb_list.extend(pb_entries)
            except Exception as exc:
                logging.warning(f"Failed to load playbook {yaml_file}: {exc}")
    except Exception as exc:
        logging.warning(f"Error while scanning playbooks in {playbook_dir}: {exc}")
    return pb_list


def match_playbooks(playbooks: List[Dict[str, Any]], evt: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the list of playbooks triggered by the given event.

    A playbook may define a ``triggers`` dictionary.  The following fields
    are recognised:

    - ``min_severity``: an integer; the playbook only triggers if the
      event's severity is greater than or equal to this value.
    - ``type``: the event ``type`` string that must match exactly.
    - ``subtype``: the event ``subtype`` string that must match exactly.

    Args:
        playbooks: List of playbook dictionaries.
        evt: The event dictionary produced by the agent.

    Returns:
        A list of playbooks that should be executed for the event.
    """
    triggered: List[Dict[str, Any]] = []
    for pb in playbooks:
        triggers: Dict[str, Any] = pb.get("triggers", {}) or {}
        # minimum severity check
        min_sev = triggers.get("min_severity")
        if min_sev is not None:
            try:
                if evt.get("severity", 0) < int(min_sev):
                    continue
            except Exception:
                continue
        # event type check
        pb_type = triggers.get("type")
        if pb_type and evt.get("type") != pb_type:
            continue
        # subtype check
        pb_subtype = triggers.get("subtype")
        if pb_subtype and evt.get("subtype") != pb_subtype:
            continue
        triggered.append(pb)
    return triggered


def execute_actions(evt: Dict[str, Any], playbooks: List[Dict[str, Any]], notify_callback=None) -> None:
    """Execute the actions defined in the given playbooks for an event.

    For each playbook triggered by the event, iterate through its ``actions``
    list and call the appropriate helper function.  Supported actions are:

    - ``kill_process``: terminate a specific process.  If ``target_pid`` is
      provided in the action definition, that PID will be used; otherwise
      the PID from ``evt['data']['pid']`` will be used.  If no PID is
      available the action does nothing.
    - ``isolate_network``: disable all non‑loopback network interfaces on
      Windows using ``netsh``.  On other platforms this is a no‑op.
    - ``quarantine_file``: move a file to a quarantine folder in the user's
      home directory.  If ``path`` is specified on the action it will be
      used; otherwise ``evt['data']['path']`` will be used.
    - ``notify``: call the provided ``notify_callback`` if one is
      supplied.  This can be used to emit a follow‑up event back to a
      collector or simply log the action.

    Args:
        evt: The event dictionary.
        playbooks: Playbooks that have been triggered for this event.
        notify_callback: Optional callback function to notify after action.
    """
    for pb in playbooks:
        actions = pb.get("actions") or []
        for action in actions:
            if not isinstance(action, dict):
                continue
            act_type = action.get("type")
            if act_type == "kill_process":
                pid = action.get("target_pid") or evt.get("data", {}).get("pid")
                if pid:
                    kill_process(pid)
            elif act_type == "isolate_network":
                isolate_network()
            elif act_type == "quarantine_file":
    # Prefer explicit path, else event.path, else resolve from PID if present
                fpath = action.get("path") or evt.get("data", {}).get("path")
                if not fpath:
                    pid = evt.get("data", {}).get("pid")
                    if pid:
                        try:
                            fpath = psutil.Process(int(pid)).exe()
                        except Exception:
                            fpath = None
                if fpath:
                    quarantine_file(fpath)
            elif act_type == "notify":
                if callable(notify_callback):
                    try:
                        notify_callback(evt, pb.get("name"))
                    except Exception:
                        pass


def kill_process(pid: Any) -> None:
    """Terminate a process by PID using psutil.

    On non‑Windows platforms this still works; however, privileges may be
    required.  Errors are suppressed to avoid destabilising the agent.
    """
    try:
        proc = psutil.Process(int(pid))
        proc.kill()
    except Exception:
        # Swallow all exceptions to avoid crashing the dispatcher
        pass


def isolate_network() -> None:
    """Disable all non‑loopback network interfaces on Windows.

    The agent uses ``netsh`` to disable interfaces by name.  On other
    operating systems the function returns silently.  Any failures are
    intentionally ignored because network isolation is a best‑effort
    operation.
    """
    try:
        if platform.system().lower().startswith("windows"):
            # Gather interface names excluding loopback adapters
            interfaces = [nic for nic in psutil.net_if_addrs().keys() if not nic.lower().startswith("loopback")]
            for nic in interfaces:
                try:
                    # Use netsh to disable the adapter; admin rights are required
                    subprocess.run([
                        "netsh",
                        "interface",
                        "set",
                        "interface",
                        nic,
                        "admin=disabled",
                    ], capture_output=True, check=True)
                except Exception:
                    # Continue attempting to disable other interfaces
                    continue
    except Exception:
        # Do not propagate exceptions; network isolation is best effort
        pass


def quarantine_file(path: str) -> None:
    """
    Safely move a suspicious file into ...\testing\RansomwareQuarantine
    and lock it down (non-executable extension, read-only, restricted ACL).
    Also writes a small manifest.json with metadata.
    """
    try:
        src = Path(path)
        if not src.exists():
            return

        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

        # Hash first (while file is still in original location)
        sha256 = hashlib.sha256()
        try:
            with open(src, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    sha256.update(chunk)
            digest = sha256.hexdigest()
        except Exception:
            digest = None

        # Create a per-item folder (prevents name collisions)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        case_dir = QUARANTINE_DIR / f"{ts}_{(digest or 'nohash')[:8]}"
        case_dir.mkdir(parents=True, exist_ok=True)

        # Rename to a non-executable extension
        dst = case_dir / (src.name + ".quarantined")

        # Move (fast if same volume), else copy+delete
        try:
            src.rename(dst)
        except Exception:
            try:
                shutil.copy2(str(src), str(dst))
                try:
                    os.remove(str(src))
                except Exception:
                    pass
            except Exception:
                return  # give up quietly to keep agent stable

        # Make read-only (best-effort)
        try:
            os.chmod(dst, stat.S_IREAD)
        except Exception:
            pass

        # Lock down ACLs: remove inheritance, grant only Administrators & SYSTEM
        try:
            subprocess.run(["icacls", str(dst), "/inheritance:r"],
                           check=False, capture_output=True)
            subprocess.run(["icacls", str(dst), "/grant:r",
                            "Administrators:F", "SYSTEM:F"],
                           check=False, capture_output=True)
            # Remove broad groups if present
            subprocess.run(["icacls", str(dst), "/remove:g", "Users", "Everyone"],
                           check=False, capture_output=True)
        except Exception:
            pass

        # Write manifest for auditing/restore
        try:
            manifest = {
                "original_path": str(path),
                "quarantined_path": str(dst),
                "size_bytes": dst.stat().st_size if dst.exists() else None,
                "sha256": digest,
                "quarantined_at": ts,
            }
            (case_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    except Exception:
        # Never crash the agent because of quarantine errors
        pass




def default_notify_callback(evt: Dict[str, Any], pb_name: str) -> None:
    """Default notification function.

    This implementation simply logs to stdout that a playbook has executed.
    Agents may override this with a custom callback to publish an event to
    the collector or display a user notification.
    """
    try:
        print(f"[response] Playbook '{pb_name}' executed for event {evt.get('type')}/{evt.get('subtype')} at {evt.get('time')}")
    except Exception:
        pass