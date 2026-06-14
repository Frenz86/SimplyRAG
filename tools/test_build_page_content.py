"""test_build_page_content — test unitario deterministico (livello T).

Verifica le garanzie di build_page_content (SOP S4/S7). Puro: niente rete, niente PDF,
niente OWUI. Usa uno stub duck-typed di Page (non importa extract_pages/pdfplumber).

Uso:  python tools/test_build_page_content.py
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_page_content import build_page_content, count_segments, MAX_SEGMENT_CHARS  # noqa: E402


class _Pg:
    """Stub duck-typed di Page: basta .page (int) e .text (str)."""
    def __init__(self, page: int, text: str):
        self.page = page
        self.text = text


def _segments(content: str) -> list[str]:
    # segmenti delimitati dall'header "# Pagina N" (NON da \n\n: \n\n separa anche header<->corpo)
    if not content.strip():
        return []
    return re.split(r"\n\n(?=# Pagina )", content)


def test_empty():
    assert build_page_content([]) == ""
    assert count_segments([]) == 0
    print("PASS test_empty")


def test_every_segment_has_page_header():
    content = build_page_content([_Pg(1, "testo pagina uno"), _Pg(2, "testo pagina due")])
    for seg in _segments(content):
        assert seg.startswith("# Pagina "), f"segmento senza header: {seg[:40]!r}"
    print("PASS test_every_segment_has_page_header")


def test_correct_page_numbers():
    content = build_page_content([_Pg(3, "terza"), _Pg(7, "settima")])
    assert "# Pagina 3" in content
    assert "# Pagina 7" in content
    print("PASS test_correct_page_numbers")


def test_segment_body_under_limit():
    # paragrafo enorme: nessun corpo di segmento eccede il limit
    big = "a " * 5000  # ~10000 char
    content = build_page_content([_Pg(1, big)], limit=1000)
    for seg in _segments(content):
        body = seg.split("\n\n", 1)[1] if "\n\n" in seg else seg
        assert len(body) <= 1000, f"corpo segmento > limit: {len(body)}"
    assert count_segments([_Pg(1, big)], limit=1000) >= 1
    print("PASS test_segment_body_under_limit")


def test_multi_segment_page_keeps_same_page():
    # una pagina che produce piu' segmenti: tutti riportano la STESSA pagina
    pages = [_Pg(5, "\n\n".join(f"paragrafo {i} " * 50 for i in range(20)))]
    content = build_page_content(pages, limit=500)
    segs = _segments(content)
    assert len(segs) > 1, "attesi piu' segmenti per una pagina densa"
    for seg in segs:
        assert seg.startswith("# Pagina 5"), f"segmento senza pagina 5: {seg[:30]!r}"
    print("PASS test_multi_segment_page_keeps_same_page")


def test_non_contiguous_pages_preserved():
    # extract_pages salta le pagine vuote -> qui simuliamo indici non contigui
    content = build_page_content([_Pg(1, "a"), _Pg(3, "b")])
    assert "# Pagina 1" in content and "# Pagina 3" in content
    assert "# Pagina 2" not in content
    print("PASS test_non_contiguous_pages_preserved")


if __name__ == "__main__":
    test_empty()
    test_every_segment_has_page_header()
    test_correct_page_numbers()
    test_segment_body_under_limit()
    test_multi_segment_page_keeps_same_page()
    test_non_contiguous_pages_preserved()
    print("\nTUTTI I TEST build_page_content PASS")
