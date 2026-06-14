"""Probe llama.cpp — FASE 2 (Link).

Verifica il LLM locale su host.docker.internal:8081 (compose default) o LLAMA_BASE.
Nel compose DEFAULT il servizio non e' definito (solo varianti GPU) -> atteso:
connection refused. Questo conferma la criticita' A2 / ADR-003.

Uso:  python probes/probe_llamacpp.py
"""
import os
import requests

BASE = os.environ.get("LLAMA_BASE", "http://localhost:8081")

for path in ["/health", "/v1/models"]:
    try:
        r = requests.get(BASE + path, timeout=5)
        print(f"GET {path:14s} -> HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"GET {path:14s} -> ERRORE: {type(e).__name__}: {e}")

print("\nNOTA: 'Connection refused' nel compose default e' ATTESO (servizio assente).")
print("      Per il LLM locale: usa una variante GPU, o avvia llama-server sull'host:8081.")
