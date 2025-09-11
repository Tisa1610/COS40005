import json, hmac, hashlib

payload = {
    "type": "test",
    "subtype": "ping",
    "severity": 2,
    "signals": {"score": 10},
    "host": {"id": "agent-1", "name": "Vihanga-Agent"}
}

key = b"dev-change-me"  # match your backend HMAC_KEY
body = dict(payload)
msg = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
signature = hmac.new(key, msg, hashlib.sha256).hexdigest()
print("HMAC:", signature)
