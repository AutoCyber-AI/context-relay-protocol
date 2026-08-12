# CRP Public Docs Quality Strategy

> How we keep `crprotocol.io` accurate, safe, and well-formatted as the site grows.

## Purpose

The public docs site is the primary conversion surface for CRP. Every page must:

1. **Build cleanly** with `mkdocs build --strict`.
2. **Contain no internal secrets** (env vars, live payment IDs, Clerk/Stripe wiring, confidential strategy).
3. **Render correctly** on desktop and mobile (no unclosed HTML, broken tables, malformed admonitions).
4. **Stay consistent** with the live product state (managed cloud availability, pricing, white-label offers).

This document defines the automated and manual checks that enforce those properties.

---

## Quality gates

### Gate 1 - Automated build

Run on every PR and before any manual deploy:

```bash
.venv/Scripts/python -m mkdocs build --strict
```

`--strict` turns MkDocs warnings into errors. A clean exit is required before merge.

### Gate 2 - Automated audit

Run the custom audit script after content changes:

```bash
.venv/Scripts/python scripts/audit_docs.py
```

The script runs Gate 1 first, then checks every `site-docs/*.md` file for:

| Check | Severity | What it catches |
|-------|----------|-----------------|
| `unclosed_fence` | **ERROR** | Code blocks that never close |
| `html_imbalance` | **ERROR** | Unclosed `<div>` or `<details>` tags |
| `table_cols` | **ERROR** | Markdown tables with inconsistent column counts |
| `dead_ref` | **ERROR** | Links to removed files (e.g. deleted env-var checklist) |
| `confidential` | **ERROR** | `CONFIDENTIAL` or `Internal Strategy` still exposed on the public site |
| `malformed_admonition` | WARN | Admonitions with missing or unindented body |
| `inline_style` | WARN | Pages with excessive inline `style=` attributes |
| `managed_status` | WARN | Live managed-cloud endpoints still marked "coming soon" |

**Policy:** PRs must fix all ERROR findings. WARN findings are triaged; obvious regressions are fixed before merge.

### Gate 3 - Link check

Use a link checker against the generated `site/` directory before deploy:

```bash
# Example using htmlproofer (not currently installed)
htmlproofer site/ --disable-external
```

For now, rely on `mkdocs build --strict` for internal links and manually review high-traffic pages.

### Gate 4 - Visual / manual review

For any change that touches marketing-facing pages, open the local build in a browser:

```bash
.venv/Scripts/python -m mkdocs serve
```

Review on desktop and mobile widths. Pay special attention to the pages listed below.

---

## Manual review checklist

Use this checklist when editing or reviewing any docs page.

### Content accuracy

- [ ] Product availability matches reality (managed cloud live for Gateway/Comply; roadmap-only for Visualise/Scribe).
- [ ] Pricing and plan names match the public pricing page.
- [ ] No live API keys, payment IDs, account IDs, or secrets placeholders.
- [ ] No internal repo paths, env-var names, or third-party dashboard details.
- [ ] No `CONFIDENTIAL` or internal strategy language on public pages.

### Markdown / Material formatting

- [ ] Admonitions (`!!! type "Title"`) are followed by 4-space-indented body lines.
- [ ] Grid cards (`<div class="grid cards" markdown>`) close properly and contain the `markdown` attribute.
- [ ] Custom `<div>` blocks (heroes, product grids, pricing grids) are balanced.
- [ ] Tables have the same number of columns in every data row.
- [ ] Code fences include a language tag and are closed.
- [ ] Em dashes (`—`) have been replaced with hyphens to avoid encoding issues.
- [ ] No duplicate adjacent buttons or links.

### Navigation

- [ ] New pages are added to `nav:` in `mkdocs.yml`.
- [ ] High-conversion pages (Products, Pricing, Getting Started) appear early in the top-level nav.
- [ ] Section ordering follows the reader's journey, not the repo layout.

### High-traffic pages to review after every visual or pricing change

- `site-docs/index.md`
- `site-docs/pricing.md`
- `site-docs/products/index.md`
- `site-docs/products/gateway.md`
- `site-docs/products/comply.md`
- `site-docs/products/scan.md`
- `site-docs/getting-started/quickstart.md`
- `site-docs/getting-started/index.md`
- `site-docs/guides/sdk.md`
- `site-docs/capabilities.md`
- `site-docs/why-crp.md`
- `site-docs/who-is-it-for.md`

---

## Issue triage

| Severity | Example | Action |
|----------|---------|--------|
| **Blocker** | Unclosed fence, broken table, exposed Stripe account ID | Fix before merge |
| **High** | Outdated managed-cloud status, dead internal link | Fix before merge |
| **Medium** | Inline style clutter, minor admonition indentation | Fix in the same PR or track in docs backlog |
| **Low** | Cosmetic spacing, wording polish | Batch and address in regular docs passes |

---

## Ongoing process

1. **Per-PR:** Author runs `mkdocs build --strict` and `scripts/audit_docs.py`.
2. **Weekly:** A 15-minute docs hygiene pass fixes any new WARN findings and checks the high-traffic pages.
3. **Monthly:** Review nav order against conversion analytics and product releases.
4. **Per-release:** Verify that product-status admonitions, pricing, and availability are still correct.

---

## Tooling

- **Build:** MkDocs Material (`mkdocs build --strict`)
- **Audit:** `scripts/audit_docs.py` (custom)
- **Lint:** Ruff is configured for Python source; docs Markdown is not currently linted beyond the audit script.
- **CI:** `.github/workflows/docs.yml` deploys on `main`; add the audit script as a separate job when ready.

---

## Latest audit result

Run after the proprietary-cleanup and formatting pass:

```
Total: 0 errors, 1 warnings across 1 files
  site-docs/index.md - 31 inline style attributes
```

The single remaining warning is acceptable: the home page intentionally uses a small set of utility inline styles for hero layout. These can be migrated to CSS classes in a future visual-refactor pass.
