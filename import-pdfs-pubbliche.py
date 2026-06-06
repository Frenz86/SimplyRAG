import os
import requests
import pdfplumber
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

EMAIL    = os.environ["OWUI_EMAIL"]
PASSWORD = os.environ["OWUI_PASSWORD"]
BASE     = os.environ.get("OWUI_BASE", "http://localhost")

COLLECTIONS = {
                "risorse-umane":         "./pdf/risorse-umane",
                "sicurezza-informatica": "./pdf/sicurezza-informatica",
                "amministrazione":       "./pdf/amministrazione",
                "qualita":               "./pdf/qualita",
                }

r = requests.post(f"{BASE}/api/v1/auths/signin", json={"email": EMAIL, "password": PASSWORD})
r.raise_for_status()
headers = {"Authorization": f"Bearer {r.json()['token']}"}
print("Login OK")

resp = requests.get(f"{BASE}/api/v1/knowledge/", headers=headers).json()
all_collections = resp if isinstance(resp, list) else resp.get("items", [])

for coll_name, folder in COLLECTIONS.items():
    pdfs = list(Path(folder).glob("*.pdf"))
    if not pdfs:
        print(f"[{coll_name}] Nessun PDF trovato, salto.")
        continue

    match = next((c for c in all_collections if c["name"] == coll_name), None)
    if match:
        coll_id = match["id"]
        print(f"\n[{coll_name}] Collection riusata: {coll_id}")
    else:
        r = requests.post(f"{BASE}/api/v1/knowledge/create", headers=headers,
                          json={"name": coll_name, "description": ""})
        r.raise_for_status()
        coll_id = r.json()["id"]
        all_collections.append({"name": coll_name, "id": coll_id})
        print(f"\n[{coll_name}] Collection creata: {coll_id}")

    requests.post(f"{BASE}/api/v1/knowledge/{coll_id}/access/update", headers=headers,
                  json={"access_grants": [{"principal_type": "user", "principal_id": "*", "permission": "read"}]})

    for pdf in pdfs:
        print(f"  Upload: {pdf.name}")
        with open(pdf, "rb") as f:
            r = requests.post(f"{BASE}/api/v1/files/", headers=headers,
                              files={"file": (pdf.name, f, "application/pdf")})
        r.raise_for_status()
        file_id = r.json()["id"]

        with pdfplumber.open(pdf) as doc:
            text = "\n".join(page.extract_text() or "" for page in doc.pages)
        print(f"    {len(text)} caratteri")

        rp = requests.post(f"{BASE}/api/v1/retrieval/process/file", headers=headers,
                           json={"file_id": file_id, "content": text})
        if not rp.ok:
            print(f"    ERRORE process: {rp.status_code} {rp.text[:200]}")
            requests.delete(f"{BASE}/api/v1/files/{file_id}", headers=headers)
            continue

        r2 = requests.post(f"{BASE}/api/v1/knowledge/{coll_id}/file/add", headers=headers,
                           json={"file_id": file_id})
        # Dedup nativo OpenWebUI: stesso contenuto gia presente -> SKIP, rimuovo il file caricato.
        if r2.ok:
            print(f"    OK")
        elif r2.status_code == 400 and "Duplicate content" in r2.text:
            print(f"    SKIP (contenuto gia presente)")
            requests.delete(f"{BASE}/api/v1/files/{file_id}", headers=headers)
        else:
            print(f"    ERRORE add: {r2.status_code} {r2.text[:200]}")
            requests.delete(f"{BASE}/api/v1/files/{file_id}", headers=headers)

print("\nFatto!")
