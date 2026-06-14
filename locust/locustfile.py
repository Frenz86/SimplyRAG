"""Load test SimplyRAG — scenario RAG completo (login → query con knowledge base → LLM).

Ogni richiesta esegue una chat completion REALE che interroga i documenti via LLM:
ATTENZIONE, ogni richiesta consuma credito OpenRouter. Vedi README.md.

Avvio tipico (UI web su http://localhost:8089):
    locust -f locustfile.py --host http://localhost

Headless (50 utenti, +5/s, 3 minuti):
    locust -f locustfile.py --host http://localhost \
           --headless -u 50 -r 5 -t 3m --csv report
"""
import os
import random

from locust import HttpUser, between, task, events

# In locale leggiamo .env; nel container ufficiale Locust dotenv non c'è e le
# variabili arrivano già dall'ambiente: in quel caso l'import si salta senza errori.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass

EMAIL = os.environ["OWUI_EMAIL"]
PASSWORD = os.environ["OWUI_PASSWORD"]

# Modello LLM: default sul più economico per contenere i costi del load test.
MODEL = os.environ.get("LOAD_TEST_MODEL", "google/gemini-2.5-flash-lite")

# Knowledge base da interrogare. Vuoto = la prima collection disponibile.
# Imposta LOAD_TEST_KB per puntare a una collection specifica per nome.
KB_NAME = os.environ.get("LOAD_TEST_KB", "")

# Domande realistiche ruotate a ogni richiesta per non colpire sempre la stessa cache.
QUERIES = [
    "Riassumi i punti chiave dei documenti in massimo 5 punti.",
    "Quali scadenze o date importanti sono presenti?",
    "Spiega i termini tecnici principali presenti nei documenti.",
    "Quali azioni devo intraprendere in base a questi documenti?",
    "C'è qualche obbligo normativo o di compliance citato?",
    "Elenca i ruoli e le responsabilità descritti.",
]


class RagUser(HttpUser):
    # Attesa realistica tra una domanda e l'altra (un utente non spara richieste a raffica).
    wait_time = between(3, 8)

    def on_start(self) -> None:
        """Login una volta per utente simulato; recupera token e knowledge base."""
        self.token = None
        self.kb_id = None

        with self.client.post(
            "/api/v1/auths/signin",
            json={"email": EMAIL, "password": PASSWORD},
            catch_response=True,
            name="auth: signin",
        ) as resp:
            if resp.status_code == 429:
                resp.failure("rate-limited (429) — Caddy auth zone: 10 req/min per IP")
                return
            if resp.status_code != 200 or "token" not in resp.json():
                resp.failure(f"login fallito: {resp.status_code} {resp.text[:200]}")
                return
            self.token = resp.json()["token"]

        headers = {"Authorization": f"Bearer {self.token}"}
        resp = self.client.get("/api/v1/knowledge/", headers=headers, name="kb: list")
        if resp.status_code != 200:
            return
        data = resp.json()
        collections = data if isinstance(data, list) else data.get("items", [])
        if not collections:
            return
        if KB_NAME:
            match = next((c for c in collections if c["name"] == KB_NAME), None)
            self.kb_id = match["id"] if match else collections[0]["id"]
        else:
            self.kb_id = collections[0]["id"]

    @task
    def rag_query(self) -> None:
        if not self.token:
            return

        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": random.choice(QUERIES)}],
            "stream": False,
        }
        if self.kb_id:
            payload["files"] = [{"type": "collection", "id": self.kb_id}]

        with self.client.post(
            "/api/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
            name="rag: chat completion",
        ) as resp:
            if resp.status_code == 429:
                resp.failure("rate-limited (429) — Caddy general zone: 240 req/min per IP")
            elif resp.status_code != 200:
                resp.failure(f"completion fallita: {resp.status_code} {resp.text[:200]}")
            elif not resp.json().get("choices"):
                resp.failure("risposta senza 'choices'")


@events.test_start.add_listener
def _on_start(environment, **_kwargs) -> None:
    print(f"[load-test] host={environment.host} model={MODEL} kb={KB_NAME or '(prima disponibile)'}")
    print("[load-test] ATTENZIONE: ogni richiesta consuma credito OpenRouter.")
