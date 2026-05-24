import requests
from pathlib import Path

DIR = Path(__file__).parent

EMAIL    = "admin@futura.com"
PASSWORD = "futura1234"
BASE     = "http://localhost"

token = requests.post(f"{BASE}/api/v1/auths/signin", json={"email": EMAIL, "password": PASSWORD}).json()["token"]
headers = {"Authorization": f"Bearer {token}"}

KEEP = {
    "google/gemini-2.5-flash-lite",
    "google/gemini-2.5-flash",
}

# Prendi tutti i modelli disponibili da Open WebUI
all_models = requests.get(f"{BASE}/api/models", headers=headers).json().get("data", [])
print(f"Modelli totali: {len(all_models)}")

ok = err = 0
for m in all_models:
    model_id = m["id"]
    is_active = model_id in KEEP

    payload = {
        "id": model_id,
        "name": m["name"],
        "is_active": is_active,
        "meta": {"description": m.get("description", "")},
        "params": {},
        "access_grants": [],
    }

    # prova create, se esiste già usa update
    r = requests.post(f"{BASE}/api/v1/models/create", headers=headers, json=payload)
    if not r.ok:
        r = requests.post(f"{BASE}/api/v1/models/model/update", headers=headers, json=payload)

    if r.ok:
        status = "ON " if is_active else "off"
        if is_active:
            print(f"  [{status}] {m['name']}")
        ok += 1
    else:
        if err < 3:
            print(f"  ERR {r.status_code}: {r.text[:120]} | id={model_id}")
        err += 1

print(f"\nFatto: {ok} OK, {err} errori")
