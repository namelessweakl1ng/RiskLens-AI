import re
from pathlib import Path


def test_html_uses_linked_assets_and_semantic_landmarks():
    html = Path("frontend/index.html").read_text()
    assert "<style" not in html
    assert not re.search(r"<script(?![^>]*src=)", html)
    assert "<main" in html and "<nav" in html
    assert 'type="module"' in html


def test_fintech_visual_tokens_and_accessibility_motion():
    css = Path("frontend/style.css").read_text()
    assert "--bg: #f8faf9" in css.lower()
    assert "--accent: #059669" in css.lower()
    assert re.search(r"--radius-(?:card|control):\s*1[246]px", css)
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css


def test_mobile_navigation_and_file_preview_controls_are_accessible():
    html = Path("frontend/index.html").read_text()
    for marker in [
        'id="mobile-menu-button"',
        'aria-controls="workspace-navigation"',
        'id="workspace-navigation"',
        'id="selected-file"',
        'id="remove-file"',
    ]:
        assert marker in html
    source = Path("frontend/js/app.js").read_text()
    assert 'addEventListener("click", toggleNavigation)' in source
    assert 'addEventListener("click", clearSelectedFile)' in source


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
