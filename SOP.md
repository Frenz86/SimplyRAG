# SOP — Ingestione PDF page-preserving

> Standard Operating Procedure (livello **A** della triade A.N.T., FASE 3).
> Fonte di verità del comportamento **prima** del codice. vedi `PROTOCOL.md` §FASE 3.
> **Scope:** pipeline di import PDF → collection OpenWebUI. Risolve invarianti **I2/I3/I4** e ADR-001.

---

## 1. Scopo
Importare PDF in collection OpenWebUI (OWUI) in modo che **ogni chunk conosca la propria pagina**,
così le risposte RAG possono citare `document + page + snippet` (invarianti I2/I3).

Sostituisce `import-pdfs-pubbliche.py` e `import-pdfs-private.py` (95% duplicati; l'unica
differenza era `access_grants`: `public` = read-per-tutti, `private` = `[]`) con **un solo tool
parametrico** `--scope public|private`.

## 2. Invarianti coperte
- **I4 — Page preservata:** il testo entra nel vector DB taggato per pagina (oggi violato: l'estrazione
  fa `"\n".join(page.extract_text()...)` → blob piatto → pagina persa).
- **I3 — Page valida:** `1 ≤ page ≤ page_count(document)`.
- **I2 — Citazione obbligatoria:** ogni risposta affermativa cita document+page+snippet.

## 3. Vincoli accertati su OWUI 0.9.6 (non indovinati, verificati sul codice dell'immagine)
1. `document_chunk.vmetadata` è **JSONB** flessibile, ma `get_enriched_texts`
   (`retrieval/utils.py:308`) renderizza al LLM **solo** `name, title, headings, source, snippet` —
   **non `page`** e non chiavi arbitrarie. ⇒ la pagina **deve stare nel testo del chunk**.
2. `MarkdownHeaderTextSplitter` (`routers/retrieval.py:1408`) **scarta** i `headings` per-chunk
   (`metadata={**doc.metadata}`) ma con `strip_headers=False` **mantiene l'header nel `page_content`**.
   ⇒ un header `# Pagina N` finisce nel testo del chunk e il LLM lo vede.
3. Il `TokenTextSplitter` (splitter attivo, `CHUNK_SIZE=1500`) **non rispetta** i confini di pagina.
   ⇒ un chunk può coprire più pagine ⇒ citazione ambigua.
4. Controlliamo il `content` passato a `/api/v1/retrieval/process/file` (override dell'estrazione OWUI).
5. Dedup nativo OWUI: stesso content-hash → `400 "Duplicate content"` su `/knowledge/{id}/file/add`.

## 4. Design — meccanismo page-preserving
**Principio:** ogni chunk deve (a) stare entro una sola pagina e (b) contenere nel testo il proprio
numero di pagina. Si ottiene combinando **pre-chunk client-side + splitter markdown di OWUI**.

1. **Estrazione per pagina** con `pdfplumber`: pagina `i` (1-based) → `page_text[i]`.
2. **Pre-chunk client-side** di ogni `page_text[i]` in segmenti **≤ ~3500 caratteri (~900 token)**,
   ben sotto `CHUNK_SIZE=1500`, così il successivo splitter di OWUI **non spezza ulteriormente**.
3. **Prefisso obbligatorio** per ogni segmento: `\n# Pagina {i}\n\n` (header markdown H1).
4. **Concatenazione** di tutti i segmenti (nell'ordine di pagina) → unica stringa `content`.
5. **Feed a OWUI** via `/retrieval/process/file` (flow esistente, content-override).
6. OWUI con `ENABLE_MARKDOWN_HEADER_TEXT_SPLITTER=true` + `strip_headers=False`:
   - splitta sugli header `#` → **un segmento = un chunk**, ciascuno dentro la sua pagina;
   - ogni `page_content` inizia con `# Pagina {i}` (header mantenuto);
   - `RAG_TEXT_SPLITTER=token` poi NON spezza ulteriormente (segmenti già < 1500 token).

**Risultato:** ogni chunk porta `# Pagina N` nel testo → il LLM lo vede nel `[context]` →
`DEFAULT_RAG_TEMPLATE` (già custom nel compose) istruisce a citare "Pagina N". I3/I4 soddisfatti
senza patchare OWUI.

### Configurazione OWUI da aggiungere al compose (`docker-compose.yml`, blocco `open-webui.environment`)
```yaml
ENABLE_MARKDOWN_HEADER_TEXT_SPLITTER: "true"   # splita sui # Pagina N (header kept nel testo)
```
(`strip_headers` è già `False` di default in 0.9.6 — non serve impostarlo.)

## 5. Flusso (stati + decisioni + fallback)
```
[START]
  │
  ├─ signin OWUI (credenziali .env) ── fail ──→ HALT (credenziali/probe_owui)
  │
  ├─ per ogni (collection, folder) in COLLECTIONS:
  │    ├─ glob *.pdf nel folder ── vuoto ──→ skip collection
  │    ├─ get/create collection by name (dedup name)
  │    ├─ set access_grants:
  │    │     scope=public  → [{principal_type:user, principal_id:*, permission:read}]
  │    │     scope=private → []
  │    ├─ pre-check: GET /knowledge/{id}/files → set di `meta.file_hash` gia' presenti (1 chiamata/coll.)
  │    └─ per ogni PDF:
  │         ├─ sha256(byte file) ∈ set? ── sì ──→ SKIP **pre-embed** (no upload/process/embed). `--force` bypassa
  │         ├─ upload file → file_id
  │         ├─ estrai page_text[] (pdfplumber)
  │         ├─ build content: segmenti # Pagina N pre-chunked ── fallisce estrazione ──→ delete file, skip
  │         ├─ POST /retrieval/process/file {file_id, content}
  │         │     └─ !ok ──→ delete file, log, skip
  │         ├─ POST /knowledge/{id}/file/add {file_id}
  │         │     ├─ 200 → OK
  │         │     ├─ 400 "Duplicate content" → SKIP + delete file (dedup nativo)
  │         │     └─ altro errore → delete file, log
  │         └─ registra {collection, file, pages, chunks, scope}
  │
  ├─ stampa report riassuntivo (per PDF: pages/chunks, stato OK/SKIP/ERR)
  └─ [END]
```

### Fallback / edge case
- **Pagina vuota** (`extract_text()` → None/`""`): salta la pagina, NON generare `# Pagina N` vuoto.
- **Segmento che sfiora CHUNK_SIZE:** soglia conservativa (~3500 char) → margine ampio sul 1500-token.
- **Cross-page in merge:** `CHUNK_MIN_SIZE_TARGET` di OWUI può fondere segmenti piccoli adiacenti;
  se fuse, sono **della stessa pagina** (segmenti contigui della stessa pagina) → pagina preservata.
  Segmenti di pagine **diverse** hanno header `#` diversi → il markdown splitter li separa. ✅
- **PDF senza testo estrai bile** (immagini): page_text vuoto per tutte → content vuoto → OWUI
  rifiuta (`EMPTY_CONTENT`) → log "PDF senza testo, serve OCR" + skip. (OCR fuori scope di questa SOP.)

## 6. Livello T — tool atomici (`tools/`)
Ogni tool: UNA cosa, input tipizzato → output tipizzato, testabile in isolamento.

| Tool | Input → Output | Note |
|---|---|---|
| `tools/extract_pages.py` | `Path(pdf) → List[Page(i, text)]` | pdfplumber; salta pagine vuote; 1-based. Deterministico, no rete. |
| `tools/build_page_content.py` | `List[Page] → str` | pre-chunk ≤ ~3500 char + prefisso `# Pagina {i}`. Pura funzione. |
| `tools/owui_client.py` | wrapper auth + chiamate REST | signin, get/create collection, upload, process, add, access, delete. Riutilizato dai probe. |
| `tools/import_pdfs.py` | `--scope public\|private [--collections ...] [--dry-run]` | **Navigation**: orchestra i 3 sopra. Sostituisce i 2 script root. |

`--dry-run`: stampa il `content` che verrebbe inviato (con gli `# Pagina N`) senza chiamare OWUI →
verifica visiva del page-preserving prima di importare.

Ogni tool ha `test_<nome>.py` (deterministico, no rete per extract/build; owui_client testato via
mock o contro stack locale in FASE 4).

## 7. Test
- **Unit (deterministici, no rete):**
  - `test_extract_pages`: PDF di test 3 pagine → 3 Page con testo; PDF con pagina vuota → saltata.
  - `test_build_page_content`: ogni segmento inizia con `# Pagina N`; nessun segmento > ~3500 char;
    tutti i `1 ≤ N ≤ page_count` presenti (se la pagina ha testo).
- **End-to-end (FASE 4 — Stylize):** import di un PDF reale su stack locale → query RAG →
  verifica che la risposta citi `Pagina K` con K reale. Golden-set.

## 8. Decisioni da approvare (HALT prima del codice)
1. **Meccanismo page-preserving:** pre-chunk + markdown-splitter + header `# Pagina N` nel testo
   (raccomandato: nessun patch OWUI, robusto). Alternative scartate:
   - patchare `get_enriched_texts` per renderizzare `page` → version-fragile;
   - insert diretto in pgvector bypassando OWUI KB → perde integrazione UI/dedup OWUI.
2. **Config globale:** aggiungere `ENABLE_MARKDOWN_HEADER_TEXT_SPLITTER: "true"` al compose
   (influenza **tutti** gli import futuri — per un RAG documentale è il comportamento desiderato).
3. **Scope:** un solo tool `--scope public|private` sostituisce i 2 script (che vengono deprecati,
   non eliminati senza conferma — vedi memory `preserve-existing-files`).
4. **Niente OCR** in questa iterazione (PDF scanned → skip con log).

## 9. Definition of Done (questa SOP)
- [ ] SOP approvata dall'utente (punto 8)
- [ ] 4 tool atomici in `tools/` + test unitari verdi
- [ ] `ENABLE_MARKDOWN_HEADER_TEXT_SPLITTER=true` nel compose, stack riavviato, probe owui OK
- [ ] `--dry-run` mostra `# Pagina N` corretti su un PDF reale
- [ ] import reale di 1 PDF → query RAG → citazione con `Pagina K` valida (FASE 4)
