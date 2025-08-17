@echo off
py -3.11 -m pip install pyinstaller
py -3.11 -m PyInstaller --onefile --noconsole agent.py
echo Built to .\dist\agent.exe
