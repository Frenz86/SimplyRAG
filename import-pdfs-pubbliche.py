import os
import re
import subprocess
import requests
import pdfplumber
from pathlib import Path

_SAFE_FILENAME = re.compile(r"^[\w\s\-\.\(\)\[\]àèéìòùÀÈÉÌÒÙ]+$", re.UNICODE)

def _esc(s: str) -> str:
    return s.replace("'", "''")

EMAIL    = os.environ["OWUI_EMAIL"]
PASSWORD = os.environ["OWUI_PASSWORD"]
BASE     = os.environ.get("OWUI_BASE", "http://localhost")

COLLECTIONS = {
                "risorse-umane":         "./pdf/risorse-umane",
                "sicurezza-informatica": "./pdf/sicurezza-informatica",
                "amministrazione":       "./pdf/amministrazione",
                "qualita":               "./pdf/qualita",
                }

def pg(sql):
    r = subprocess.run(
        ["docker", "exec", "postgres", "psql", "-U", "owui", "-d", "openwebui",
         "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True, check=True
    )
    rows = [line.split("\t") for line in r.stdout.strip().splitlines() if line.strip()]
    return rows

def already_in_collection(coll_name, filename):
    if not _SAFE_FILENAME.match(filename):
        raise ValueError(f"Nome file non sicuro: {filename!r}")
    rows = pg(f"""
        SELECT 1 FROM knowledge_file kf
        JOIN file f ON f.id = kf.file_id
        JOIN knowledge k ON k.id = kf.knowledge_id
        WHERE k.name = '{_esc(coll_name)}' AND f.filename = '{_esc(filename)}'
        LIMIT 1
    """)
    return len(rows) > 0

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
        if already_in_collection(coll_name, pdf.name):
            print(f"  SKIP: {pdf.name}")
            continue

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
            continue

        r2 = requests.post(f"{BASE}/api/v1/knowledge/{coll_id}/file/add", headers=headers,
                           json={"file_id": file_id})
        if r2.ok:
            print(f"    OK")
        else:
            print(f"    ERRORE add: {r2.status_code} {r2.text[:200]}")

print("\nFatto!")
