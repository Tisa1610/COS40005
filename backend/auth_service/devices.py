from fastapi import APIRouter, Depends, HTTPException, Header
from typing import List, Dict
from datetime import datetime
import random
import jwt, os
from dotenv import load_dotenv

# Load env
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")

# Router
router = APIRouter()

# -------------------------------
# JWT auth dependency
# -------------------------------
def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

# -------------------------------
# Sample devices list
# -------------------------------
devices = [
    {"id": "PLC-01", "name": "Line-1 PLC", "status": "online", "role": "PLC", "last_seen": "2025-10-10T14:00:00Z", "thresholds": {"temp": 70, "pressure": 30}},
    {"id": "HMI-01", "name": "Main HMI", "status": "online", "role": "HMI", "last_seen": "2025-10-10T14:05:00Z", "thresholds": {}},
    {"id": "SCADA-01", "name": "SCADA Server", "status": "online", "role": "Server", "last_seen": "2025-10-10T14:10:00Z", "thresholds": {}},
    {"id": "Sensor-Temp-01", "name": "Temperature Sensor", "status": "online", "role": "Sensor", "last_seen": "2025-10-10T14:12:00Z", "thresholds": {"temp": 75}}
]

# -------------------------------
# Devices endpoint
# -------------------------------
@router.get("/api/devices", response_model=List[Dict])
def list_devices(user=Depends(verify_token)):
    """
    Returns all devices with status, role, thresholds, last_seen
    """
    for device in devices:
        # Randomly simulate offline status
        device["status"] = "offline" if random.random() < 0.1 else "online"
        device["last_seen"] = datetime.utcnow().isoformat()
    return devices
