# Frontend design and verification

RiskLens uses the FastAPI-served semantic HTML shell and native JavaScript modules in `frontend/`. It has no separate frontend build and introduces no UI dependency. The page shell, API client, analysis renderer, utility functions, and SVG chart helpers remain separated by responsibility.

## Visual conventions

The interface uses a warm off-white canvas (`#F8FAF9`), white cards, charcoal text, slate secondary text, emerald actions (`#059669` / `#047857`), and restrained red, orange, and amber severity colors. CSS custom properties in `frontend/style.css` centralize the palette, typography, radii, elevation, and common motion. Cards use 16px corners; controls use 12px corners. Focus indicators remain visible, and transitions honor `prefers-reduced-motion`.

At desktop widths the workspace has a persistent left navigation and aligned top bar. At narrow widths the navigation becomes an off-canvas menu controlled by a button with an updated accessible name and `aria-expanded` state. Document tables remain horizontally scrollable inside their panel; the page itself is designed to avoid horizontal overflow.

The upload selection preview reports the actual file name and byte size. It uses text nodes, and the remove action clears both selected-file state and the native file input. Upload size and server-side extraction limits remain authoritative. Uploaded PDF bytes are discarded after analysis; extracted text and results are stored locally in SQLite.

## Data and trust

Dashboard counts, distributions, risk scores, findings, timestamps, and history rows come from the API. The risk gauge displays the canonical score without recomputing it. The score is a heuristic triage measure, not a calibrated loss probability. No trained RiskLens-specific classifier ships by default, so rule-only analysis is clearly identified when the API reports the classifier unavailable. Historical analyses remain marked unverified.

User-controlled filenames, clause text, evidence and recommendations are rendered through DOM text nodes or `textContent`; do not replace these patterns with HTML string interpolation. No original-PDF preview, OCR, external AI chat, or notification service is implied by the interface.

## Verification

Run from the repository root:

```bash
python -m pytest
python -m ruff check backend training_pipeline tests
python -m ruff format --check backend training_pipeline tests
for file in frontend/js/*.js tests/*.cjs; do node --check "$file" || exit 1; done
```

When Playwright and Chromium are installed, start the FastAPI app and run `node tests/browser-regressions.cjs` to cover long filename layout, uncertainty labels, and out-of-order history pagination at mobile and desktop widths. The broader browser script in `tests/browser.cjs` covers upload, dashboard, analysis, filters, and deletion. Review the empty workspace at 390px and 1440px widths and check analysis/history at both sizes. This repository does not currently include screenshot artifacts in version control.
