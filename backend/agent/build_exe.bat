@echo off
py -3.11 -m pip install pyinstaller
py -3.11 -m PyInstaller --onefile --noconsole ^
  --add-data "playbooks;playbooks" ^
  --add-data "response.py;." ^
  agent.py
copy /Y config.yaml dist\
echo Built to .\dist\agent.exe (config.yaml copied)
