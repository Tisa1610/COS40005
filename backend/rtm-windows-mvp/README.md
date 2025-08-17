# rtm-windows-mvp

Windows-only MVP for the Real-Time Monitoring part of our OT ransomware platform.

## Components
- **Agent (Windows service)**: watches file churn, process starts, Sysmon + PowerShell logs.
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
