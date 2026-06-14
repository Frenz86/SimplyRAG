"""Probe Postgres/pgvector — FASE 2 (Link).

Connettività + estensione vector. Usa `docker exec` (come backup-db.py):
zero dipendenze extra, testa il container reale dello stack.

Uso:  python probes/probe_postgres.py   (richiede lo stack UP)
"""
import os
import sys
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

CONT = os.environ.get("POSTGRES_CONTAINER", "postgres")
USER = os.environ.get("POSTGRES_USER", "owui")
DB = os.environ.get("POSTGRES_DB", "openwebui")

# SELECT 1 + versione + presenza ext vector + conta documenti indicizzati.
SQL = (
    "SELECT 1 AS ping;\n"
    "SELECT version();\n"
    "SELECT extname, extversion FROM pg_extension WHERE extname='vector';\n"
    "SELECT count(*) AS n_docs FROM document;  -- tabella documenti OpenWebUI (può non esistere ancora)\n"
)

proc = subprocess.run(
    ["docker", "exec", CONT, "psql", "-U", USER, "-d", DB, "-c", SQL],
    capture_output=True, text=True,
)
print(f"exit: {proc.returncode}")
print(proc.stdout)
if proc.returncode != 0:
    print("STDERR:", proc.stderr.strip()[:500], file=sys.stderr)
    print("\nNOTA: se 'No such container' -> lo stack e' giu. Avvia: docker compose up -d")
