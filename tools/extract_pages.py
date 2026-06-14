"""extract_pages — Tool atomico (livello T della triade A.N.T.).

Estrae il testo per-pagina da un PDF: 1-based, salta le pagine vuote.
Puro, deterministico, NESSUNA rete. Soddisfa l'invariante I4 (page preservata in estrazione).

Input tipizzato -> output tipizzato: Path(pdf) -> list[Page], con Page(page:int>=1, text:str).

Uso:
    from extract_pages import extract_pages, page_count   # se importato da tools/
    pages = extract_pages(Path("doc.pdf"))

CLI:  python tools/extract_pages.py <file.pdf>
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import pdfplumber


@dataclass(frozen=True)
class Page:
    page: int   # 1-based
    text: str   # non vuoto, gia' stripped


def _index_pages(raw_texts: list[str]) -> list[Page]:
    """Pura: mappa i testi grezzi (in ordine di pagina) a Page 1-based, saltando i vuoti."""
    pages: list[Page] = []
    for i, raw in enumerate(raw_texts, start=1):
        t = (raw or "").strip()
        if t:
            pages.append(Page(page=i, text=t))
    return pages


def extract_pages(pdf_path: Path) -> list[Page]:
    """Apre il PDF e restituisce una Page per ogni pagina con testo estrai bile."""
    with pdfplumber.open(str(pdf_path)) as doc:
        raw = [p.extract_text() or "" for p in doc.pages]
    return _index_pages(raw)


def page_count(pdf_path: Path) -> int:
    """Numero di pagine fisiche del PDF (per validare I3: page <= page_count)."""
    with pdfplumber.open(str(pdf_path)) as doc:
        return len(doc.pages)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("uso: python tools/extract_pages.py <file.pdf>")
        sys.exit(2)
    path = Path(sys.argv[1])
    pp = extract_pages(path)
    total = page_count(path)
    print(f"Pagine totali: {total} | con testo: {len(pp)}")
    for p in pp:
        preview = p.text[:60].replace("\n", " ")
        print(f"  p.{p.page}: {len(p.text)} char | {preview}...")
