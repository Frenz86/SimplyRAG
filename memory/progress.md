# Progress

Cosa è stato fatto, errori incontrati, test eseguiti, risultati.

## Log
| Data | Fase | Azione | Esito |
|---|---|---|---|
| 2026-06-14 | FASE 1 | Blueprint: 5 domande + Schema + 8 invarianti in CLAUDE.md | DRAFT approvato |
| 2026-06-14 | FASE 1 | ADR-001 (page-preserving), ADR-002 (elimina filter-models), ADR-003 (llama default) | Scritti |
| 2026-06-14 | FASE 2 | Scritti 5 probe in `probes/` | Done |
| 2026-06-14 | FASE 2 | `probe_openrouter.py` eseguito (chiave reale) | ✅ OK — key valida, $6.21 spesi, NO hard cap |
| 2026-06-14 | FASE 2 | stack `docker compose up -d` (lo tiro su io) | ✅ up: postgres/open-webui/caddy healthy |
| 2026-06-14 | FASE 2 | `probe_postgres.py` | ✅ PG16.14, vector 0.8.2, n_docs=0 |
| 2026-06-14 | FASE 2 | `probe_owui.py` (fix bug encoding) | ✅ /health 200, signin admin@futura.com |
| 2026-06-14 | FASE 2 | `probe_embeddings.py` (riscritto come test dim) | 🔴 MISMATCH: colonna vector(1536) vs e5-base 768 → INSERT ERROR confermato |
| 2026-06-14 | FASE 2 | `probe_llamacpp.py` | ⚠️ down (atteso, ADR-003) |
| 2026-06-14 | FASE 2 | FIX embedding dim (ALTER colonna a 768) | ✅ applicato + ri-verificato: INSERT 768 passa. ivfflat da REINDEX dopo import reale |
| 2026-06-14 | FASE 2 | **FASE 2 CHIUSA** — tutti i canali verificati | ✅ openrouter, postgres, owui, embeddings; llama.cpp assente by design |
| 2026-06-14 | FASE 2 | **Crash-loop open-webui** (sintomo: Caddy 502, `ConnectionError` su `/api/v1/auths/signin`). Diagnosi via log + codice immagine: `VECTOR_LENGTH` è letto da `PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH` (default `1536`) ≠ colonna `768`, NON dedotto dal modello. | 🔴→✅ root-caused; fix env `PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH=768` nel compose → `up -d` → open-webui Healthy |
| 2026-06-14 | FASE 2 | **RE-VERIFICA** dei 5 probe su stack sano (post-fix) | ✅ postgres (PG16.14, vector 0.8.2, n_docs=0); owui (/health 200, signin admin, token 247 char); openrouter (key OK, **$6.28, NO hard cap**, 337 modelli, gemini entrambi); embeddings (colonna 768 = modello 768 = env 768, INSERT passa); llama.cpp ⚠️ down by design (ADR-003) |
| 2026-06-14 | FASE 3 | `SOP.md` scritta (livello A — ingestione page-preserving, I4) | ✅ approvata dall'utente ("procedi come raccomandato") |
| 2026-06-14 | FASE 3 | Verifica meccanismo pagina su codice reale OWUI 0.9.6 | ✅ `get_enriched_texts` non renderizza `page`; markdown splitter scarta headings ma keep header nel testo; token splitter non rispetta pagina → ADR-004 |
| 2026-06-14 | FASE 3 | `tools/{extract_pages,build_page_content,owui_client,import_pdfs}.py` + 2 `test_*.py` | ✅ tutti i test PASS (puri, no rete); dry-run: 5 PDF → 15 segmenti `# Pagina N` |
| 2026-06-14 | FASE 3 | config `ENABLE_MARKDOWN_HEADER_TEXT_SPLITTER=true` nel compose + restart | ✅ open-webui Healthy; env caricato; probe_owui OK |

## Errori (→ portare nel Registro di `CLAUDE.md`)
| Data | Errore | Causa radice | Stato |
|---|---|---|---|
| | | | |

## Verifiche end-to-end
- TODO
