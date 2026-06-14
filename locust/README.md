# Load test SimplyRAG (Locust)

Misura quanti utenti/richieste regge lo stack. Scenario **RAG completo**: ogni utente
simulato fa login, allega una knowledge base e interroga l'LLM con domande reali.

> ⚠️ **Costo reale.** Ogni richiesta esegue una chat completion via OpenRouter e
> consuma credito. Di default usa il modello più economico
> (`google/gemini-2.5-flash-lite`). Tieni d'occhio la spesa e fai prove brevi.

## Variabili (da `.env` nella root del progetto)

| Variabile | Default | Note |
|-----------|---------|------|
| `OWUI_EMAIL` / `OWUI_PASSWORD` | — | Account usato dagli utenti simulati (obbligatorie) |
| `LOAD_TEST_MODEL` | `google/gemini-2.5-flash-lite` | Modello LLM per il test |
| `LOAD_TEST_KB` | prima collection | Nome della knowledge base da interrogare |

## Due modalità

### 1. Attraverso Caddy (realistico, include il rate limit)
Punta a `http://localhost` → passa da Caddy. **Atteso: molti `429`** perché il Caddyfile
limita a **240 req/min per IP** (zona general) e **10/min** sull'auth. Da una sola macchina
sei un solo IP, quindi questo misura il *rate limiter*, non la capacità pura dell'app.
Utile per validare che il rate limiting funzioni.

```bash
pip install -r requirements.txt
locust -f locustfile.py --host http://localhost
# UI: http://localhost:8089
```

### 2. Diretto su open-webui (capacità reale, bypassa il rate limit)
Esegue Locust dentro la rete Docker e colpisce `open-webui:8080` saltando Caddy.
È il modo corretto per sapere **quanti user/req regge davvero l'app**.

```bash
# lo stack principale dev'essere già su (docker compose up -d)
# lanciare DALLA ROOT del progetto: --env-file fa trovare il .env (qui sta la project dir su locust/)
docker compose --env-file .env -f locust/docker-compose.locust.yml up --build
# UI: http://localhost:8089  (host già impostato su open-webui:8080)
```

## Headless (numeri in CSV, senza UI)

```bash
locust -f locustfile.py --host http://localhost \
       --headless -u 50 -r 5 -t 3m --csv report
```

- `-u 50`  utenti concorrenti totali
- `-r 5`   nuovi utenti avviati al secondo (ramp-up)
- `-t 3m`  durata
- `--csv report` → `report_stats.csv`, `report_failures.csv`, ecc.

## Come leggere i risultati

Sali con `-u` finché uno di questi peggiora — quello è il tuo tetto:

- **Failures %** che cresce (timeout, `5xx`): l'app è satura.
- **p95 / p99 latency** che esplode: oltre la soglia di esperienza accettabile.
- **`429`**: stai colpendo il rate limit di Caddy, non l'app (passa alla modalità 2).

Il numero di RPS sostenibile con failures ~0% e p95 stabile è la capacità reale dello stack
**per il modello LLM scelto** (il collo di bottiglia è quasi sempre la latenza dell'LLM).
