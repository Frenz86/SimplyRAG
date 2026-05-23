import requests

EMAIL    = "admin@futura.com"
PASSWORD = "futura1234"
BASE     = "http://localhost"

r = requests.post(f"{BASE}/api/v1/auths/signin", json={"email": EMAIL, "password": PASSWORD})
r.raise_for_status()
headers = {"Authorization": f"Bearer {r.json()['token']}"}

raw = requests.get(f"{BASE}/api/v1/knowledge/", headers=headers)
print("RAW:", raw.text[:300])
resp = raw.json()
collections = resp if isinstance(resp, list) else resp.get("items", [])
print(f"Trovate {len(collections)} collection:\n")
for c in collections:
    print(f"  [{c['id']}] {c['name']}")

print("\nVuoi cancellarle tutte? (s/n): ", end="")
if input().strip().lower() == "s":
    for c in collections:
        r = requests.delete(f"{BASE}/api/v1/knowledge/{c['id']}/delete", headers=headers)
        print(f"  {'Cancellata' if r.ok else 'ERRORE'}: {c['name']}")
    print("Fatto.")
else:
    print("Annullato.")
