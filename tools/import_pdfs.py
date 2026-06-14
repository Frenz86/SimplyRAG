"""import_pdfs — Navigation (livello N della triade A.N.T.).

Orchestra i tool atomici T (extract_pages, build_page_content, owui_client) nella pipeline
di ingestione page-preserving. Sostituisce import-pdfs-pubbliche.py e import-pdfs-private.py
(95% duplicati). vedi SOP.md.

Navigation ragiona, Tools eseguono: qui si decide COSA/QUANDO (scope, selezione collection,
dry-run, gestione errori per-file senza abortire il batch); la logica deterministica sta nei T.

Uso (da root del progetto):
    python tools/import_pdfs.py --scope public                    # importa tutto, read-per-tutti
    python tools/import_pdfs.py --scope private                   # solo owner
    python tools/import_pdfs.py --scope public --dry-run          # stampa il content page-preserving, no rete
    python tools/import_pdfs.py --scope public --collections amministrazione,qualita
"""
from __future__ import annotations
import argparse
import hashlib
import sys
from pathlib import Path

# bootstrap import dei tool fratelli (cosi' e' runnable: python tools/import_pdfs.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_pages import extract_pages, page_count          # noqa: E402
from build_page_content import build_page_content, count_segments  # noqa: E402
from owui_client import OwuiClient, OwuiError                # noqa: E402

# collection -> cartella PDF (centralizzata: prima duplicata nei 2 script root)
COLLECTIONS = {
    "risorse-umane":         "./pdf/risorse-umane",
    "sicurezza-informatica": "./pdf/sicurezza-informatica",
    "amministrazione":       "./pdf/amministrazione",
    "qualita":               "./pdf/qualita",
}


def file_sha256(path: Path) -> str:
    """sha256 dei byte del file (stesso algoritmo di OWUI meta.file_hash).
    Usato per il pre-check PRE-embed: se il file e' gia' nella KB, skip senza embeddings."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Import PDF page-preserving in OpenWebUI (SOP, invariante I4).")
    p.add_argument("--scope", required=True, choices=["public", "private"],
                   help="public = leggibile da ogni utente; private = solo owner")
    p.add_argument("--collections", default="",
                   help="lista separata da virgola (default: tutte). Es: amministrazione,qualita")
    p.add_argument("--dry-run", action="store_true",
                   help="estrae e mostra il content page-preserving SENZA chiamare OWUI")
    p.add_argument("--force", action="store_true",
                   help="ignora il pre-check file_hash e re-importa comunque (ri-embedda)")
    return p.parse_args()


def select_collections(filter_csv: str) -> dict:
    if not filter_csv:
        return dict(COLLECTIONS)
    wanted = [c.strip() for c in filter_csv.split(",") if c.strip()]
    missing = [c for c in wanted if c not in COLLECTIONS]
    if missing:
        print(f"ERR: collection sconosciute: {missing}. Valide: {list(COLLECTIONS)}", file=sys.stderr)
        sys.exit(2)
    return {c: COLLECTIONS[c] for c in wanted}


def dry_run(collections: dict) -> int:
    """Verifica visiva del page-preserving: nessuna scrittura, nessuna rete."""
    total_segments = 0
    for coll, folder in collections.items():
        pdfs = sorted(Path(folder).glob("*.pdf"))
        if not pdfs:
            print(f"[{coll}] nessun PDF, salto.")
            continue
        print(f"\n[{coll}] {len(pdfs)} PDF  (DRY-RUN, nessuna scrittura)")
        for pdf in pdfs:
            pages = extract_pages(pdf)
            total = page_count(pdf)
            segs = count_segments(pages)
            total_segments += segs
            print(f"  {pdf.name}: {total} pagine, {len(pages)} con testo, {segs} segmenti")
            if pages:
                content = build_page_content(pages)
                heads = [ln for ln in content.split("\n") if ln.startswith("# Pagina ")]
                more = " ..." if len(heads) > 8 else ""
                print(f"    header pagina nel content: {heads[:8]}{more}")
    print(f"\nTotale segmenti (~ chunk OWUI) che verrebbero importati: {total_segments}")
    return 0


def import_one(client: OwuiClient, coll_id: str, pdf: Path,
               existing_hashes: set[str], force: bool = False) -> str:
    """Pipeline su un singolo PDF. Ritorna 'OK (...)' | 'SKIP (...)' | 'ERR (...)'.

    PRE-CHECK (PRE-embed): se lo sha256 del file corrisponde a un file gia' nella KB,
    salta SENZA upload/process/embed (risparmia embeddings + evita chunk orfani file-<id>).
    `force=True` bypassa il pre-check. Errori per-file non abortiscono il batch."""
    fh = file_sha256(pdf)
    if not force and fh in existing_hashes:
        return f"SKIP (file_hash {fh[:8]} gia' presente - pre-check pre-embed)"

    pages = extract_pages(pdf)
    if not pages:
        return "ERR (nessun testo estraibile - serve OCR?)"
    content = build_page_content(pages)
    file_id: str | None = None
    try:
        file_id = client.upload_file(pdf)
        client.process_file(file_id, content)
        res = client.add_file_to_knowledge(coll_id, file_id)
        if res.status == "added":
            existing_hashes.add(fh)   # cosi' un duplicato nello stesso batch salta al volo
            return f"OK ({len(pages)} pagine, {count_segments(pages)} chunk)"
        if res.status == "duplicate":
            client.delete_file(file_id)
            return "SKIP (contenuto gia' presente - dedup nativo OWUI post-embed)"
        client.delete_file(file_id)
        return f"ERR (add: {res.detail})"
    except OwuiError as e:
        if file_id:
            client.delete_file(file_id)
        return f"ERR ({e})"


def run_import(collections: dict, scope: str, force: bool = False) -> int:
    try:
        client = OwuiClient.from_env()
    except OwuiError as e:
        print(f"ERR login OWUI: {e}", file=sys.stderr)
        return 1
    print(f"Login OK ({client.base_url}) | scope={scope} | force={force}")

    for coll, folder in collections.items():
        pdfs = sorted(Path(folder).glob("*.pdf"))
        if not pdfs:
            print(f"\n[{coll}] nessun PDF, salto.")
            continue
        coll_id = client.get_or_create_collection(coll)
        client.set_collection_access(coll_id, scope)
        # pre-check: hash dei file gia' nella KB (1 chiamata per collection, non per file)
        existing = {f.get("meta", {}).get("file_hash")
                    for f in client.list_kb_files(coll_id)
                    if f.get("meta", {}).get("file_hash")}
        print(f"\n[{coll}] collection {coll_id} | access={scope} | {len(pdfs)} PDF | {len(existing)} file gia' in KB")
        for pdf in pdfs:
            print(f"  {pdf.name}: {import_one(client, coll_id, pdf, existing, force)}")
    print("\nFatto!")
    return 0


def main() -> int:
    args = parse_args()
    collections = select_collections(args.collections)
    if args.dry_run:
        return dry_run(collections)
    return run_import(collections, args.scope, args.force)


if __name__ == "__main__":
    sys.exit(main())
