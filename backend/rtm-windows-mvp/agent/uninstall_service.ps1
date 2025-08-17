param([string]$ServiceName = "rtm-agent")
sc.exe stop $ServiceName | Out-Null
Start-Sleep -s 2
sc.exe delete $ServiceName | Out-Null
Write-Host "Service removed."
