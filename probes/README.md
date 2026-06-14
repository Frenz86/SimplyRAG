# probes/

Un **probe script minimale e isolato** per ogni servizio esterno (FASE 2 — Link).
Ogni probe: autentica con credenziale **reale** → chiamata più semplice possibile
(`ping` / `whoami` / `SELECT 1`) → stampa la **risposta grezza**.

**Regola:** Link rotto = **HALT**. Nessun canale non verificato prosegue.

Esempio: `probe_<servizio>.py`
