# CRP Docs Platform Evaluation

## Executive summary

The CRP documentation site should **stay on MkDocs Material** for the foreseeable future. It is not yet outgrowing the platform. The current build is fast (~12 s), passes `--strict`, has no unreferenced pages, and supports 156 pages plus an auto-generated Python API reference. The pain points users have reported are visual (readability, density, card consistency, typography), not architectural limitations of MkDocs.

**Recommendation:**

1. **Do not migrate** to Docusaurus, Sphinx, GitBook/ReadMe, or Fern/Speakeasy today.
2. **Invest in the current MkDocs site**: typography, spacing, color consistency, mobile layout, and navigation polish.
3. **Add versioning** (`mike`) when CRP ships a stable v1.0 / v2.0 or needs to keep multiple SDK versions online.
4. **Re-evaluate migration** only when one of the concrete triggers below is hit.

## What is working well today

| Capability | Current state |
|------------|---------------|
| Authoring format | Markdown - whole team can contribute via Git |
| Theme | Material for MkDocs (already the richest MkDocs theme) |
| API reference | Auto-generated from `crp/` via `mkdocstrings` + `scripts/generate_api_reference.py` |
| Search | Client-side full-text with highlight, suggestions, sharing |
| Nav model | Section sidebar + indexes + prune - scales to 156 pages |
| CI/CD | `.github/workflows/docs.yml` deploys to `gh-pages` automatically |
| Extensions | Admonitions, tabs, Mermaid diagrams, code annotations, footnotes, emoji |
| Build speed | ~12 s strict build |
| Cost/hosting | Free via GitHub Pages |

## What is missing

These are the real gaps. Note that none of them make the site unusable; they are future capabilities.

- **Versioning** - no ability to browse v3.x vs v4.x docs side-by-side.
- **Interactive API explorer** - no Try-it console or OpenAPI/Swagger rendering.
- **React/MDX components** - no embedded playgrounds, interactive calculators, or animated diagrams.
- **i18n / multi-language** - only English today.
- **Generated SDK docs beyond Python** - no TypeScript/Java/Go SDK auto-reference yet.
- **WYSIWYG/editor UI** - non-engineers must edit Markdown in Git.

## Platform comparison

Scored 1–5 (5 = best fit). Weighted by what matters most to CRP today.

| Dimension | Weight | MkDocs Material | Docusaurus | Sphinx | GitBook / ReadMe | Fern / Speakeasy |
|-----------|--------|-----------------|------------|--------|------------------|------------------|
| Markdown authoring | 5 | 5 | 4 | 3 | 5 | 4 |
| Python API auto-docs | 5 | 5 | 3* | 5 | 2 | 3 |
| Build speed / simplicity | 4 | 5 | 3 | 3 | 5 | 4 |
| Search | 4 | 4 | 4 | 4 | 5 | 5 |
| Theming / branding | 4 | 4 | 5 | 3 | 4 | 5 |
| Versioning | 3 | 3** | 5 | 5 | 4 | 4 |
| Interactive components (React/MDX) | 3 | 1 | 5 | 2 | 3 | 4 |
| OpenAPI / SDK reference generation | 3 | 2 | 3 | 2 | 4 | 5 |
| Multi-language (i18n) | 2 | 2 | 5 | 4 | 4 | 4 |
| CI/CD portability | 3 | 5 | 4 | 4 | 3 | 3 |
| Vendor lock-in / cost | 4 | 5 | 4 | 5 | 2 | 2 |
| **Weighted total** | - | **4.2** | **3.9** | **3.6** | **3.6** | **3.9** |

\* Docusaurus can generate Python docs with `docusaurus-plugin-typedoc` or a custom parser, but the ecosystem is weaker than MkDocs/Sphinx for Python.
\** MkDocs versioning is solved by `mike`; it is good but not as polished as Docusaurus/Sphinx out-of-the-box.

### Notes on each option

**MkDocs Material (current)**
- Already the strongest Markdown-native option for Python projects.
- `mkdocstrings` gives us tightly integrated API reference pages.
- Migration cost = 0. Build and deploy pipeline already works.
- Ceiling: static content only; no React components, no native versioning, weaker OpenAPI rendering.

**Docusaurus**
- Best choice if we need React/MDX components, interactive diagrams, or i18n.
- Strong versioning and blog support.
- Python API docs require extra plumbing (e.g., convert mkdocstrings output or use a TypeDoc-like pipeline).
- Higher migration effort: convert `nav`, rewrite custom CSS/JS, rebuild API generation.

**Sphinx**
- The canonical Python docs generator; autodoc is mature.
- RST/Myst can feel heavy for marketing-style pages; theming is harder than MkDocs/Docusaurus.
- Best if docs become deeply API-centric and less product/marketing oriented.

**GitBook / ReadMe**
- Fully managed, beautiful default UI, good search, OpenAPI blocks.
- Expensive at scale; less control over CI, custom domains, and git workflows.
- Best for a small, non-technical docs team that wants a CMS.

**Fern / Speakeasy**
- Built for API-first products and SDK generation.
- Excellent OpenAPI reference and multi-language SDK snippets.
- Less natural for long-form narrative/protocol docs; requires OpenAPI spec as the source of truth.
- Best when the Gateway/Comply APIs become the primary developer surface.

## Decision

**Keep MkDocs Material.** The site has grown quickly but has not hit the ceiling. The weighted comparison shows MkDocs Material still ahead for CRP’s current needs, primarily because Python API auto-generation, Markdown authoring, CI portability, and zero cost/lock-in matter more than React components or managed hosting right now.

## Migration triggers

Re-open this evaluation when any of the following become true:

1. **Versioned product docs are required** - e.g., maintaining v3.x and v4.x simultaneously, and `mike` feels too clunky.
2. **Interactive API explorer is a hard requirement** - users need to call the Gateway from the docs.
3. **Multi-language docs** - translations to French, German, Japanese, etc., become a priority.
4. **Embedded React/MDX components** - calculators, interactive conformance checkers, live playgrounds.
5. **Non-engineering owners need a WYSIWYG editor** - Git-based Markdown becomes a blocker.
6. **Search performance degrades** - build/search times grow past ~60 s or the index becomes unusable.
7. **Non-Python SDKs become primary** - TypeScript/Go/Java SDK docs need first-class generated reference.

## Recommended roadmap

### Now (this cycle)
- Polish typography, spacing, card/grid consistency, and dark-mode contrast in the existing MkDocs site.
- Add `content.action.edit` so every page has an "Edit this page" link.
- Keep the auto-generated API reference pipeline.

### Next quarter
- Evaluate `mike` for versioning once a release branch/tag strategy is in place.
- Add an OpenAPI/Swagger page for the Gateway HTTP API using a lightweight MkDocs plugin or iframe.
- Create a docs contribution guide to keep Markdown quality high as more authors join.

### 6–12 months
- Re-run this evaluation if any trigger fires.
- Pilot Docusaurus on a small branch if React components or i18n become necessary.
- Pilot Fern if the Gateway API becomes the dominant developer surface.

## Conclusion

MkDocs is not the bottleneck. The site needs better styling and clearer information hierarchy, not a platform migration. Stay the course, keep the auto-generated API pipeline, and revisit the decision when a concrete trigger appears.
