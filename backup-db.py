r"""
Backup del database PostgreSQL (vettori, utenti, collection) in un dump SQL compresso.

Uso:
    python backup-db.py

Output: ./backups/openwebui_<YYYYMMDD_HHMMSS>.sql.gz  (rotazione: ultimi BACKUP_KEEP)

Ripristino (da Git Bash / Linux / macOS):
    gzip -dc backups/openwebui_<TS>.sql.gz | docker exec -i postgres psql -U owui -d openwebui

Ripristino (Windows PowerShell, serve 7-Zip o Git Bash per decomprimere):
    7z x backups\openwebui_<TS>.sql.gz -so | docker exec -i postgres psql -U owui -d openwebui

Nota: usa `docker exec` perche' pg_dump non ha un'alternativa via API. E' uno script
operativo da eseguire sull'host, non logica applicativa.
"""
import os
import gzip
import shutil
import datetime
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CONTAINER  = os.environ.get("POSTGRES_CONTAINER", "postgres")
DB_USER    = os.environ.get("POSTGRES_USER", "owui")
DB_NAME    = os.environ.get("POSTGRES_DB", "openwebui")
BACKUP_DIR = Path("./backups")
KEEP       = int(os.environ.get("BACKUP_KEEP", "7"))

BACKUP_DIR.mkdir(exist_ok=True)
ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
out = BACKUP_DIR / f"openwebui_{ts}.sql.gz"

print(f"Backup di '{DB_NAME}' dal container '{CONTAINER}' -> {out}")
proc = subprocess.Popen(
    ["docker", "exec", CONTAINER, "pg_dump", "-U", DB_USER, "-d", DB_NAME],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
with gzip.open(out, "wb") as f:
    shutil.copyfileobj(proc.stdout, f)
_, err = proc.communicate()

if proc.returncode != 0:
    out.unlink(missing_ok=True)
    raise SystemExit(f"pg_dump fallito (exit {proc.returncode}): {err.decode(errors='replace')[:300]}")

print(f"OK: {out.stat().st_size / 1024 / 1024:.2f} MB")

# Rotazione: mantieni solo gli ultimi KEEP backup
dumps = sorted(BACKUP_DIR.glob("openwebui_*.sql.gz"))
for old in dumps[:-KEEP]:
    old.unlink()
    print(f"Rimosso vecchio backup: {old.name}")
