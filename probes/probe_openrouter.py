"""Probe OpenRouter — FASE 2 (Link).

Valida la chiave reale e stampa la shape GREZZA:
  1. GET /api/v1/key  -> valida la chiave + saldo credito (interessa il budget)
  2. GET /api/v1/models -> conferma che i modelli dichiarati nel compose esistono

Nessun costo: entrambe le chiamate sono read-only e non consumano credito.

Uso:  python probes/probe_openrouter.py
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

KEY = os.environ.get("OPENROUTER_API_KEY")
if not KEY:
    print("SKIP: OPENROUTER_API_KEY mancante in .env")
    sys.exit(2)

BASE = "https://openrouter.ai/api/v1"
H = {"Authorization": f"Bearer {KEY}"}

# Dichiarati in docker-compose.yml (OPENAI_MODELS / MODEL_FILTER_LIST).
WANT = ["google/gemini-2.5-flash", "google/gemini-2.5-flash-lite"]

print("=== 1) GET /key (valida chiave + credito) ===")
r = requests.get(f"{BASE}/key", headers=H, timeout=20)
print(f"HTTP {r.status_code}")
if r.ok:
    d = r.json().get("data", {})
    print(f"  label      : {d.get('label')}")
    print(f"  usage      : {d.get('usage')}")
    print(f"  limit      : {d.get('limit')}")
    print(f"  limit_by   : {d.get('limit_by')}")
    print(f"  free_credits: {d.get('free_credit') or d.get('free_credit_granted')}")
    print(f"  is_free_tier: {d.get('is_free_tier')}")
else:
    print(r.text[:400])

print("\n=== 2) GET /models (verifica modelli dichiarati) ===")
r = requests.get(f"{BASE}/models", headers=H, timeout=20)
print(f"HTTP {r.status_code}")
if r.ok:
    ids = [m["id"] for m in r.json().get("data", [])]
    print(f"  modelli totali: {len(ids)}")
    for w in WANT:
        print(f"  {'OK    ' if w in ids else 'MANCA '} {w}")
else:
    print(r.text[:400])
