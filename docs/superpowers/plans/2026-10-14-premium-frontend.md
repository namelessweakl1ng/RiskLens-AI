# RiskLens Premium Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the existing RiskLens vanilla frontend into a polished, responsive light fintech dashboard while retaining real API data and existing analysis behavior.

**Architecture:** Keep the FastAPI-served semantic HTML and native ES modules. Refresh the existing stylesheet and small shell/upload interactions; preserve API, scoring, database, and rendering safety contracts.

**Tech Stack:** HTML, CSS, native JavaScript modules, FastAPI static assets, pytest and Playwright where installed.

**Spec:** `docs/superpowers/specs/2026-10-07-risklens-design.md` plus the uploaded RiskLens AI frontend transformation prompt.

## Global Constraints

- Preserve the backend and canonical `AnalysisResult` contract.
- Use actual API values; do not add mock production data or fabricated confidence.
- Keep user content rendered through text nodes and `textContent`.
- Keep the 20 MiB PDF limit and privacy disclosure accurate.
- Respect keyboard focus, reduced motion, and small mobile widths.

## Review Focus

- A long filename must wrap without horizontal overflow.
- A cleared file must also clear the native input value and preview.
- Mobile navigation must expose its expanded state and remain keyboard operable.
- Existing analysis and history data must continue to render safely.
- Reduced-motion users must not receive forced transitions or score animation.

---

### Task 1: Premium visual system and application shell

**Files:**
- Modify: `frontend/style.css`
- Modify: `frontend/index.html`
- Modify: `tests/test_frontend.py`

**Interfaces:**
- Consumes: Existing HTML classes and API-backed render targets.
- Produces: Warm light theme, emerald accents, rounded surfaces, and compact responsive navigation shell.

- [ ] Replace visual assertions with palette, radius, focus, and reduced-motion checks.
- [ ] Add an accessible mobile navigation toggle and label existing navigation.
- [ ] Apply a cohesive responsive style system while preserving all existing component selectors.
- [ ] Run frontend static assertions and browser regression checks where available.

### Task 2: File selection and documentation

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/js/app.js`
- Modify: `README.md`
- Create: `docs/FRONTEND.md`
- Modify: `tests/test_frontend.py`

**Interfaces:**
- Consumes: Existing `select(file)` state and `/api/analyze` endpoint.
- Produces: Safe filename and byte-size preview, clear/replace action, and mobile navigation toggle behavior.

- [ ] Add tests for accessible preview and clear controls.
- [ ] Render selected file metadata with text nodes and clear both application and input state.
- [ ] Implement navigation toggle, Escape handling, and close-on-route-selection behavior.
- [ ] Document visual tokens, component organization, accurate privacy/model limitations, and browser verification.
- [ ] Run requested syntax, unit, and browser checks; review the complete diff.
