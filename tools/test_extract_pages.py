"""test_extract_pages — test unitario (livello T).

Parte PURA (_index_pages): deterministica, niente PDF, niente rete.
Parte STRUTTURALE (extract_pages): smoke test su un PDF reale di pdf/ se presente.

Uso:  python tools/test_extract_pages.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_pages import _index_pages, Page  # noqa: E402


def test_index_skips_empty_and_is_1based():
    # i numeri pagina sono POSIZIONI FISICHE: le pagine vuote non shiftano le successive (I3)
    pages = _index_pages(["pag1", "", "   ", "pag3"])
    assert [p.page for p in pages] == [1, 4]
    assert [p.text for p in pages] == ["pag1", "pag3"]
    print("PASS test_index_skips_empty_and_is_1based")


def test_index_strips_whitespace():
    pages = _index_pages(["  spazi  ", "\t tab \n"])
    assert pages[0].text == "spazi"
    assert pages[1].text == "tab"
    print("PASS test_index_strips_whitespace")


def test_index_all_empty():
    assert _index_pages(["", "  ", ""]) == []
    print("PASS test_index_all_empty")


def test_index_none_safe():
    # pdfplumber puo' restituire None su pagina senza testo
    assert _index_pages([None, "ok"]) == [Page(2, "ok")]
    print("PASS test_index_none_safe")


def test_real_pdf_structure():
    """Smoke test su un PDF reale: 1-based, page <= page_count (I3), testo non vuoto, univoci."""
    from extract_pages import extract_pages, page_count
    roots = [Path("pdf"), Path("../pdf"), Path(__file__).resolve().parent.parent / "pdf"]
    candidates = []
    for root in roots:
        candidates += sorted(root.glob("*/*.pdf"))
    if not candidates:
        print("SKIP test_real_pdf_structure (nessun PDF trovato in pdf/)")
        return
    pdf = candidates[0]
    total = page_count(pdf)
    pages = extract_pages(pdf)
    assert all(1 <= p.page <= total for p in pages), "page fuori range (I3)"
    assert all(p.text.strip() for p in pages), "pagina con testo vuoto"
    nums = [p.page for p in pages]
    assert nums == sorted(nums) and len(nums) == len(set(nums)), "pagine non ordinate/univoche"
    print(f"PASS test_real_pdf_structure ({pdf.name}: {total} pag, {len(pages)} con testo)")


if __name__ == "__main__":
    test_index_skips_empty_and_is_1based()
    test_index_strips_whitespace()
    test_index_all_empty()
    test_index_none_safe()
    test_real_pdf_structure()
    print("\nTUTTI I TEST extract_pages PASS")
