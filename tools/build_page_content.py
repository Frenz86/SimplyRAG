"""build_page_content — Tool atomico (livello T).

Costruisce la stringa `content` page-preserving da passare a /retrieval/process/file.
Ogni segmento (<= MAX_SEGMENT_CHARS) e' prefissato con l'header markdown "# Pagina {N}",
cosi' con ENABLE_MARKDOWN_HEADER_TEXT_SPLITTER ogni chunk sta in una sola pagina e porta
il numero di pagina nel proprio testo (invariante I3/I4). vedi SOP.md S4.

Puro, deterministico, NESSUNA rete. Duck-typed: `pages` e' un iterable di oggetti con
attributi `.page` (int>=1) e `.text` (str) -> testabile senza importare extract_pages.

Garanzie (verificate da test_build_page_content.py):
- ogni segmento inizia con "# Pagina {N}";
- nessun segmento eccede MAX_SEGMENT_CHARS (corpo);
- ogni pagina con testo produce >= 1 segmento.
"""
from __future__ import annotations

MAX_SEGMENT_CHARS = 3500  # ~900 token, margine ampio su CHUNK_SIZE=1500 token di OWUI


def _chunk_text(text: str, limit: int) -> list[str]:
    """Spezza text in segmenti <= limit caratteri, preferendo i confini di paragrafo.

    - raggruppa paragrafi (split su "\\n\\n") finche' restano <= limit;
    - un paragrafo piu' lungo di limit viene tagliato duro (raro: pagina densa senza a-capo).
    Deterministico: nessuna randomicita'.
    """
    out: list[str] = []
    buf = ""
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if len(para) > limit:
            if buf:
                out.append(buf)
                buf = ""
            for j in range(0, len(para), limit):
                out.append(para[j:j + limit])
            continue
        if buf and len(buf) + 2 + len(para) > limit:
            out.append(buf)
            buf = para
        else:
            buf = (buf + "\n\n" + para) if buf else para
    if buf:
        out.append(buf)
    return out


def build_page_content(pages, limit: int = MAX_SEGMENT_CHARS) -> str:
    """pages: iterable di {.page:int, .text:str} -> stringa con segmenti "# Pagina N\\n\\n<testo>\"."""
    segments: list[str] = []
    for pg in pages:
        for seg in _chunk_text(pg.text, limit):
            segments.append(f"# Pagina {pg.page}\n\n{seg}")
    return "\n\n".join(segments)


def count_segments(pages, limit: int = MAX_SEGMENT_CHARS) -> int:
    """Numero totale di segmenti che verrebbero generati (1 segmento ~= 1 chunk OWUI)."""
    return sum(len(_chunk_text(pg.text, limit)) for pg in pages)


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from extract_pages import extract_pages  # import dal modulo fratello (per il demo)

    if len(sys.argv) != 2:
        print("uso: python tools/build_page_content.py <file.pdf>")
        sys.exit(2)
    pp = extract_pages(Path(sys.argv[1]))
    content = build_page_content(pp)
    print(f"Pagine con testo: {len(pp)} | segmenti: {count_segments(pp)} | content: {len(content)} char")
    print("--- primi 500 char del content ---")
    print(content[:500])
