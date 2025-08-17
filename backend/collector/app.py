import os, json, hmac, hashlib
from fastapi import FastAPI, Request, HTTPException

KEY = os.environ.get("RTM_HMAC_KEY","dev").encode()
app = FastAPI(title="RTM Collector")

def verify(event: dict):
    sig = event.get("hmac","")
    body = event.copy(); body.pop("hmac", None)
    msg = json.dumps(body, separators=(",",":"), sort_keys=True).encode()
    good = hmac.compare_digest(sig, hmac.new(KEY, msg, hashlib.sha256).hexdigest())
    if not good: raise HTTPException(400, "bad hmac")

@app.post("/ingest")
async def ingest(req: Request):
    event = await req.json()
    verify(event)
    print(json.dumps(event, ensure_ascii=False))
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
