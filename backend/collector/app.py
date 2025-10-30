import os
import json
import hmac
import hashlib
from pathlib import Path
import tempfile
import shutil
import yaml
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

KEY = os.environ.get("RTM_HMAC_KEY", "dev").encode()
app = FastAPI(title="RTM Collector")

# ---------------------------------------------------------------------------
# Configuration API
#
# The agent ships with a YAML configuration file (backend/agent/config.yaml)
# that controls identifiers, watch paths, outbound settings and thresholds.
# We expose:
#   GET  /api/config       -> returns YAML as JSON
#   PUT  /api/config       -> deep-merge JSON into YAML (preserve unknown keys)
#   POST /api/agent/reload -> "touch" config so the agent auto-reloads
#
# Config path can be overridden with AGENT_CONFIG_PATH env var.
DEFAULT_CONFIG_RELATIVE = Path(__file__).resolve().parent.parent / "agent" / "config.yaml"
CFG_PATH = Path(os.getenv("AGENT_CONFIG_PATH", str(DEFAULT_CONFIG_RELATIVE)))


def _load_yaml(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError("config root must be a mapping/object")
        return data
    except FileNotFoundError:
        return {}


def _atomic_write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            yaml.safe_dump(data, tmp, sort_keys=False, allow_unicode=True)
        shutil.move(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass


def _deep_update(original: dict, updates: dict) -> dict:
    """Recursively merge 'updates' into 'original' and return a new dict."""
    result = dict(original)
    for key, val in updates.items():
        if isinstance(val, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_update(result[key], val)
        else:
            result[key] = val
    return result


@app.get("/api/config")
def get_config():
    try:
        cfg = _load_yaml(CFG_PATH)
        return JSONResponse(cfg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {e}")


@app.put("/api/config")
async def put_config(request: Request):
    try:
        updates = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    try:
        cfg = _load_yaml(CFG_PATH)
        new_cfg = _deep_update(cfg, updates)
        _atomic_write_yaml(CFG_PATH, new_cfg)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {e}")


@app.post("/api/agent/reload")
def reload_agent():
    """Touch the config file; the agent watches mtime and restarts itself."""
    try:
        if not CFG_PATH.exists():
            _atomic_write_yaml(CFG_PATH, {})
        CFG_PATH.touch()
        return {"ok": True, "note": "Config timestamp updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to signal reload: {e}")


# ---------------- Existing collector ingest (unchanged) ---------------------
def verify(event: dict):
    sig = event.get("hmac", "")
    body = event.copy()
    body.pop("hmac", None)
    msg = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    good = hmac.compare_digest(sig, hmac.new(KEY, msg, hashlib.sha256).hexdigest())
    if not good:
        raise HTTPException(400, "bad hmac")


@app.post("/ingest")
async def ingest(req: Request):
    event = await req.json()
    verify(event)
    print(json.dumps(event, ensure_ascii=False))
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
