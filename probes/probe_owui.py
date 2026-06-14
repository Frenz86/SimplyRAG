"""Probe OpenWebUI — FASE 2 (Link).

1. GET /health (no auth) -> l'app risponde?
2. POST /api/v1/auths/signin con credenziali reali -> token valido?
Stampa la shape GREZZA di entrambe.

Uso:  python probes/probe_owui.py   (richiede lo stack UP)
"""
import os
import sys
import json
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE = os.environ.get("OWUI_BASE", "http://localhost")
EMAIL = os.environ.get("OWUI_EMAIL")
PASSWORD = os.environ.get("OWUI_PASSWORD")
if not (EMAIL and PASSWORD):
    print("SKIP: OWUI_EMAIL/OWUI_PASSWORD mancanti in .env")
    sys.exit(2)

print("=== 1) GET /health ===")
try:
    r = requests.get(f"{BASE}/health", timeout=10)
    print(f"HTTP {r.status_code}: {r.text[:300]}")
except Exception as e:
    print(f"ERRORE: {type(e).__name__}: {e}")

print("\n=== 2) POST /api/v1/auths/signin ===")
r = requests.post(
    f"{BASE}/api/v1/auths/signin",
    json={"email": EMAIL, "password": PASSWORD},
    timeout=10,
)
print(f"HTTP {r.status_code}")
if r.ok:
    d = r.json()
    # maschera il token nella stampa (e' una credenziale)
    tok = d.get("token", "")
    d_masked = {k: ("***" if k == "token" else v) for k, v in d.items()}
    print(json.dumps(d_masked, indent=2, default=str)[:600])
    print(f"\n  token lunghezza: {len(tok)} char  -> {'VALIDO' if tok else 'ASSENTE'}")
else:
    print(r.text[:400])
