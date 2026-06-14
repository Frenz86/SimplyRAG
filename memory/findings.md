# Findings

Ricerca, scoperte, vincoli. Shape **reale** delle risposte dei servizi esterni.

## Audit iniziale (FASE 1 — 2026-06-14)

### Stack rilevato (come è, non come dice la doc)
- **Reverse proxy:** Caddy custom (plugin rate-limit) su **HTTP :80 only** — NO HTTPS.
- **App:** OpenWebUI `0.9.6`, embedding `multilingual-e5-base` locale (pre-scaricato da `model-init`).
- **DB:** Postgres `pgvector/pgvector:pg16`, estensione `vector` via `init/01-vector.sql`.
- **LLM:** ibrido — locale (llama.cpp `host.docker.internal:8081`) + OpenRouter (`gemini-2.5-flash`, `-flash-lite`).
- **GPU varianti:** `docker-compose-gpu-{MINI4PRO,rtx5060,gtx1060}.yml` aggiungono servizio `llama-cpp`.
- **pgadmin:** commentato nel compose default (disabilitato).

### Criticità — Sicurezza
- `.env.example` contiene un **valore concreto** di `WEBUI_SECRET_KEY` (chiave firma JWT). Copiato senza cambio → riuso/forzatura sessioni. Deve essere placeholder.
- Caddy su HTTP puro → credenziali OWUI in chiaro. README dichiara falsamente HTTPS + cert self-signed.
- `BYPASS_MODEL_ACCESS_CONTROL: "True"` → ogni utente loggato usa ogni modello (anche i costosi su OpenRouter). OK single-admin, rischio multi-user.
- Chiave OpenRouter server-side, nessuna quota per-user.

### Criticità — Bug/coerenza (rompono il sistema oggi)
- `utils/filter-models.py` KEEP = `gemini-3.5-flash` / `gemini-3.1-flash-lite` (modelli inesistenti). Esecuzione → **nessun** modello attivo → RAG rotto. Endpoint usati deprecati in OWUI 0.9.6. Sostituire con `ENABLE_MODEL_FILTER` (già nel compose).
- Drift locust: `locustfile.py` default `gemini-3.1-flash-lite` vs `docker-compose.locust.yml` default `gemini-2.5-flash-lite`.
- `docker-compose.yml` default referencia LLM locale (`Qwen3.6-35B...gguf` su `host.docker.internal:8081`) ma **nessun** servizio `llama-cpp` in questo compose (solo varianti GPU). `Dockerfile.llamacpp` orphan + fork `PrismML-Eng/llama.cpp` di esistenza dubbia.
- README stale (import singolo, pgadmin on, HTTPS). `instructions.txt` richiede `OWUI_*` ma in `.env.example` sono commentate → KeyError su setup pulito.
- `import-pdfs-pubbliche.py` / `-private.py` = 95% duplicati (da diventare 1 tool parametrico).

### Criticità — Processo vs PROTOCOL
- CLAUDE.md = solo TODO (schema, invarianti, contratti, DoD, registro errori vuoti).
- Nessun probe in `probes/` (FASE 2 mai fatta).
- Nessuna SOP; nessun tool atomico in `tools/`; **zero test** (Self-Annealing impossibile).
- `backup-db.py` non schedulato; restore mai testato.
- `model-init` scarica embedding senza hash/checksum (supply-chain).

## Vincoli
- Single-admin su LAN (ipotesi da confermare nelle 5 domande).
- Hardware target multi-filo: GTX1060 6GB / RTX5060-ti 16GB / Mac MINI4 PRO.

## Servizi esterni (shape reale)
### OpenWebUI REST (`/api/v1/*`)
- Endpoint signin: `POST /api/v1/auths/signin` → `{"token": "..."}`
- KB list: `GET /api/v1/knowledge/` → lista o `{"items": [...]}`
- File upload + process + add: `POST /files/`, `POST /retrieval/process/file`, `POST /knowledge/{id}/file/add`
- Quirk: dedup nativa → 400 `"Duplicate content"` sul file/add.
### OpenRouter ✅ VERIFICATO (2026-06-14, probe_openrouter.py)
- Base: `https://openrouter.ai/api/v1` (compatibile OpenAI `/models`, `/chat/completions`).
- Auth: Bearer `OPENROUTER_API_KEY` — chiave valida, account a pagamento (`is_free_tier: False`).
- `GET /key` → `{data:{label, usage, limit, limit_by, is_free_tier}}`. **usage=$6.21**, **limit=None (NO hard cap)** → rischio spesa: fissare un cap sulla chiave o alert.
- `GET /models` → 337 modelli. Confermati presenti: `google/gemini-2.5-flash`, `google/gemini-2.5-flash-lite`.
### Postgres ✅ VERIFICATO (2026-06-14, ri-verifica post-fix, probe_postgres.py)
- `pgvector/pgvector:pg16` → PostgreSQL 16.14 (Debian).
- ext `vector 0.8.2` attiva. `SELECT 1` OK.
- Tabella `document_chunk(id text PK, vector vector(768), collection_name text, text, vmetadata jsonb)` + indici (ivfflat su vector). **`n_docs=0`** (KB vuota: slate pulito).
- *(Correzione: la versione precedente di questo file diceva `vector(1536)` — valore pre-fix. Ora la colonna è `vector(768)`, allineata a e5-base.)*

### OpenWebUI ✅ VERIFICATO (2026-06-14, ri-verifica post-fix, probe_owui.py)
- `GET /health` → `200 {"status":true}`.
- `POST /api/v1/auths/signin` → `200`, ritorna `{id,name,role,email,token(Bearer),token_type,expires_at,permissions{...}}`.
- Admin: `admin@futura.com` (id `5a65bedd...`), role=admin, **token 247 char**.

### ✅ Embeddings — ALLINEATO + STABILE (2026-06-14, ri-verifica post-fix, probe_embeddings.py)
- Modello caricato OK: `multilingual-e5-base` locale, **768 dim** (`model.safetensors` 1.1 GB fp32 sul volume `embedding_model`, pre-scaricato da `model-init`).
- `POST /api/v1/embeddings` (engine in-process, `RAG_EMBEDDING_ENGINE=""`) → **HTTP 500**: endpoint non esposto per engine vuoto. Il canale si verifica a livello storage (INSERT), non HTTP.
- **Allineamento a 3 fronti:** colonna `document_chunk.vector = vector(768)` = modello 768 = env `PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH=768`. Test deterministico (INSERT 768-dim in transazione, ROLLBACK): `INSERT 0 1` → **passa**. n_chunks=0.
- **Quirk critico OWUI 0.9.6 (causa del crash-loop odierno):** `VECTOR_LENGTH` **non è dedotto dal modello** — è letto da `PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH` (`config.py:778`, default `1536`). Se l'env non è impostato → `check_vector_length` (`pgvector.py:265`) solleva "VECTOR_LENGTH 1536 does not match existing vector column dimension 768" a tempo di import → uvicorn non parte → open-webui mai healthy → Caddy 502 / `ConnectionError` su signin. Bug latente: la "verifica" precedente passava perché la colonna era 768 E l'env risultava inavvertitamente coerente al momento del test, ma al riavvio lo stack crashava.
- **Fix STABILE applicato:** env `PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH: "768"` nel compose (docker-compose.yml). ivfflat da REINDEX dopo il primo import reale (NOTICE "low recall" su tabella vuota). Regole permanenti in `CLAUDE.md` §6 (2 voci).

### llama.cpp — ASSENTE nel compose default (2026-06-14, probe_llamacpp.py)
- `GET host.docker.internal:8081/{health,v1/models}` → Connection refused. ATTESO (servizio non definito nel compose default, solo varianti GPU). Conferma criticità A2 / ADR-003.
