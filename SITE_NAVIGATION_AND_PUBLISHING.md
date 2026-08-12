# CRP Site — Navigation Map & Publishing Guide

**Domain:** [crprotocol.io](https://crprotocol.io)
**Engine:** MkDocs Material
**Source:** `site-docs/` directory
**Config:** `mkdocs.yml`
**CNAME:** `crprotocol.io`

---

## 1. Complete Site Navigation Map

```
crprotocol.io
│
├── Home                           → index.md
├── Why CRP?                       → why-crp.md
│
├── Getting Started/
│   ├── Overview                   → getting-started/index.md
│   ├── Installation               → getting-started/installation.md
│   ├── Quick Start                → getting-started/quickstart.md
│   ├── Providers                  → getting-started/providers.md
│   ├── Local Models & LM Studio   → getting-started/local-models.md
│   ├── CLI Reference              → getting-started/cli.md
│   └── Licensing & IP Protection  → getting-started/licensing.md
│
├── Protocol/
│   ├── Overview                   → protocol/index.md
│   ├── Core Protocol              → protocol/core.md
│   ├── Context Envelope           → protocol/envelope.md
│   ├── Dispatch Strategies        → protocol/dispatch-strategies.md
│   ├── Continuation & Stitching   → protocol/continuation.md
│   ├── Extraction Pipeline        → protocol/extraction.md
│   ├── Contextual Knowledge Fabric → protocol/ckf.md
│   ├── Quality Tiers              → protocol/quality-tiers.md
│   ├── Provenance & Hallucination → protocol/provenance.md
│   ├── Meta-Learning              → protocol/meta-learning.md
│   └── Research Foundations       → protocol/research.md
│
├── Guides/
│   ├── Overview                   → guides/index.md
│   ├── Demo App                   → guides/demo-app.md
│   ├── Streaming                  → guides/streaming.md
│   ├── Multi-Turn Conversations   → guides/multi-turn.md
│   ├── Data Ingestion             → guides/ingestion.md
│   ├── Session Persistence        → guides/session-persistence.md
│   └── HTTP Sidecar               → guides/sidecar.md
│
├── Compliance/
│   ├── Overview                   → compliance/index.md
│   ├── EU AI Act                  → compliance/eu-ai-act.md
│   ├── ISO 42001                  → compliance/iso-42001.md
│   ├── GDPR                       → compliance/gdpr.md
│   ├── NIST AI RMF                → compliance/nist-ai-rmf.md
│   └── Security                   → compliance/security.md
│
├── API Reference/
│   ├── Overview                   → api/index.md
│   ├── Client                     → api/client.md
│   ├── Dispatch Methods           → api/dispatch.md
│   ├── Compliance API             → api/compliance.md
│   └── JSON Schemas               → api/schemas.md
│
├── Testing & Benchmarks/
│   ├── Overview                   → testing/index.md
│   ├── Running Tests              → testing/running-tests.md
│   ├── Benchmarks                 → testing/benchmarks.md
│   └── Reproduce Benchmarks       → testing/reproduce.md
│
├── Contributing                   → contributing.md
│
├── Products/
│   ├── Overview                   → products/index.md
│   ├── CRP Comply                 → products/comply.md
│   ├── CRP Comply — AutoCyber AI  → products/comply-autocyber.md
│   └── CRP Scribe                 → products/scribe.md
│
└── Terms of Service               → terms-of-service.md
```

**Total pages:** 48
**All files verified:** Every nav entry resolves to an existing file in `site-docs/`.

### Orphaned Files (not in nav)

| File | Status | Action |
|------|--------|--------|
| `site-docs/benchmarks.md` | Not in nav (separate from `testing/benchmarks.md`) | Review — may be a draft/duplicate. Add to nav or delete. |

---

## 2. Prerequisites

### Install the docs toolchain

```bash
pip install mkdocs-material pymdownx-extensions
```

This installs:
- `mkdocs` — static site generator
- `mkdocs-material` — the Material theme
- `pymdownx-extensions` — admonitions, code highlighting, superfences, tabs, emoji, etc.

### Verify installation

```bash
mkdocs --version
# Expected: mkdocs, version 1.6.x
```

---

## 3. Local Development

### Serve locally (live reload)

```bash
cd c:\Users\User\Desktop\context-relay-protocol
mkdocs serve
```

Opens at **http://127.0.0.1:8000** with hot-reload on every file save.

### Build the static site (without serving)

```bash
mkdocs build --strict
```

- `--strict` treats warnings as errors (catches broken links, missing files)
- Output goes to `site/` directory (gitignored)
- Check for any build warnings before deploying

### Common build issues

| Issue | Fix |
|-------|-----|
| `WARNING - Page not found: xyz.md` | File missing from `site-docs/`. Create it or remove from nav. |
| `WARNING - Navigation item has no page` | Usually a typo in `mkdocs.yml` nav path. |
| `ERROR - Config value 'plugins': ...` | Missing pip package. Run `pip install <plugin-name>`. |
| Emoji icons not rendering | Ensure `pymdownx-extensions` is installed. Material emoji extension is configured in `mkdocs.yml`. |
| Mermaid diagrams not rendering | `pymdownx.superfences` custom fence config handles this — already configured. |

---

## 4. Publishing to GitHub Pages

### Option A: GitHub Actions (Recommended)

Create `.github/workflows/docs.yml`:

```yaml
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.

name: Deploy Docs

on:
  push:
    branches: [main]
    paths:
      - 'site-docs/**'
      - 'mkdocs.yml'
  workflow_dispatch:  # allow manual trigger

permissions:
  contents: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install docs dependencies
        run: pip install mkdocs-material pymdownx-extensions

      - name: Build and deploy
        run: mkdocs gh-deploy --force --strict
```

**How it works:**
1. On every push to `main` that touches `site-docs/` or `mkdocs.yml`, it triggers
2. Builds the site with `--strict` (fails on warnings)
3. `mkdocs gh-deploy --force` pushes the built static files to the `gh-pages` branch
4. GitHub Pages serves from that branch

### Option B: Manual deploy from local machine

```bash
cd c:\Users\User\Desktop\context-relay-protocol
mkdocs gh-deploy --force --strict
```

This builds and pushes the `gh-pages` branch in one command.

---

## 5. GitHub Pages Configuration

### One-time setup in GitHub repo settings:

1. Go to **github.com/Constantinos-uni/context-relay-protocol** → **Settings** → **Pages**
2. Set **Source** to: `Deploy from a branch`
3. Set **Branch** to: `gh-pages` / `/ (root)`
4. Click **Save**

### Custom domain setup:

The `CNAME` file already exists in `site-docs/` with content `crprotocol.io`.
MkDocs copies this to the root of the built site automatically.

**DNS records required** (at your domain registrar):

| Type | Name | Value |
|------|------|-------|
| `A` | `@` | `185.199.108.153` |
| `A` | `@` | `185.199.109.153` |
| `A` | `@` | `185.199.110.153` |
| `A` | `@` | `185.199.111.153` |
| `CNAME` | `www` | `constantinos-uni.github.io` |

> These are GitHub Pages' IP addresses. If you've already configured DNS for
> crprotocol.io, no changes are needed.

After DNS propagates, enable **Enforce HTTPS** in the GitHub Pages settings.

---

## 6. Publishing Checklist

Run through this before every deploy:

```
PRE-DEPLOY
──────────
□  mkdocs build --strict            # Zero warnings?
□  mkdocs serve                     # Preview locally — all pages render?
□  Check nav order                  # Products tab visible and correct?
□  Check all links                  # Internal cross-links working?
□  Check product pages              # comply.md, comply-autocyber.md, scribe.md
□  Check CNAME                      # site-docs/CNAME contains "crprotocol.io"?
□  Check hero stats on home page    # Numbers still accurate?

DEPLOY
──────
□  git add -A && git commit         # Commit all changes
□  git push origin main             # Push to GitHub
□  GitHub Action triggers (or run mkdocs gh-deploy --force)
□  Wait 2–5 minutes for propagation

POST-DEPLOY
───────────
□  Visit https://crprotocol.io      # Site loads?
□  Check HTTPS                      # Padlock icon present?
□  Visit /products/comply/          # CRP Comply page renders?
□  Visit /products/comply-autocyber/# AutoCyber AI page renders?
□  Check mobile layout              # Responsive on phone?
```

---

## 7. Next Steps — Priority Order

### Step 1: Install docs toolchain and test locally

```bash
pip install mkdocs-material pymdownx-extensions
cd c:\Users\User\Desktop\context-relay-protocol
mkdocs build --strict
mkdocs serve
```

Visit http://127.0.0.1:8000 and verify every page.

### Step 2: Create the GitHub Actions workflow

Create `.github/workflows/docs.yml` with the YAML from Section 4 above. This
automates deployment on every push to `main`.

### Step 3: Configure GitHub Pages

In the repo settings → Pages:
- Source: `Deploy from a branch`
- Branch: `gh-pages` / `/ (root)`
- Custom domain: `crprotocol.io`
- Enforce HTTPS: ✅

### Step 4: Verify DNS

Confirm your domain registrar has the 4 `A` records and `www` CNAME pointing to
GitHub Pages (see Section 5).

### Step 5: First deploy

```bash
git add -A
git commit -m "docs: add Products section, CRP Comply & AutoCyber AI pages"
git push origin main
```

The GitHub Action deploys automatically. Or manually:

```bash
mkdocs gh-deploy --force --strict
```

### Step 6: Verify live site

- https://crprotocol.io — home page loads
- https://crprotocol.io/products/comply/ — CRP Comply product page
- https://crprotocol.io/products/comply-autocyber/ — AutoCyber AI integration page
- https://crprotocol.io/products/ — Products overview with cards

### Step 7: Add to CI pipeline (optional)

Add a docs build check to the existing CI workflow so broken docs block PRs:

```yaml
# Add to .github/workflows/ci.yml
  docs-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: pip install mkdocs-material pymdownx-extensions
      - run: mkdocs build --strict
```

---

## 8. Maintenance

### Adding a new page

1. Create the `.md` file in the appropriate `site-docs/` subdirectory
2. Add it to the `nav:` section in `mkdocs.yml`
3. Run `mkdocs build --strict` to verify
4. Commit and push

### Adding a new product

1. Create `site-docs/products/<product-name>.md`
2. Add a card to `site-docs/products/index.md`
3. Add to `mkdocs.yml` nav under `Products:`
4. Run `mkdocs build --strict`
5. Commit and push

### Updating the home page stats

Edit `site-docs/index.md` — the hero stats section has hardcoded numbers:

```html
<div class="hero-stat"><span class="num">1,537</span><span class="label">Tests Passing</span></div>
<div class="hero-stat"><span class="num">33/35</span><span class="label">EU AI Act Controls</span></div>
```

Update these when test count or compliance coverage changes.

---

## 9. Architecture Reference

```
context-relay-protocol/
├── mkdocs.yml                    ← Site config, theme, nav, extensions
├── site-docs/                    ← All page content (docs_dir)
│   ├── CNAME                     ← Custom domain for GitHub Pages
│   ├── index.md                  ← Home page (hero, stats, Before/After)
│   ├── why-crp.md                ← Value proposition
│   ├── getting-started/          ← Installation, quickstart, providers
│   ├── protocol/                 ← Technical protocol documentation
│   ├── guides/                   ← How-to guides
│   ├── compliance/               ← EU AI Act, ISO 42001, GDPR, NIST
│   ├── api/                      ← API reference
│   ├── testing/                  ← Test and benchmark docs
│   ├── products/                 ← Product pages (Comply, Scribe, etc.)
│   ├── contributing.md
│   └── terms-of-service.md
├── .github/workflows/
│   ├── ci.yml                    ← Lint, test, type-check
│   ├── docs.yml                  ← ⬅ CREATE THIS — auto-deploy docs
│   ├── validate-schemas.yml
│   └── link-check.yml
└── site/                         ← Built output (gitignored)
```

---

*Last updated: April 2026. Contact: info@crprotocol.io*
