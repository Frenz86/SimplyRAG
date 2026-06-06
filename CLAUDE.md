# CLAUDE.md — Regole globali

## Principi di codice — DRY · KISS · SOLID

- **DRY**: nessuna duplicazione di logica o costanti. Se qualcosa si ripete, va estratto in un'astrazione condivisa e importato.
- **KISS**: la soluzione più semplice che soddisfa i requisiti è sempre preferibile. Eliminare complessità non necessaria.
- **SOLID**:
  - Single Responsibility: ogni modulo/funzione ha una sola ragione di cambiare.
  - Open/Closed: aperto all'estensione, chiuso alla modifica diretta.
  - Dependency Inversion: dipendi dalle astrazioni, non dalle implementazioni concrete.
- Non aggiungere astrazioni premature. Tre righe simili sono meglio di un'astrazione inutile.
- Non aggiungere error handling per casi impossibili. Validare solo ai boundary del sistema (input utente, API esterne).
- Commenti solo sul **perché**, mai sul **cosa**. Il codice ben scritto si spiega da solo.
- Non lasciare debito tecnico silenzioso: segnalarlo sempre come nota separata, senza ignorarlo né applicarlo senza avvisare.

---

## Sicurezza & Privacy (GDPR)

- **Input validation** a ogni layer: frontend, API, DB. Mai fidarsi dell'input esterno.
- **Secrets mai hardcodati**: usare variabili d'ambiente. In produzione, secret manager.
- **Nessun dato personale nei log**: email, IP, nomi vanno mascherati o esclusi.
- **SQL injection**: query parametrizzate o ORM sempre. Mai interpolazione di stringhe.
- **Principio del minimo privilegio**: ruoli, permessi DB e accessi cloud al minimo indispensabile.
- **Rate limiting** su tutti gli endpoint esposti, non solo quelli di autenticazione.
- **Minimizzazione dei dati**: raccogliere e conservare solo ciò che è strettamente necessario.
- **Diritto all'oblio**: la cancellazione deve essere implementabile (DELETE cascade o soft delete con retention policy documentata).
- **Autenticazione**: JWT con refresh token rotation, o session-based con CSRF protection.
- **Headers HTTP di sicurezza**: CSP, HSTS, X-Frame-Options, X-Content-Type-Options.
- **Nuove dipendenze**: prima di aggiungere qualsiasi libreria (frontend o backend), verificare che non abbia vulnerabilità note (CVE) e che sia attivamente mantenuta. Segnalare eventuali rischi prima di procedere.
- Segnalare ogni implicazione di sicurezza o privacy con prefisso `🔒` o `🛡️` prima di procedere.

---

## Best practice generali

- **Anno corrente**: usarlo nelle ricerche di best practice (es. `"FastAPI best practices 2026"`) per evitare pattern obsoleti o API deprecate.
- **Error handling, typing e validazione** sempre inclusi nel codice prodotto — mai codice di esempio incompleto.
- **Multi-stage Dockerfile**: stage build separato dallo stage production.
- **Ambienti separati**: file `.env` distinti per development, staging e production.
- **Health check endpoint** sempre presente nelle applicazioni deployate.
- **Rollback strategy** sempre considerata prima di un deploy o di una migrazione DB.
- Prima di modificare un progetto esistente, analizzare i pattern architetturali già adottati e rispettarli. Non introdurre pattern diversi senza discuterlo prima.

---

## Architettura SimplyRAG

SimplyRAG è una soluzione **RAG documentale containerizzata**, progettata per uso aziendale locale (on-premise), con supporto a modelli LLM sia locali che remoti.

### Stack tecnologico

| Layer | Tecnologia | Note |
|-------|-----------|------|
| Frontend + API RAG | **Open WebUI** v0.9.6 | Porta 8080 interna, esposta via Caddy |
| Vector DB | **PostgreSQL 16 + pgvector** | Porta 5432, volume persistente `pgdata` |
| DB Admin | **pgAdmin** v8.14 | Accessibile via `/pgadmin` |
| Reverse proxy | **Caddy** | Porta 80, security headers (CSP) e routing |
| Embedding | **intfloat/multilingual-e5-base** | Pre-scaricato dal servizio `model-init` in `/models/e5-base` (~1.1GB, solo safetensors) |
| LLM remoto | **Gemini 2.5 Flash** via OpenRouter | API key in `.env` |
| LLM locale | **llama.cpp** (GGUF, opzionale) | Porta 8081 host, accessibile via `host.docker.internal` |

### Pipeline RAG

```
PDF in ./pdf/<collection>/
  → upload via OpenWebUI API (/api/v1/files/)
  → chunking token-based (size=1500, overlap=200)
  → embedding locale (multilingual-e5-base)
  → vettori in pgvector
  → query utente → BM25 + ricerca vettoriale (ibrida)
  → top-10 risultati, soglia rilevanza 0.3
  → context + prompt template → LLM
  → risposta basata SOLO sui documenti
```

### Gestione del modello embedding (servizio `model-init`)

Il modello embedding **non** viene scaricato da open-webui a runtime (lo fa in modo inefficiente: tira l'intero repo ~5GB con tutti i formati — pytorch.bin, ONNX, OpenVINO — e li **riscarica** se cancellati). Invece:

- Il servizio **`model-init`** (esegue una volta sola, `restart: "no"`) pre-scarica **solo** `model.safetensors` + tokenizer + config (~1.1GB) nel volume `embedding_model`, con `HF_HUB_DISABLE_XET=true`.
- open-webui monta quel volume in `/models/e5-base:ro` e usa `RAG_EMBEDDING_MODEL: "/models/e5-base"` → SentenceTransformers carica da **path locale**, senza alcun download a runtime.
- `depends_on: model-init: service_completed_successfully` garantisce che il modello sia pronto prima dell'avvio.
- Idempotente: se `model.safetensors` è già presente, `model-init` salta il download.

🔒 **Vincolo Docker Desktop**: il backend **Xet** di HuggingFace **stalla** su Docker Desktop (file `.incomplete` fermi a 0 byte). Tutti i download HF nel progetto usano `HF_HUB_DISABLE_XET=true`. Inoltre Docker Desktop deve avere **≥4GB RAM** (Settings → Resources): con meno, il caricamento del modello va in OOM (exit 137).

⚠️ **PostgreSQL major version**: il volume `pgdata` è legato alla major version (pg16). Cambiare `pgvector/pgvector:pg16` → `pg17` rompe l'avvio (`database files are incompatible`); richiede migrazione esplicita con `pg_upgrade` o dump/restore, non basta cambiare il tag.

### Novità v0.9.6 (rilevanti per il progetto)

- **Smart directory sync built-in**: Open WebUI ora sincronizza nativamente una directory locale in una knowledge base (checksum-based, solo file nuovi/modificati). Gli script `import-pdfs-*.py` restano necessari perché gestiscono `access_grants` (pubblico/privato) che il sync nativo non gestisce.
- **`ENABLE_KB_EXEC: "true"`**: abilita un tool filesystem (`ls`, `cat`, `grep`, `find`, `head`, `tail`, `sed`) che i modelli AI possono usare per navigare e cercare nelle knowledge base. Attivato nel compose.
- **Knowledge base folders**: i file nelle KB ora si organizzano in sottocartelle con breadcrumb navigation — utile per collection con molti documenti.
- **Incremental sync con checksum**: alternativa allo script di import manuale. Il sync nativo evita re-upload di file invariati.
- **`oikb`**: tool companion ufficiale per sync da directory locale, GitHub, S3, Confluence e 40+ sorgenti. Alternativa futura agli script Python per l'ingestion.

### Regole critiche del pipeline RAG

- **RAG-only**: il system prompt vieta espressamente di rispondere senza fonte documentale. Mai rimuovere o aggirare questo vincolo.
- **Hybrid search** (BM25 + vettori) è abilitato per default — non disabilitare senza motivo esplicito.
- **Reranker disabilitato** per default (troppo lento senza GPU dedicata) — abilitare solo con hardware adeguato.
- **Idempotenza import**: gli script `import-pdfs-*.py` si appoggiano al **dedup nativo per contenuto** di OpenWebUI (risposta 400 "Duplicate content detected" → SKIP). Nessuna query SQL diretta né `docker exec`: tutto via API. ⚠️ La v0.9.6 ha cambiato lo schema (knowledge base folders): l'endpoint `/api/v1/knowledge/{id}` non espone più i file come array piatto (`files: null`), quindi il dedup per-filename non è affidabile — si usa quello per-contenuto del server.
- **Chunking**: modificare `CHUNK_SIZE` e `CHUNK_OVERLAP` con cautela — impattano la qualità del retrieval su tutti i documenti.

### Collections e accesso

- Le PDF collection sono mappate da cartelle in `./pdf/<nome-collection>/`
- Le collection **pubbliche** (import-pdfs-pubbliche.py) sono accessibili a tutti gli utenti autenticati
- Le collection **private** (import-pdfs-private.py) hanno accesso negato ai ruoli non autorizzati
- Il cleanup (cleanup-collections.py) cancella TUTTE le collection — usare con estrema cautela in produzione

### Configurazione

Tutti i segreti e parametri operativi vivono nel file `.env` (mai committato). Variabili chiave:

```
POSTGRES_PASSWORD        # Password superuser PostgreSQL
WEBUI_SECRET_KEY         # JWT secret OpenWebUI
OPENROUTER_API_KEY       # API key LLM remoto
PGADMIN_EMAIL/PASSWORD   # Credenziali pgAdmin
OWUI_EMAIL/PASSWORD      # Account admin per script import
HF_TOKEN                 # HuggingFace (opzionale, per modelli privati)
HF_REPO / HF_MODEL       # Configurazione modello GGUF locale
```

Copiare sempre da `.env.example` come base — non creare `.env` da zero.

### Docker e networking

- **Network `backend`**: postgres ↔ open-webui (isolato)
- **Network `frontend`**: caddy ↔ open-webui ↔ pgadmin
- **llama.cpp** gira sull'host (non containerizzato) — raggiunto via `host.docker.internal:8081`
- Logging configurato con driver JSON, max 10MB × 3 file rotation — non aumentare senza verificare spazio disco
- Per GPU diverse esistono file `docker-compose-gpu-*.yml` — usare il corretto per l'hardware target

### Script di utilità

| Script | Scopo | Rischio |
|--------|-------|---------|
| `import-pdfs-pubbliche.py` | Importa PDF in collection pubbliche | Basso |
| `import-pdfs-private.py` | Importa PDF in collection private | Basso |
| `cleanup-collections.py` | Cancella TUTTE le collection | **ALTO — irreversibile** |
| `utils/filter-models.py` | Abilita/disabilita modelli in OpenWebUI | Medio |

### Pattern da rispettare

1. **Microservizi containerizzati** — ogni componente ha il suo container; non aggiungere logica applicativa nel Caddyfile o nei container infra.
2. **Configuration via Environment** — nessun valore di configurazione hardcodato nel codice o nei Dockerfile.
3. **Volumes persistenti** — dati su `pgdata`, `openwebui_data`, `hf_cache`: mai usare bind mount locali per i dati di produzione.
4. **Health checks obbligatori** — ogni nuovo servizio aggiunto al compose deve avere un `healthcheck`.
5. **Idempotenza degli script** — gli script di import devono essere rieseguibili senza creare duplicati.
6. **RAG-only enforcement** — il prompt template che vincola le risposte ai documenti non va mai rimosso o indebolito.
