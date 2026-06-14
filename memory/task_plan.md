# Task Plan

Fasi, obiettivi, checklist del protocollo **B.L.A.S.T.**

## Obiettivo
Sistema RAG locale (OpenWebUI + pgvector) su documenti aziendali in crescita, che
**risponde solo dalle fonti** e **cita sempre documento + pagina**. Successo =
golden-set superato (≥95% corrette, 0 allucinazioni), p95 < 8s, restore verificato.

## Fasi
- [~] **B — Blueprint** — discovery (5 domande ✅) + Schema Dati + invarianti in `CLAUDE.md` (DRAFT → attesa approvazione)
- [x] **L — Link** — probe di ogni servizio esterno (`probes/`): postgres, openrouter, owui, embeddings, llama.cpp ✅ (ri-verificati 2026-06-14 post-fix; llama.cpp down by design ADR-003)
- [~] **A — Architect** — `SOP.md` ✅ + `tools/` import page-preserving ✅ (4 tool atomici + 2 test verdi; ADR-004). Restano: altri tool atomici + Navigation per query/citazione; DoD import in FASE 4
- [ ] **S — Stylize** — prompt RAG con citazione obbligatoria + golden-set + verifica end-to-end
- [ ] **T — Trigger** — backup schedulato + Self-Annealing Loop

## Checklist corrente (deriva dall'audit iniziale → `findings.md`)
- [ ] Approvazione Schema Dati da parte dell'utente (HALT)
- [ ] A1 `utils/filter-models.py` — MANTENERE (direttiva utente); opzionale FIX model names non distruttivo (ADR-002 revocato)
- [ ] A2 Risolvere LLM locale fantasma nel compose default (ADR-003)
- [ ] A3 Singola fonte di verità per i nomi modello
- [ ] A4 Aggiornare README + `.env.example` (placeholder secret, decommentare `OWUI_*`)
- [ ] B5 `WEBUI_SECRET_KEY` → placeholder in `.env.example`
- [ ] B6/B7 Decidere TLS vs LAN-only
- [ ] I4 Riscrivere ingestione page-preserving (ADR-001)
