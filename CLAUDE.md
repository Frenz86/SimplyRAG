# CLAUDE.md — Costituzione del Progetto

> Protocollo operativo: **B.L.A.S.T. + A.N.T.** → vedi `PROTOCOL.md`.
> **Affidabilità prima della velocità. Mai indovinare la business logic.**

Questo file è la **fonte di verità** del comportamento del sistema. Si compila in
**FASE 1 — Blueprint**, prima di scrivere qualsiasi codice.

> Stato: **DRAFT FASE 1 — in attesa di approvazione utente** (HALT). Le voci
> marcate `[PROPOSTA]` sono default proposti dove l'utente non ha fornito un valore.

---

## 1. Schema Dati
Forma di input → output. Tipi, campi obbligatori/opzionali, esempi.

### Input A — Documento in ingestione
Un file + metadati che lo collocano in una collection. **OBBLIGATORIO** che il
contenuto arrivi **strutturato per pagina** (vedi invariante I4): niente testo
piatto che distrugge i confini di pagina.
```json
{
  "file": "<blob PDF/DOCX/HTML>",
  "filename": "procedura-fatturazione-attiva.pdf",
  "collection": "amministrazione",
  "scope": "public | private",
  "pages": [
    {"page": 1, "text": "...testo pagina 1..."},
    {"page": 2, "text": "...testo pagina 2..."}
  ]
}
```
- `filename`, `collection`, `scope`, `pages[]` **obbligatori**.
- `collection` è **indicativo**: le 4 attuali (risorse-umane, sicurezza-informatica,
  amministrazione, qualita) non sono un elenco chiuso — cresce con l'azienda.

### Input B — Query utente
```json
{
  "query": "Quali sono le scadenze della procedura di fatturazione?",
  "collections": ["amministrazione"]
}
```
- `query` obbligatorio; `collections` opzionale (default: tutte quelle accessibili).

### Output — Risposta con tracciabilità fonte (RAG-only)
```json
{
  "answer": "Le scadenze sono: emissione entro 15 giorni ...",
  "found": true,
  "citations": [
    {
      "document": "procedura-fatturazione-attiva.pdf",
      "page": 3,
      "snippet": "La fattura deve essere emessa entro 15 giorni dalla consegna..."
    }
  ]
}
```
- `answer`: stringa, **solo** da chunk recuperati.
- `found`: bool. `false` ⟺ nessuna fonte a supporto ⟺ `answer` = sentinel (sotto).
- `citations[]`: **obbligatorio non vuoto** quando `found=true`. Ogni voce ha
  `document` (str), `page` (int ≥ 1, ≤ pagine del documento), `snippet` (str).
- **Sentinel "non trovato"** (stringa fissa, invariante I5):
  `"Non ho trovato questa informazione nei documenti disponibili."`

### Esempi
- ✅ **Valido:** `answer` con `found=true` + ≥1 `citation` con `document`+`page`+`snippet`, e ogni affermazione dell'answer è coperta da uno snippet.
- ❌ **Non valido:** `answer` con contenuto **non** coperto da alcuna `citation` (allucinazione).
- ❌ **Non valido:** `citation` senza `page`, o con `page` fuori range.
- ❌ **Non valido:** `found=true` con `citations=[]`, o `found=false` con `citations` non vuote.

## 2. Regole comportamentali
- **RAG-only:** la risposta deriva **esclusivamente** dai chunk recuperati. Nessuna conoscenza esterna, nessuna invenzione.
- **Tracciabilità obbligatoria:** ogni risposta affermativa cita documento + pagina + snippet.
- **Silenzio onesto:** se nessun chunk a supporto, restituisci il sentinel fisso — non improvvisare.
- **Dedup:** un contenuto già presente in una collection non viene re-importato (dedup nativo OWUI "Duplicate content").
- **Scope di accesso:** collection `public` = leggibili da ogni utente; `private` = solo owner. Mai esporre `private` ad altri.
- **Determinismo nei Tool, ragionamento nella Navigation** (A.N.T.): i tool non contengono business logic ambigua.

## 3. Invarianti architetturali
Cose che devono essere **SEMPRE** vere.
- **I1 — RAG-only assoluto.** Nessuna esce dal sistema senza fonte nei chunk recuperati.
- **I2 — Citazione obbligatoria.** `found=true` ⟹ `len(citations) ≥ 1`, con `document`+`page`+`snippet`.
- **I3 — Page valida.** Per ogni `citation`, `1 ≤ page ≤ page_count(document)`.
- **I4 — Page preservata in ingestione.** Il testo entra nel vector DB **taggato per pagina**. Un documento importato senza metadati di pagina **non può** generare citazioni valide → l'ingestione deve rifiutarlo o reprocessarlo. *(Oggi violato: vedi ADR-001.)*
- **I5 — Sentinel biunivoco.** `found=false` ⟺ `citations=[]` ⟺ `answer` è esattamente la stringa sentinel.
- **I6 — Unicità del contenuto.** Nessun chunk duplicato nella stessa collection.
- **I7 — Data residency locale.** Documenti e vettori restano nei container locali (Postgres volume); nessun dato personale esce verso cloud tranne la query/prompt verso il LLM (vedi I8).
- **I8 — Privacy LLM.** verso OpenRouter viaggiano solo `query` + `snippet` recuperati (già necessari), mai dump interi di collection. `[PROPOSTA]` GDPR: documenti HR + fatturazione contengono dati personali → considerare quale LLM è ammissibile.

## 4. Contratti delle interfacce
Per ogni servizio esterno: endpoint, auth, shape **reale** della risposta, rate limit, quirk.
(Da verificare con probe in **FASE 2 — Link**.)

| Servizio | Endpoint | Auth | Shape risposta | Note |
|---|---|---|---|---|
| Postgres/pgvector | `postgres:5432`, db `openwebui`, user `owui` | `POSTGRES_PASSWORD` | SQL; ext `vector` | backup via `pg_dump`; `init/01-vector.sql` |
| OpenWebUI | `localhost:80` (Caddy) → `open-webui:8080` | Bearer JWT da `/api/v1/auths/signin` | REST `/api/v1/*` | dedup `400 "Duplicate content"` su `knowledge/{id}/file/add` |
| OpenRouter | `https://openrouter.ai/api/v1` | Bearer `OPENROUTER_API_KEY` | OpenAI-compat (`/models`, `/chat/completions`) | modelli attivi: `gemini-2.5-flash`, `gemini-2.5-flash-lite` |
| llama.cpp | `host.docker.internal:8081` (default) / `llama-cpp:8081` (GPU) | `no-key` | OpenAI-compat | **ASSENTE** nel compose default → vedi criticità A2 |

## 5. Definition of Done
- [ ] Schema dati definito e **approvato** dall'utente
- [ ] Invarianti I1–I8 codificate come controlli/test
- [ ] Ogni link esterno verificato con probe (`probes/`): postgres, openrouter, owui, embeddings, llama.cpp
- [ ] Ingestione preserva `page` (I4) — risolve ADR-001
- [ ] SOP + Navigation + Tool atomici (`tools/`) con test, incluso 1 tool import unificato
- [ ] Golden-set (≥20 Q&A attese) + verifica qualità: ≥95% risposte corrette con citazione valida, 0 allucinazioni
- [ ] p95 < 8s sul golden-set `[PROPOSTA]`
- [ ] Restore DB verificato end-to-end (backup → drop → restore → query OK)
- [ ] Trigger configurato (backup schedulato minimo)
- [ ] Self-Annealing Loop attivo, errori noti → regole in §6

`[PROPOSTA]` **Criteri di successo misurabili (Q5):** ≥100 doc indicizzati senza duplicati; golden-set superato; p95 < 8s; restore verificato; 0 risposte senza fonte.

`[PROPOSTA]` **Vincoli (Q4):** latenza target p95 < 8s (ceiling 15s = degradato); budget OpenRouter **[da definire €/mese]** con alert 80% + hard cap; GDPR applicabile (residency locale già soddisfatta); 5–10 utenti concorrenti attesi; HTTP accettabile solo su LAN fidata, TLS obbligatorio se esposta fuori LAN.

## 6. Registro Errori → Regole (Self-Annealing)
Ogni errore diventa una **regola permanente**. Un errore può accadere **una sola volta**.

| Data | Errore (causa radice) | Regola permanente | Test |
|---|---|---|---|
| 2026-06-14 | Embedding dim mismatch: `document_chunk.vector` era `vector(1536)` ma il modello configurato (e5-base) produce 768 → ogni insert falliva con "expected 1536 dimensions, not 768". Causa: colonna residua da config precedente; OWUI 0.9.6 non riconcilia la dimensione allo startup. | Ogni cambio di `RAG_EMBEDDING_MODEL` richiede verifica e (se diversa) ALTER di `document_chunk.vector` alla nuova dimensione **prima** di qualsiasi import. L'embedding è considerato "canale" e va verificato con il probe. | `probes/probe_embeddings.py` (INSERT in transazione con ROLLBACK); inserito nella DoD §5. |
| 2026-06-14 | Crash-loop open-webui → unhealthy → Caddy 502 / `ConnectionError` su `/api/v1/auths/signin`. Causa **distinta** dalla riga sopra: modello (e5-base 768) e colonna (`vector(768)`) erano ENTRAMBI corretti, ma OWUI legge `VECTOR_LENGTH` da `PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH` (`config.py:778`, default `1536`) — **non lo deduce dal modello**. Env non impostato → `check_vector_length` (`pgvector.py:265`) solleva "VECTOR_LENGTH 1536 does not match existing vector column dimension 768" a tempo di import → uvicorn non parte → mai healthy. | `PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH` va impostato esplicitamente = dim embedding (e5-base → `"768"`) nel compose. Non basta che colonna e modello combacino: OWUI lo **dichiara separatamente**. Allineamento richiesto su 3 fronti: modello ↔ colonna ↔ env, tutti uguali. | `docker compose up -d` → `open-webui Healthy`; `docker compose logs open-webui \| grep -c VECTOR_LENGTH` = 0 e `grep Initialization complete` ≥ 1; `EMBED_DIM=768 python probes/probe_embeddings.py`. |
