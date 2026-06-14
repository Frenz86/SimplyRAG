"""Probe Embeddings — FASE 2 (Link) + test di regressione dimensionale.

Verifica l'allineamento: embedding-modello (e5-base = 768) <-> colonna pgvector.
L'endpoint OpenAI-compat /api/v1/embeddings restituisce HTTP 500 con engine
in-process (RAG_EMBEDDING_ENGINE vuoto), quindi il canale si verifica a livello
storage: il modello caricato deve corrispondere a document_chunk.vector(N).

Test deterministico (zero persistenza, in transazione con ROLLBACK):
  tenta INSERT di un vettore EMBED_DIM-dim -> se pgvector rifiuta, mismatch = rotto.

Self-Annealing: se cambi modello (es. e5-large 1024), imposta EMBED_DIM e ri-esegui:
il probe segnala subito se la colonna non e' allineata.

Uso:  EMBED_DIM=768 python probes/probe_embeddings.py   (richiede stack UP)
"""
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

EMBED_DIM = int(os.environ.get("EMBED_DIM", "768"))  # multilingual-e5-base = 768
CONT = os.environ.get("POSTGRES_CONTAINER", "postgres")
USER = os.environ.get("POSTGRES_USER", "owui")
DB = os.environ.get("POSTGRES_DB", "openwebui")


def psql(sql: str) -> tuple[int, str]:
    p = subprocess.run(
        ["docker", "exec", CONT, "psql", "-U", USER, "-d", DB, "-tAc", sql],
        capture_output=True, text=True,
    )
    return p.returncode, (p.stdout.strip() or p.stderr.strip())


# 1) dimensione colonna corrente
rc, col = psql(
    "SELECT format_type(atttypid,atttypmod) FROM pg_attribute a "
    "JOIN pg_class c ON a.attrelid=c.oid "
    "JOIN pg_namespace n ON c.relnamespace=n.oid "
    "WHERE n.nspname='public' AND c.relname='document_chunk' AND attname='vector';"
)
print(f"Colonna document_chunk.vector : {col}")
print(f"Modello embedding (e5-base)   : vector({EMBED_DIM})")

# 2) test INSERT in transazione (ROLLBACK -> nessuna persistenza)
lit = "[" + ",".join(str(i) for i in range(1, EMBED_DIM + 1)) + "]"
test_sql = (
    f"BEGIN; "
    f"INSERT INTO document_chunk (id, collection_name, vector) "
    f"VALUES ('__dimtest__', '__test__', '{lit}'::vector); "
    f"ROLLBACK;"
)
rc, out = psql(test_sql)
print(f"\nINSERT vettore {EMBED_DIM}-dim -> exit {rc}")
print(f"  {out}")

if rc == 0:
    print("\nESITO: ALLINEATO - embedding inseribile. Canale OK.")
else:
    print("\nESITO: MISMATCH - pgvector rifiuta l'insert. Embedding ROTTO.")
    print("  Fix (tabella vuota, sicuro):")
    print("    DROP INDEX IF EXISTS idx_document_chunk_vector;")
    print(f"    ALTER TABLE document_chunk ALTER COLUMN vector TYPE vector({EMBED_DIM});")
    print("    CREATE INDEX idx_document_chunk_vector ON document_chunk "
          "USING ivfflat (vector vector_cosine_ops) WITH (lists='100');")
