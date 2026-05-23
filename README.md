# SimplyRAG

Sistema RAG locale basato su OpenWebUI + PostgreSQL/pgvector.

---

## Avvio

```bash
# 1) Crea il file .env (una volta sola)
cp .env.example .env        # poi edita con le tue chiavi

# 2) Tira su tutto
docker compose up -d

# 3) Abilita l'estensione vector su Postgres (una volta sola)
docker exec -it postgres psql -U owui -d openwebui -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 4) Apri OpenWebUI
# http://localhost  → crea il primo utente (sarà admin)
```

---

## import-pdfs.py

Importa PDF nelle knowledge collection di OpenWebUI.

**Pre-requisiti**

```bash
pip install requests pdfplumber
```

**Struttura cartelle PDF**

```
pdf/
├── risorse-umane/          # → collection "risorse-umane"
├── sicurezza-informatica/  # → collection "sicurezza-informatica"
├── amministrazione/        # → collection "amministrazione"
└── qualita/                # → collection "qualita"
```

Metti i file `.pdf` nelle sottocartelle corrispondenti alla collection.

**Configurazione** (prime righe dello script)

```python
EMAIL    = "admin@futura.com"   # email dell'utente admin in OpenWebUI
PASSWORD = "futura1234"         # password
BASE     = "http://localhost"   # URL di OpenWebUI
```

**Esecuzione**

```bash
python import-pdfs.py
```

**Comportamento**

- Se la collection non esiste la crea, altrimenti la riusa.
- Controlla via DB se il file è già importato: lo salta (`SKIP`) per evitare duplicati.
- Per ogni PDF nuovo: carica il file, estrae il testo con `pdfplumber`, lo indicizza nel vettore, lo aggiunge alla collection.

---

## cleanup-collections.py

Lista e cancella le knowledge collection da OpenWebUI.

**Pre-requisiti**

```bash
pip install requests
```

**Esecuzione**

```bash
python cleanup-collections.py
```

**Comportamento**

1. Si autentica con le stesse credenziali di `import-pdfs.py`.
2. Stampa l'elenco di tutte le collection presenti (id + nome).
3. Chiede conferma interattiva: `Vuoi cancellarle tutte? (s/n)`
4. Se confermi con `s` cancella tutto; altrimenti esce senza toccare nulla.

> **Attenzione:** la cancellazione è irreversibile. I PDF nella cartella `./pdf/` non vengono toccati; vengono rimossi solo i metadati e i vettori in OpenWebUI. Dopo il cleanup puoi rieseguire `import-pdfs.py` per reimportare da zero.
