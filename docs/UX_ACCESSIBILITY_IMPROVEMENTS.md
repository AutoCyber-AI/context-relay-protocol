# UX & Accessibility Improvements

This document records the heavy UX and accessibility pass applied to the CRP documentation site.

## Goal

Make the site faster, easier to navigate, more accessible, and more trustworthy for visitors — while keeping the build stable on Windows, macOS, and Linux.

## Plugins installed and enabled

| Plugin | Purpose | Status |
|---|---|---|
| `mkdocs-minify-plugin` | Minifies HTML/CSS/JS for faster loads. | Enabled |
| `mkdocs-redirects` | Provides redirect maps for future URL changes. | Enabled (empty map) |
| `mkdocs-git-revision-date-localized-plugin` | Shows "Last updated" and "Created" dates per page. | Enabled |
| `mkdocs-git-authors-plugin` | Lists document authors from git history. | Enabled |
| `mkdocs-glightbox` | Accessible image lightbox/zoom for content images. | Enabled |
| Material `privacy` | Downloads external assets (fonts, Mermaid, Twemoji) so the site does not leak visitor data to third parties. | Enabled |
| Material `meta` | Inherits metadata per directory (used for tags). | Enabled |
| Material `tags` | Tag-based discovery with a generated tags index. | Enabled |

### Plugins researched but intentionally not enabled

- **`optimize`** — Requires external binaries (`pngquant`, `oxipng`, `svgo`) that are not guaranteed on Windows or in CI. Images are already optimized manually.
- **`social`** — Requires CairoSVG, which needs native `cairo` libraries. These are not available in this Windows environment and would break local builds. A manually created `og-image.png` is already in place.

## Material features enabled

- `navigation.instant` + `navigation.instant.prefetch` + `navigation.instant.progress` — SPA-like navigation with prefetch and progress bar.
- `navigation.path` — Breadcrumb navigation above each page title.
- `header.autohide` — Header hides on scroll down to maximize reading space.
- `content.code.select` — Code range selection button on code blocks.
- `content.footnote.tooltips` — Inline footnote tooltips.
- `toc` `permalink_title` set to an accessible description.

## Accessibility markup improvements

- **Header logo**: `overrides/partials/logo.html` overrides the generic `"logo"` alt text with `"Context Relay Protocol home"` and explicit `width`/`height`.
- **Hero logo**: `loading="eager"` and explicit `width`/`height` to prevent layout shift.
- **Announcement ticker**: Added Previous / Pause / Next buttons with `aria-label` and `aria-pressed`.
- **No heuristic a11y issues**: A scan of the built `site/` found no images missing `alt`, no empty links, and no buttons lacking accessible names.

## Tags and discoverability

- Added `site-docs/tags.md` as a tags index.
- Added `.meta.yml` files in every major section (`api`, `compliance`, `getting-started`, `guides`, `legal`, `products`, `protocol`, `safety`, `sdk`, `spec`, `testing`) so each page inherits a section tag.

## Build and verification

```bash
.venv\Scripts\python scripts/audit_docs.py
# Running mkdocs build --strict ...
# No audit findings. Site docs look clean.
```

```bash
DISABLE_MKDOCS_2_WARNING=true .venv\Scripts\python -m mkdocs build --strict
# Documentation built successfully.
```

## CI updates

- `.github/workflows/docs.yml` now checks out the full git history (`fetch-depth: 0`) so git-based plugins work correctly.
- `DISABLE_MKDOCS_2_WARNING=true` is set in CI to suppress the MkDocs 2.0 ecosystem warning.
- `pyproject.toml` docs extras include all installed plugins.

## Files added or changed

- `mkdocs.yml` — new features, plugins, tags nav, TOC title.
- `pyproject.toml` — docs dependency list updated.
- `.github/workflows/docs.yml` — `fetch-depth: 0`, env var.
- `scripts/audit_docs.py` — sets `DISABLE_MKDOCS_2_WARNING` during audit.
- `overrides/partials/logo.html` — accessible logo partial.
- `site-docs/tags.md` — tags index page.
- `site-docs/*/.meta.yml` — section-level metadata tags.
- `.gitignore` — ignores `.cache/` created by the privacy plugin.
