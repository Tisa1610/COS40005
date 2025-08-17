@echo off
py -3.11 -m pip install pyinstaller
py -3.11 -m PyInstaller --onefile --noconsole ^
  --add-data "config.yaml;." ^
  --add-data "playbooks;playbooks" ^
  --add-data "response.py;." ^
  agent.py
echo Built to .\dist\agent.exe
