# Decisions

Scelte architetturali e la motivazione di ognuna (ADR leggeri).

## ADR-001 — Ingestione deve preservare il numero di pagina
- **Contesto:** L'utente (FASE 1, Q2) vuole risposta con **tracciabilità della fonte (citazione + pagina)**. Gli script attuali `import-pdfs-pubbliche.py` / `-private.py` fanno `"\n".join(page.extract_text() ...)` appiattendo tutto il PDF in una stringa, poi passano `content` piatto a `/retrieval/process/file`. I numeri di pagina sono persi **prima** del chunking → nessuna citazione potrà mai indicare la pagina.
- **Decisione:** L'ingestione estrae il testo **per pagina** e tagga ogni segmento/chunk con il proprio numero di pagina. Invariante I4 codificata in `CLAUDE.md`: un documento senza metadati di pagina non può generare citazioni valide.
- **Motivazione:** La tracciabilità fonte+pagina è un requisito esplicito di output; senza page-preserving ingestion è irraggiungibile.
- **Conseguenze:** I due script import vanno riscritti come **1 tool atomico** `import_pdfs.py --scope public|private` che estrae per-pagina. Da verificare in FASE 2 come OWUI 0.9.6 riceve/persiste il metadato `page` sui chunk (probe).

## ADR-002 — `utils/filter-models.py` — MANTENERE (direttiva utente, 2026-06-14)
- **Contesto:** Lo script filtra i modelli con un `KEEP` set che nomina modelli inesistenti (`gemini-3.5-flash`, `gemini-3.1-flash-lite`), usando endpoint deprecati in OWUI 0.9.6. Eseguendolo così com'è nessun modello risulta attivo → RAG rotto.
- **Decisione (REVOCATA la cancellazione):** L'utente ha bloccato esplicitamente l'eliminazione dello script. **Mantenere il file.** Opzione residua (da confermare): FIX non distruttivo — allineare il `KEEP` set ai modelli reali (`gemini-2.5-flash`, `gemini-2.5-flash-lite`) e verificare gli endpoint per OWUI 0.9.6.
- **Motivazione:** Rispetto dei file esistenti del progetto; lo script fa parte del flusso operativo dell'utente (è in `instructions.txt`).
- **Conseguenze:** Niente `git rm`. Il filtro modelli nativo (`ENABLE_MODEL_FILTER` + `MODEL_FILTER_LIST`) resta comunque la fonte primaria; filter-models.py va considerato "da sistemare", non "da cancellare".

## ADR-003 — LLM locale opzionale nel compose default
- **Contesto:** Il compose default lista un modello locale (`Qwen3.6-35B...gguf` su `host.docker.internal:8081`) ma non definisce il servizio `llama-cpp` (solo le varianti GPU). Selezione del modello locale → errore runtime.
- **Decisione (proposta):** Nel compose default rimuovere il modello locale dalla lista; tenerlo solo nelle varianti GPU, OPPURE aggiungere un servizio `llama-cpp` con `profiles: [local]` attivabile on-demand.
- **Motivazione:** Il compose default deve avviarsi e funzionare senza hardware GPU.
- **Conseguenze:** Da confermare con l'utente (Q3 conferma i 3 sistemi esterni, ma l'HW target è multi-filo).

## ADR-004 — Meccanismo page-preserving: pre-chunk + header markdown `# Pagina N` (2026-06-14, APPROVATO)
- **Contesto:** ADR-001 richiede page-preserving. Verifica sul codice reale OWUI 0.9.6 (non indovinata): (1) `get_enriched_texts` (`retrieval/utils.py:308`) renderizza al LLM **solo** `name/title/headings/source/snippet`, **mai** `page` né chiavi arbitrarie → la pagina deve stare nel **testo** del chunk; (2) `MarkdownHeaderTextSplitter` (`routers/retrieval.py:1408`) **scarta** i `headings` per-chunk (`metadata={**doc.metadata}`) ma con `strip_headers=False` mantiene l'header nel `page_content`; (3) il `TokenTextSplitter` (attivo, `CHUNK_SIZE=1500`) non rispetta i confini di pagina.
- **Decisione (approvata dall'utente, "procedi come raccomandato"):** pre-chunk lato client (≤ ~3500 char, ben sotto i 1500 token) + prefisso `# Pagina {N}` (header markdown H1) per segmento + `ENABLE_MARKDOWN_HEADER_TEXT_SPLITTER=true` nel compose. Risultato: ogni chunk sta in **una sola pagina** e porta `# Pagina N` nel testo → il LLM lo vede in `[context]` e lo cita. **Nessun patch a OWUI**.
- **Alternative scartate:** (a) patch di `get_enriched_texts` via `sed` come env.py → version-fragile ai futuri update OWUI; (b) insert diretto in pgvector bypassando la KB OWUI → perde integrazione UI + dedup nativo.
- **Conseguenze:** config **globale** cambiata (tutti gli import futuri splittano su header — desiderato per un RAG documentale). Implementato in `tools/{extract_pages,build_page_content,owui_client,import_pdfs}.py` + `test_*.py` (verdi). I 2 script root deprecati (NON eliminati, vedi memory `preserve-existing-files`). DoD residua in `SOP.md` §9: import reale + query RAG + citazione `Pagina K` → **FASE 4 (Stylize)**.
- **Quirk noto (mitigato):** `CHUNK_MIN_SIZE_TARGET` di OWUI può fondere segmenti piccoli adiacenti; se fusi sono della **stessa** pagina (segmenti contigui) → pagina preservata; segmenti di pagine diverse hanno header `#` diversi → il markdown splitter li separa comunque. Segmenti > CHUNK_SIZE: impossibili (soglia conservativa).
