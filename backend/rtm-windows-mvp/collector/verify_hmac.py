import json, hmac, hashlib, os, sys
KEY = os.environ.get("RTM_HMAC_KEY","dev").encode()
evt = json.load(sys.stdin)
sig = evt.get("hmac","")
body = evt.copy(); body.pop("hmac", None)
msg = json.dumps(body, separators=(",",":"), sort_keys=True).encode()
print("valid:", hmac.compare_digest(sig, hmac.new(KEY, msg, hashlib.sha256).hexdigest()))
