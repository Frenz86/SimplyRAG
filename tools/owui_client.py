"""owui_client — Tool atomico (livello T).

Wrapper minimale sulle REST API di OpenWebUI usate dalla pipeline di ingestione.
UNA sola responsabilita': parlare con OWUI (auth reale via signin, raise su errore).
Nessuna business logic di chunking/page (quelle vivono in extract_pages/build_page_content).

Endpoint verificati su OWUI 0.9.6 (vedi memory/findings.md). Riutilizzabile dai probe.

Uso:
    c = OwuiClient.from_env()
    coll_id = c.get_or_create_collection("amministrazione")
    c.set_collection_access(coll_id, scope="public")   # o "private"
    fid = c.upload_file(Path("doc.pdf"))
    c.process_file(fid, content)
    res = c.add_file_to_knowledge(coll_id, fid)         # AddResult(status="added"|"duplicate"|"error")
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()


class OwuiError(RuntimeError):
    """Errore di una chiamata OWUI: status + body grezzo."""


@dataclass(frozen=True)
class AddResult:
    status: str   # "added" | "duplicate" | "error"
    detail: str = ""


@dataclass
class OwuiClient:
    base_url: str
    token: str

    @classmethod
    def from_env(cls) -> "OwuiClient":
        base = os.environ.get("OWUI_BASE", "http://localhost").rstrip("/")
        email = os.environ.get("OWUI_EMAIL")
        password = os.environ.get("OWUI_PASSWORD")
        if not (email and password):
            raise OwuiError("OWUI_EMAIL/OWUI_PASSWORD mancanti in .env")
        r = requests.post(f"{base}/api/v1/auths/signin",
                          json={"email": email, "password": password}, timeout=15)
        if not r.ok:
            raise OwuiError(f"signin HTTP {r.status_code}: {r.text[:200]}")
        token = r.json().get("token")
        if not token:
            raise OwuiError("signin OK ma nessun token nella risposta")
        return cls(base_url=base, token=token)

    @property
    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    # ---------------- collections ----------------
    def list_collections(self) -> list[dict]:
        r = requests.get(f"{self.base_url}/api/v1/knowledge/", headers=self._h, timeout=15)
        if not r.ok:
            raise OwuiError(f"list collections HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        return data if isinstance(data, list) else data.get("items", [])

    def get_or_create_collection(self, name: str, description: str = "") -> str:
        for c in self.list_collections():
            if c.get("name") == name:
                return c["id"]
        r = requests.post(f"{self.base_url}/api/v1/knowledge/create",
                          headers=self._h,
                          json={"name": name, "description": description}, timeout=15)
        if not r.ok:
            raise OwuiError(f"create collection '{name}' HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["id"]

    def set_collection_access(self, collection_id: str, scope: str) -> None:
        """scope='public'  -> read per tutti gli utenti (collection pubblica).
           scope='private' -> nessun grant (solo owner)."""
        if scope not in ("public", "private"):
            raise ValueError(f"scope deve essere 'public'|'private', got {scope!r}")
        grants = ([{"principal_type": "user", "principal_id": "*", "permission": "read"}]
                  if scope == "public" else [])
        r = requests.post(f"{self.base_url}/api/v1/knowledge/{collection_id}/access/update",
                          headers=self._h, json={"access_grants": grants}, timeout=15)
        if not r.ok:
            raise OwuiError(f"set access HTTP {r.status_code}: {r.text[:200]}")

    def list_kb_files(self, collection_id: str) -> list[dict]:
        """File gia' presenti nella KB: [{id, filename, hash, meta:{file_hash,...}}].
        Usato per il pre-check PRE-embed (evita di ri-calcolare gli embeddings di file gia' importati)."""
        r = requests.get(f"{self.base_url}/api/v1/knowledge/{collection_id}/files",
                         headers=self._h, timeout=15)
        if not r.ok:
            raise OwuiError(f"list kb files HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        items = data.get("items") if isinstance(data, dict) else data
        return items or []

    def delete_collection(self, collection_id: str) -> None:
        """Cancella una KB (DELETE /knowledge/{id}/delete). Distruttivo: serve per reset pulito.
        Nota: i chunk in document_chunk della vecchia collection restano orfani (OWUI non pulisce
        in cascata); con un re-import la KB avvera' un nuovo id -> gli orfani non vengono piu' querydati."""
        r = requests.delete(f"{self.base_url}/api/v1/knowledge/{collection_id}/delete",
                            headers=self._h, timeout=30)
        if not r.ok:
            raise OwuiError(f"delete collection HTTP {r.status_code}: {r.text[:200]}")

    # ---------------- files ----------------
    def upload_file(self, pdf_path: Path) -> str:
        with open(pdf_path, "rb") as f:
            r = requests.post(f"{self.base_url}/api/v1/files/", headers=self._h,
                              files={"file": (pdf_path.name, f, "application/pdf")}, timeout=120)
        if not r.ok:
            raise OwuiError(f"upload {pdf_path.name} HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["id"]

    def process_file(self, file_id: str, content: str) -> None:
        """Content-override: OWUI chunka `content` (page-preserving) invece di estrarre."""
        r = requests.post(f"{self.base_url}/api/v1/retrieval/process/file",
                          headers=self._h, json={"file_id": file_id, "content": content},
                          timeout=180)
        if not r.ok:
            raise OwuiError(f"process file HTTP {r.status_code}: {r.text[:200]}")

    def add_file_to_knowledge(self, collection_id: str, file_id: str) -> AddResult:
        r = requests.post(f"{self.base_url}/api/v1/knowledge/{collection_id}/file/add",
                          headers=self._h, json={"file_id": file_id}, timeout=60)
        if r.ok:
            return AddResult("added")
        if r.status_code == 400 and "Duplicate content" in r.text:
            return AddResult("duplicate", "Duplicate content")
        return AddResult("error", f"HTTP {r.status_code}: {r.text[:200]}")

    def delete_file(self, file_id: str) -> None:
        # best-effort: non raise (usato in cleanup su file gia' caricati parzialmente)
        requests.delete(f"{self.base_url}/api/v1/files/{file_id}", headers=self._h, timeout=30)
