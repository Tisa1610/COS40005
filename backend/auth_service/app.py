from fastapi import FastAPI, HTTPException, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import psutil
import json
import os
from pathlib import Path

# ==================================================
# CONFIGURATION (using environment variables)
# ==================================================
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", 1440))

# Store auth data safely
AUTH_DATA_DIR = Path("backend/auth_data")
AUTH_DATA_DIR.mkdir(parents=True, exist_ok=True)

USERS_FILE = AUTH_DATA_DIR / "users.json"
REFRESH_TOKEN_FILE = AUTH_DATA_DIR / "refresh_tokens.json"

# ==================================================
# PASSWORD HASHING
# ==================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==================================================
# FASTAPI APP INIT
# ==================================================
app = FastAPI()

# Restrict CORS for local + deployed URL only
origins = [
    "http://localhost:3000",
    "https://your-deployed-url.com"  # replace later with real frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ==================================================
# SCHEMAS
# ==================================================
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class LoginForm(BaseModel):
    username: str
    password: str

class RefreshTokenForm(BaseModel):
    refresh_token: str

# ==================================================
# UTILITY FUNCTIONS
# ==================================================
def load_json_file(file_path: Path) -> Dict:
    if file_path.exists():
        with open(file_path, "r") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
    return {}

def save_json_file(file_path: Path, data: Dict):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    tokens = load_json_file(REFRESH_TOKEN_FILE)
    tokens[token] = {"user": data["sub"], "exp": expire.isoformat()}
    save_json_file(REFRESH_TOKEN_FILE, tokens)
    return token

def cleanup_expired_refresh_tokens():
    tokens = load_json_file(REFRESH_TOKEN_FILE)
    now = datetime.utcnow()
    valid_tokens = {k: v for k, v in tokens.items() if datetime.fromisoformat(v["exp"]) > now}
    if len(valid_tokens) != len(tokens):
        save_json_file(REFRESH_TOKEN_FILE, valid_tokens)

def verify_token(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if not username or not role:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def verify_admin(user: dict = Depends(verify_token)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# ==================================================
# AUTH ENDPOINTS
# ==================================================

# Login: supports both JSON and form-data (for UI or curl)
@app.post("/auth/login", response_model=Token)
def login(
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    form_data: Optional[OAuth2PasswordRequestForm] = Depends(None),
    json_data: Optional[LoginForm] = None,
):
    users = load_json_file(USERS_FILE)

    # Support both form and JSON
    user_input = {
        "username": username or (form_data.username if form_data else None) or (json_data.username if json_data else None),
        "password": password or (form_data.password if form_data else None) or (json_data.password if json_data else None),
    }

    if not user_input["username"] or not user_input["password"]:
        raise HTTPException(status_code=400, detail="Username and password required")

    user = users.get(user_input["username"])
    if not user or not verify_password(user_input["password"], user.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": user["username"], "role": user["role"]})
    refresh_token = create_refresh_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@app.post("/auth/refresh", response_model=Token)
def refresh_token(form_data: RefreshTokenForm):
    cleanup_expired_refresh_tokens()
    tokens = load_json_file(REFRESH_TOKEN_FILE)
    if form_data.refresh_token not in tokens:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    try:
        payload = jwt.decode(form_data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username or not role:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        # Rotate token: issue new and revoke old
        del tokens[form_data.refresh_token]
        save_json_file(REFRESH_TOKEN_FILE, tokens)

        access_token = create_access_token({"sub": username, "role": role})
        new_refresh_token = create_refresh_token({"sub": username, "role": role})

        return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@app.post("/auth/logout")
def logout(user: dict = Depends(verify_token)):
    tokens = load_json_file(REFRESH_TOKEN_FILE)
    tokens = {k: v for k, v in tokens.items() if v["user"] != user["username"]}
    save_json_file(REFRESH_TOKEN_FILE, tokens)
    return {"detail": f"User {user['username']} logged out successfully"}

# ==================================================
# SYSTEM ENDPOINTS
# ==================================================
@app.get("/health")
def health_check():
    return {"status": "ok", "time": datetime.utcnow()}

@app.get("/metrics")
def get_metrics(user: dict = Depends(verify_token)):
    cpu_usage = psutil.cpu_percent()
    ram_usage = psutil.virtual_memory().percent
    temperature = 0
    packet_count = 100
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for entries in temps.values():
                if entries:
                    temperature = entries[0].current
                    break
    except Exception:
        pass
    return {"cpu_usage": cpu_usage, "ram_usage": ram_usage, "temperature": temperature, "packet_count": packet_count}

@app.get("/alerts")
def get_alerts(user: dict = Depends(verify_token)):
    return {"alerts": ["Alert1", "Alert2"]}

@app.get("/rtm")
def get_rtm(user: dict = Depends(verify_admin)):
    return {"status": "RTM agent data (admin only)"}

@app.get("/soar")
def get_soar(user: dict = Depends(verify_admin)):
    return {"status": "SOAR data (admin only)"}

@app.get("/config")
def get_config(user: dict = Depends(verify_admin)):
    return {"config": "Current system config (admin only)"}

@app.get("/backups")
def get_backups(user: dict = Depends(verify_admin)):
    return {"backups": ["backup1.zip", "backup2.zip"]}

# ==================================================
# INIT DEFAULT USERS (admin-provisioned only)
# ==================================================
def init_users():
    users = load_json_file(USERS_FILE)
    fixed = False

    if "admin" not in users:
        users["admin"] = {"username": "admin", "password": hash_password("Password123!"), "role": "admin"}
        fixed = True

    if "user" not in users:
        users["user"] = {"username": "user", "password": hash_password("Password123!"), "role": "user"}
        fixed = True

    if fixed:
        save_json_file(USERS_FILE, users)

init_users()
cleanup_expired_refresh_tokens()

# ==================================================
# RUN SERVER
# ==================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8010, log_level="info")
