import sys, io, json, urllib.request, urllib.parse, urllib.error, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os as _os, re as _re


def _secret(_name):
    _v = _os.environ.get(_name)
    if _v:
        return _v
    try:
        _env = open(_os.path.join(_os.path.dirname(__file__), "..", ".env")).read()
    except OSError:
        return None
    _m = _re.search(rf"^{_name}=(.+)$", _env, _re.M)
    return _m.group(1).strip() if _m else None


SNOV_ID = _secret("SNOV_USER_ID")
SNOV_SEC = _secret("SNOV_USER_SECRET")
if not (SNOV_ID and SNOV_SEC):
    raise SystemExit("Set SNOV_USER_ID and SNOV_USER_SECRET (env var or .env)")
SNOV_API = "https://api.snov.io"

_token = None
_token_time = 0

def get_token():
    global _token, _token_time
    if _token and (time.time() - _token_time) < 3000:
        return _token
    body = urllib.parse.urlencode({"grant_type":"client_credentials","client_id":SNOV_ID,"client_secret":SNOV_SEC}).encode()
    req = urllib.request.Request(f"{SNOV_API}/v1/oauth/access_token", data=body, method="POST", headers={"Content-Type":"application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        _token = json.loads(resp.read())["access_token"]
        _token_time = time.time()
        return _token

def snov_post(path, params, content_type="application/x-www-form-urlencoded"):
    token = get_token()
    if content_type == "application/json":
        data = json.dumps(params).encode()
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{SNOV_API}{path}", data=data, method="POST", headers={"Authorization":f"Bearer {token}","Content-Type":content_type})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", errors="replace")[:300]}
    except Exception as e:
        return {"error": str(e)}

def snov_get(path):
    token = get_token()
    req = urllib.request.Request(f"{SNOV_API}{path}", method="GET", headers={"Authorization":f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code}
    except Exception as e:
        return {"error": str(e)}

# 1. Check Snov.io account balance/credits
print("=== SNOV.IO ACCOUNT INFO ===", flush=True)
token = get_token()
# Never print any part of a live access token. The first 20 characters were being echoed
# to stdout, which lands in terminal scrollback, CI logs and pasted screenshots — and a
# Snov token spends real credits. That it is a prefix is not a mitigation; what is needed
# here is only "did auth work", which does not require the value.
print(f"Token OK ({len(token)} chars, not shown)", flush=True)

# Check credits
resp = snov_get("/v1/get-balance")
print(f"Balance: {json.dumps(resp, indent=2)}", flush=True)

# 2. Test email verifier with one email
print(f"\n=== TEST: Email Verifier ===", flush=True)
test_email = "info@etqaan.sa"
print(f"Verifying: {test_email}", flush=True)
time.sleep(1)
result = snov_post("/v1/email-verifier", {"email": test_email}, content_type="application/json")
print(f"Result: {json.dumps(result, indent=2)}", flush=True)

# 3. Test domain search for a no_domain company
print(f"\n=== TEST: Domain Search (no_domain company) ===", flush=True)
# Try searching by company name - Snov doesn't support this, but let's check
# Actually let's try adding a domain to search
print("Snov.io domain search requires a domain - cannot search by company name alone.", flush=True)
print("For companies with no_domain, we need to find their website first.", flush=True)
