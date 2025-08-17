param(
  [string]$ExePath = "$PSScriptRoot\dist\agent.exe",
  [string]$ServiceName = "rtm-agent",
  [string]$HmacKey = ""
)
if (-not (Test-Path $ExePath)) { throw "EXE not found: $ExePath" }
$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($svc) { sc.exe delete $ServiceName | Out-Null; Start-Sleep -s 2 }

sc.exe create $ServiceName binPath= "`"$ExePath`"" start= auto | Out-Null
sc.exe description $ServiceName "Real-Time Monitoring Agent" | Out-Null
if ($HmacKey -ne "") {
  setx RTM_HMAC_KEY $HmacKey /M | Out-Null
}
sc.exe start $ServiceName | Out-Null
Write-Host "Service installed and started."
