from pathlib import Path


def test_print_background_covers_the_pdf_page():
    css = (Path(__file__).parents[1] / "frontend" / "src" / "index.css").read_text()

    print_styles = css.split("@media print", 1)[1]
    assert "html,\n  body" in print_styles
    assert "background: var(--background)" in print_styles


def test_print_report_keeps_bordered_sections_on_one_page():
    css = (Path(__file__).parents[1] / "frontend" / "src" / "index.css").read_text()

    print_styles = css.split("@media print", 1)[1]
    assert '.export-report [data-slot="card"]' in print_styles
    assert "break-inside: avoid" in print_styles
