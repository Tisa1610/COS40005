@echo off
set RTM_HMAC_KEY=CHANGE_ME_TO_A_LONG_RANDOM
py -3.11 -m pip install -r requirements.txt
py -3.11 app.py
