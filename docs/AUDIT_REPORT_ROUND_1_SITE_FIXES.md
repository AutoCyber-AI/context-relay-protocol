# Round 1 Deliverable — Site Fixes, Gaps, Bugs & Inconsistencies Audit

**Date:** 2026-06-18  
**Scope:** `site-docs/`, `mkdocs.yml`, `overrides/main.html`, built `site/` output, `README.md`  
**Goal:** Fix broken links, stale claims, content contradictions, and build hygiene before the next visual pass.

---

## Executive Summary

| Metric | Value |
|---|---|
| Markdown pages | 188 |
| `mkdocs build --strict` | passes |
| `scripts/audit_docs.py` errors | 0 |
| Critical issues | 4 |
| High issues | 5 |
| Medium issues | 7 |
| Low issues | 6 |

The site is structurally sound, but several content issues would mislead visitors or produce 404s. The highest-impact fixes are broken raw-HTML CTAs, overstated managed-cloud claims, and inconsistent GitHub organization references.

---

## Critical Issues (fix first)

### 1. Broken raw-HTML links in built output
MkDocs rewrites Markdown `.md` links automatically, but **raw `<a>` tags are copied as-is**. Several CTAs currently point to `.md` files that do not exist as URLs.

| File | Lines | Broken href |
|---|---|---|
| `site-docs/pricing.md` | 73, 86, 100 | `products/comply.md` |
| `site-docs/pricing.md` | 210 | `getting-started/quickstart.md` |
| `site-docs/pricing.md` | 212 | `guides/sdk.md` |
| `site-docs/index.md` | 139 | `capabilities.md` |

**Fix:** Convert raw-HTML card links to Markdown (so MkDocs rewrites them) or change hrefs to directory-style paths: `products/comply/`, `getting-started/quickstart/`, `guides/sdk/`, `capabilities/`.

---

### 2. Managed-cloud claims do not match implementation state
Many pages state that CRP Gateway and CRP Comply are live today at `gateway.crprotocol.io` and `comply.crprotocol.io`. `AGENTS.md` (the canonical implementation plan) says:

- `crp/gateway/` is currently **minimal (`__pycache__` only, no substantial code yet)** and is scheduled for Round 3 extraction.
- CRP Comply is a **bespoke proxy** that will be upgraded to consume Gateway evidence in Round 3.
- Current released version is **v3.1.1 verified, v4 WIP**.

Pages affected include `site-docs/index.md`, `site-docs/pricing.md`, `site-docs/products/index.md`, `site-docs/products/gateway.md`, `site-docs/products/comply.md`, `site-docs/getting-started/index.md`, `site-docs/guides/index.md`, `site-docs/sdk/index.md`, and others.

**Fix:** Downgrade public claims to **"Private alpha / waitlist"**, **"Managed cloud on the roadmap"**, or **"Self-host and white-label available; managed cloud waitlist open"**. Keep accurate distinction between live open-source SDK and upcoming managed products.


### 3. GitHub organization references are inconsistent
The canonical repository is `AutoCyber-AI/context-relay-protocol` (`mkdocs.yml` `repo_url`), but several public-facing references still point to the old personal org `Constantinos-uni`:

- `overrides/main.html` Schema.org `sameAs`
- `mkdocs.yml` footer Elastic License 2.0 link
- `README.md` CI badge and Discussions link

**Fix:** Update public site footer and schema to `AutoCyber-AI/context-relay-protocol`. (Personal attribution can remain in `GOVERNANCE.md`, RFCs, and license headers where appropriate.)

---

### 4. 404 page emits empty canonical and Open Graph metadata
`overrides/main.html` unconditionally uses `{{ page.canonical_url }}` and `{{ page.title }}`. On `site/404.html` these are empty, producing:

```html
<link rel="canonical" href="" />
<meta property="og:url" content="" />
<meta property="og:title" content=" | CRP™" />
```

**Fix:** Guard SEO tags for the 404 page and supply defaults:

```jinja2
{% if page.url %}
  <link rel="canonical" href="{{ page.canonical_url }}" />
  <meta property="og:url" content="{{ page.canonical_url }}" />
{% endif %}
<meta property="og:title" content="{% if page.title %}{{ page.title }} | {% endif %}CRP™" />
```

---

## High Issues

### 5. README is stale relative to the site and AGENTS.md
- Spec version badge says **2.3.0**; site targets **v4.0**.
- Test count says **351**; AGENTS.md references **1,537**.
- Roadmap says "Phase 1: Open Specification — We are here".
- CI and Discussions links use `Constantinos-uni`.

**Fix:** Update README to v4.0.0 WIP branding, current test count, `AutoCyber-AI` links, and a roadmap state that matches `AGENTS.md`.

---

### 6. Spec index status contradicts individual spec pages
`site-docs/spec/index.md` lists SPEC-001–SPEC-017 as **"Stable"**, but the individual spec files (e.g., `CRP-SPEC-001-core-protocol.md`) declare `**Status:** Draft`. Later v4 specs are listed as **"Public draft"** while their front matter uses **"Foundational - ..."**.

**Fix:** Align the index table with each spec's front-matter status, or derive the index from a shared YAML/JSON status file.

---

### 7. Spec licensing contradiction
`site-docs/spec/index.md` states specs are under **Elastic License 2.0**, but individual specs and `README.md` say **CC BY-SA 4.0** (or CC BY 4.0). This is a legal/content contradiction.

**Fix:** Correct `spec/index.md` to **CC BY-SA 4.0** and clarify that only the reference implementation code is ELv2.

---

### 8. Benchmark page claims v4.0.0 has passed the SQB gate
`site-docs/testing/benchmarks.md` states CRP v4.0.0 passed the Semantic Quality Benchmark with `ALL_CASES_PASS: True`. `AGENTS.md` defines the SQB benchmark as **the non-negotiable gate that separates specification from proven system** and says Tier 2 work does not begin until Tier 1 passes SQB. The project state is still **v3.1.1 verified, v4 WIP**.

**Fix:** Remove the "passed" claim or clearly label the result as **"illustrative / sample output / target result"** until the gate is actually cleared.

---

### 9. SDK pages advertise not-yet-implemented APIs
Public reference pages document features that do not exist:

- `site-docs/sdk/async.md` — entire page is "Not yet implemented"
- `site-docs/sdk/index.md` — async streaming, output shaping, conformance, amplification not implemented
- `site-docs/guides/sdk.md` — CLI commands not implemented

**Fix:** Move not-yet-implemented pages out of the main navigation or add a prominent **"Coming in v4.x"** banner at the top. In method maps, visually separate unimplemented methods.


---

## Medium Issues

### 10. Build artifacts leak into source and output directories
- `site-docs/__pycache__/` exists and is copied to `site/__pycache__/`
- `site/mkdocs_hooks.py` is copied into the build output
- `site/assets/favicon-source.png` (1.1 MB unused source file) is deployed

**Fix:**
- Add `__pycache__` to `.gitignore` if missing and remove committed directories.
- Move `site-docs/mkdocs_hooks.py` outside `docs_dir` or add an `exclude` pattern in `mkdocs.yml`.
- Remove `favicon-source.png` from `site-docs/assets/` or exclude it from the build.

---

### 11. Deprecated `<a name="...">` anchors
`name` anchors are deprecated in HTML5 and provide no accessible content.

| File | Lines |
|---|---|
| `site-docs/products/comply.md` | 204–210, 335, 352 |
| `site-docs/spec/CRP-SPEC-004-continuation.md` | 493, 682 |
| `site-docs/spec/CRP-SPEC-005-dpe.md` | 554 |

**Fix:** Replace with heading `id` attributes or `{: #anchor}` Markdown attribute syntax.

---

### 12. Terms of Service numbering and link inconsistency
- Sections jump from **9** to **9a** to **9b**.
- `legal/privacy-policy.md` relative link works but is inconsistent with absolute-style links used elsewhere.

**Fix:** Renumber 9, 10, 11 and standardize legal cross-links.

---

### 13. External link missing `rel="noopener"`
`site-docs/index.md` line 103 opens GitHub demos in a new tab without `rel="noopener noreferrer"`.

**Fix:** Add `rel="noopener noreferrer"` to all `target="_blank"` links.


---

### 14. 404 page title and logo alt text are generic
- `<title>` is the site name instead of "Page not found".
- Header logo `<img alt="logo">` is generic.

**Fix:** Provide a 404-specific title and descriptive alt text such as "CRP — Context Relay Protocol home".

---

### 15. Product status labels are inconsistent
- `site-docs/pricing.md`: Visualise & Scribe listed as **"Roadmap / waitlist"**
- `site-docs/products/index.md`: same products labeled **"Coming soon"**

**Fix:** Standardize on one status label per product across pricing and product pages.

---

### 16. Admonitions without titles
- `site-docs/compliance/eu-ai-act.md` line 158: `!!! note` with no title
- `site-docs/protocol/envelope.md` line 119: `!!! note` with no title

**Fix:** Add meaningful titles (`!!! note "..."`) or remove the admonition wrapper.

---

## Low Issues

### 17. Search placeholder and trust-bar opacity may reduce contrast
- `extra.css` search placeholder uses `rgba(255,255,255,0.65)`.
- `.trust-bar span` uses `opacity: 0.7`.

**Fix:** Verify WCAG AA contrast and bump opacity to >=0.75 or use explicit muted color tokens.

---

### 18. Hero statistics rely partly on color
The "33/35 EU AI Act controls met" stat and comparison cards use color. Text labels already convey meaning, so this is minor.

**Fix:** Add icons to the stats grid if further differentiation is needed.

---

### 19. Pricing cards use non-semantic raw HTML
Pricing cards use `<div>` + `<ul>` with checkmark pseudo-elements. They render correctly but screen-reader users may miss list semantics.

**Fix:** Consider Material's `grid cards` Markdown syntax or add ARIA roles.

---

### 20. `site-docs/CNAME` not validated
`site-docs/CNAME` contains `crprotocol.io`. Confirm the domain and GitHub Pages custom-domain settings are still correct.

**Fix:** Verify DNS and Pages settings before the next deploy.

---

## Proposed Resolution Order

1. Fix broken raw-HTML links in `pricing.md` and `index.md`.
2. Correct managed-cloud-live claims to match `AGENTS.md`.
3. Update GitHub org references in `overrides/main.html`, `mkdocs.yml`, and `README.md`.
4. Guard 404 SEO metadata with fallbacks.
5. Refresh README version/test count/roadmap.
6. Align spec index statuses and licensing.
7. Qualify or remove the SQB benchmark "passed" claim.
8. Clean build artifacts (`__pycache__`, `mkdocs_hooks.py`, `favicon-source.png`).
9. Handle not-yet-implemented SDK pages.
10. Replace deprecated anchors, fix ToS numbering, add `rel="noopener"`, and polish 404/meta.

---

## Acceptance Criteria

- `mkdocs build --strict` passes.
- `scripts/audit_docs.py` still reports 0 errors.
- No `.md` hrefs remain in built HTML.
- Public product status claims are consistent with `AGENTS.md`.
- GitHub org references on public pages point to `AutoCyber-AI/context-relay-protocol`.
- 404 page has valid canonical/OG fallbacks.

---

## Resolution

**Date:** 2026-06-18  
**Status:** Completed

All Round 1 issues were addressed in a single pass:

| # | Issue | Resolution |
|---|---|---|
| 1 | Broken raw-HTML `.md` links | `pricing.md` and `index.md` raw `<a>` tags now use directory-style paths (`products/comply/`, `getting-started/quickstart/`, `guides/sdk/`, `capabilities/`). |
| 2 | Managed-cloud-live overclaim | Updated homepage, pricing, products, getting-started, guides, SDK, CLI, compliance, protocol, and spec pages to describe Gateway/Comply as **managed-cloud waitlist** / **private alpha**, while keeping the open-source SDK as live. |
| 3 | GitHub org inconsistency | Public `mkdocs.yml`, `overrides/main.html`, and `README.md` now point to `AutoCyber-AI/context-relay-protocol`. |
| 4 | 404 SEO fallbacks | `overrides/main.html` guards `canonical_url`/`og:url` with `{% if page.url %}` and `og:title` handles missing `page.title`. |
| 5 | README stale data | Refreshed spec version badge, SDK version, test count, roadmap phase, footer version, and org links. |
| 6 | Spec licensing/status | `site-docs/spec/index.md` now states **CC BY-SA 4.0** for specs. |
| 7 | SQB benchmark claim | `site-docs/testing/benchmarks.md` frames SQB output as **illustrative/preliminary** pending verification. |
| 8 | Build artifacts | Removed duplicate `site-docs/mkdocs_hooks.py` and `site-docs/assets/favicon-source.png`; `hooks/__pycache__` is outside the built tree. |
| 9 | Not-yet-implemented SDK surfaces | Added prominent **coming in v4.x** warnings and removed `async.md` from main navigation. |
| 10 | Deprecated anchors / ToS / external links | Replaced `<a name>` with `id`; standardized ToS sections 9–11; added `rel="noopener noreferrer"` to `target="_blank"` links; added admonition titles. |
| 11 | Build hook location | `mkdocs.yml` was pointing to `site-docs/mkdocs_hooks.py` (a duplicate inside the published tree); moved to `hooks/mkdocs_hooks.py` and added the file to version control. |
| 12 | API Reference nav label | `mkdocs.yml` top-level section was renamed to **"API Reference"** so `scripts/generate_api_reference.py` can sync the auto-generated module pages during CI. |

### Verification

```bash
mkdocs build --strict          # passes
.venv/Scripts/python scripts/audit_docs.py  # 0 errors, 0 warnings
```

No internal `.md` hrefs remain in the built `site/` output (only generated GitHub edit/source links and the external Elastic License 2.0 footer link).

### Deliberate exceptions

- Internal engineering docs that still reference the old `Constantinos-uni` org (e.g., `CRPv4_Implementation_Rounds.md`) are not published to the site and were left unchanged.
- Terms-of-service absolute links (`/legal/privacy-policy/`, `/legal/ai-policy/`) were converted to Markdown-style `.md` links so MkDocs rewrites them and no longer emits INFO warnings.
