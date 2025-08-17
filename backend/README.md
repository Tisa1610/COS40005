# rtm-windows-mvp

Windows-only MVP for the Real-Time Monitoring part of our OT ransomware platform.

## Components
 - **Agent (Windows service)**: watches file churn, process starts, Sysmon + PowerShell logs and can automatically respond to threats using SOAR playbooks.
- **Secure transport**: MQTT/TLS (default) or HTTPS to collector.
- **Collector (optional)**: FastAPI endpoint that verifies HMAC and prints/stores events.

## Quick start (dev)

1) Run the agent on Windows:

```bat
cd agent
py -3.11 -m pip install -r requirements.txt
set RTM_HMAC_KEY=CHANGE_ME_TO_A_LONG_RANDOM
py -3.11 agent.py
```

2) (Optional) Run the collector:

```bat
cd collector
py -3.11 -m pip install -r requirements.txt
set RTM_HMAC_KEY=CHANGE_ME_TO_A_LONG_RANDOM
py -3.11 app.py
```

3) Generate noise to test:
```bat
for /l %i in (1,1,250) do @echo X>%USERPROFILE%\Desktop\test%i.txt
start powershell -NoLogo -Command "Write-Output 'hello'"
```

## Install as a service (prod-lite)

- Create an EXE:
```bat
cd agent
build_exe.bat
```

- Install with the PowerShell script:
```ps1
.\install_service.ps1 -ExePath "C:\rtm-windows-mvp\agent\dist\agent.exe" -HmacKey "YOUR_LONG_RANDOM"
```

## Switch transport
- MQTT (default): configure broker CA/user in `agent\config.yaml` and drop CA at `deploy\tls\ca.crt`.
- HTTPS: set `outbound.mode: https` and point to your collector URL (TLS).

## What it detects (out-of-box)
- Mass **file writes** per second (burst threshold).
- **Process starts** for script/LOLBINs (powershell, wscript, cscript, cmd, mshta).
- **Sysmon** file/registry/process events.
- **PowerShell ScriptBlock** logs (Event ID 4104).
- **Service installs / VSS delete** indicators in event text.

Tune thresholds in `agent\config.yaml`.

## Automated response and SOAR

The MVP now includes a simple **Security Orchestration, Automation and Response (SOAR)**
layer.  Playbooks live under the `playbooks/` directory next to
`agent.py` and are loaded at runtime.  A playbook consists of a set of
trigger conditions (for example, minimum severity or specific event types)
and a list of actions.  Supported actions include:

* `kill_process` – terminate a suspicious process by PID.
* `isolate_network` – disable all non‑loopback network interfaces on
  Windows via `netsh` to prevent lateral movement.  Requires
  administrative privileges and has no effect on other platforms.
* `quarantine_file` – move a file to a quarantine folder in the current
  user's home directory.
* `notify` – invoke a notification callback.  By default this prints to
  stdout but can be customised to publish a follow‑up event back to the
  collector.

The default playbooks are defined in `playbooks/default.yaml`.  You can
create additional YAML files in the `playbooks/` directory to customise
behaviour.  Each file should contain a top‑level `playbooks:` list.
Playbooks will be evaluated in the order they are loaded.  See
`response.py` for implementation details.

## Extending the platform

This repository contains placeholder directories for future modules:

* **`ai/`** – reserved for machine‑learning–based detection and predictive
  analytics.  Components placed here should implement hybrid detection,
  sandbox analysis and continuous learning.
* **`backup/`** – reserved for secure backup and immutable storage.
  Modules placed here should handle snapshotting, vaulting and
  high‑speed recovery.  A separate team will populate these
  components.

When building the agent executable with `build_exe.bat`, the
`config.yaml`, `playbooks/` directory and `response.py` are bundled
alongside the binary so that custom configurations and playbooks are
available at runtime.
