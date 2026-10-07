import re
from pathlib import Path


def test_html_uses_linked_assets_and_semantic_landmarks():
    html = Path("frontend/index.html").read_text()
    assert "<style" not in html
    assert not re.search(r"<script(?![^>]*src=)", html)
    assert "<main" in html and "<nav" in html
    assert 'type="module"' in html


def test_all_rectangular_styles_are_square():
    css = Path("frontend/style.css").read_text()
    radii = re.findall(r"border-radius\s*:\s*([^;]+)", css)
    assert radii and all(value.strip() == "0" for value in radii)
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css


def test_user_data_is_never_interpolated_as_html():
    files = list(Path("frontend/js").glob("*.js"))
    assert files
    for path in files:
        text = path.read_text()
        assert ".innerHTML" not in text
        assert "Math.random" not in text
    assert "textContent" in Path("frontend/js/utils.js").read_text()


def test_dashboard_has_evidence_filters_and_accessible_upload():
    html = Path("frontend/index.html").read_text()
    for marker in [
        'id="file-input"',
        'id="clause-search"',
        'id="severity-filter"',
        'id="method-filter"',
        'aria-live="polite"',
        'id="analysis-view"',
        'id="history-view"',
    ]:
        assert marker in html


def test_delete_flow_captures_immutable_target_before_await():
    source = Path("frontend/js/app.js").read_text()
    assert "const target = deletion;" in source
    assert "await api.remove(target.document_id);" in source
    assert "lastAnalysis?.document_id === target.document_id" in source
