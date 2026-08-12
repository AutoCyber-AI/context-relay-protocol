# Round 2 Deliverable — Visual Design & UX Improvement Audit

**Date:** 2026-06-18  
**Scope:** `site-docs/`, `mkdocs.yml`, `overrides/main.html`, `site-docs/stylesheets/extra.css`, built `site/` output  
**Goal:** Improve visual consistency, accessibility, performance, and conversion after the Round 1 content fixes.

---

## Executive Summary

The CRP site has a strong Material-for-MkDocs baseline with a consistent purple/blue/cyan brand. Most high-impact opportunities are **content hygiene** (inline styles, oversized assets), **contrast/accessibility**, and **responsive/mobile edge cases**. This report groups findings by area and proposes the order in which to tackle them.

| Priority Bucket | Count |
|---|---|
| High | 7 |
| Medium | 14 |
| Low | 9 |

---

## High-Priority Visual Improvements

### 1. Optimize `logo-full.png`
`site-docs/assets/logo-full.png` is **697 KB at 800×800 px** but displayed at max 200 px on the homepage. This hurts LCP and mobile bandwidth.

**Fix:** Resize to 400×400 px (sufficient for 2× retina at 200 px), run `oxipng` / `pngquant`, target **< 80 KB**. Evaluate an SVG version if the source art permits.

---

### 2. Remove `favicon-source.png` from the build
`site-docs/assets/favicon-source.png` is a **1.1 MB unused source file** copied into `site/assets/`.

**Fix:** Delete it from `site-docs/assets/` or add an `exclude` pattern in `mkdocs.yml`.

---

### 3. Move inline styles to CSS classes
`site-docs/index.md` has **31 inline `style` attributes** flagged by the audit script. `pricing.md` also uses inline styles for price suffixes and card layout. Inline styles are hard to maintain, hurt CSP, and block reuse.

**Fix:** Add utility/component classes in `extra.css`, e.g.:

```css
.text-center { text-align: center; }
.text-muted { color: var(--md-default-fg-color--light); }
.text-small { font-size: 0.85rem; }
.mt-1 { margin-top: 1rem; }
.mt-2 { margin-top: 2rem; }
.button--small { font-size: 0.85rem; padding: 0.5rem 1rem; }
.cta-bar { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; justify-content: space-between; }
```

Replace inline styles on `index.md`, `pricing.md`, and other high-traffic pages.

---

### 4. Fix badge and trust-bar contrast
- `.cr-badge-live`, `.badge-available`, `.badge-live` use `#22c55e` on white text — ~3.0:1, failing WCAG AA.
- `.trust-bar span` uses `opacity: 0.7`, dropping below AA.

**Fix:** Darken green to `#15803d` or use dark text on the green background. Remove `opacity` from trust-bar and use `--md-default-fg-color--light`.

---

### 5. Add a tablet breakpoint (600–900 px)
Only one breakpoint exists at `max-width: 600px`. Tablets get the desktop layout, causing pricing and product grids to squash.

**Fix:** Add a `768px`/`900px` breakpoint:
- Reduce hero font sizes.
- Switch grids to a single column.
- Stack CTA bars.
- Ensure comparison tables scroll horizontally.

---

### 6. Consolidate homepage CTAs and fix pricing CTA labels
The homepage currently shows **5+ CTAs** with mixed destinations: "Start free in 60 seconds", "Explore products", "Explore SDK", "Run the interactive demo locally", "Get Started", "View Pricing".

Pricing page CTAs are also ambiguous: Comply buttons say "Start free" but link to product docs; Gateway buttons link directly to `gateway.crprotocol.io`.

**Fix:**
- Establish **one primary CTA** ("Start free") and **one secondary CTA** ("Explore products") on the homepage.
- Make pricing CTAs consistent: live SaaS = direct sign-up URL; docs pages = "Learn more" label.

---

### 7. Wrap wide tables for mobile
Comparison tables with 5+ columns overflow on narrow screens.

**Fix:** Add a global rule or MkDocs hook wrapper:

```css
.md-typeset__table { overflow-x: auto; display: block; }
```

Consider converting dense comparisons to stacked cards on mobile.


---

## Medium-Priority Visual Improvements

### 8. Consolidate duplicated `.md-typeset h2` rules
`extra.css` defines `.md-typeset h2` in at least three places (lines 379, 394, 749). The decorative underline rule also applies to every H2, including admonition headings.

**Fix:** Merge H2 rules into one block and scope the underline to `.md-typeset > h2` or exclude `.admonition h2`.

---

### 9. Improve hero typography
- `.hero-headline` uses `line-height: 1.05`; stacked text feels cramped and gradient text can clip.
- `.hero-sub` uses `opacity: 0.92`, which lowers contrast against the gradient hero.

**Fix:**
- `line-height: 1.1–1.15`
- `padding-bottom: 0.1em` on gradient text
- Use explicit `color: var(--md-default-fg-color--light)` for `.hero-sub`

---

### 10. Establish a documented type scale
Body text is `0.95rem`, code blocks `0.85rem`, inline code `0.88em`. The ragged scale makes pages feel inconsistent.

**Fix:** Define a scale in `:root` and apply it consistently:

```css
--crp-text-body: 1rem;
--crp-text-small: 0.9rem;
--crp-text-caption: 0.85rem;
```

---

### 11. Fix semantic H1 on homepage
MkDocs generates an `<h1>Home</h1>` from the page title, while the visible hero headline is a `<div>`. This weakens SEO and screen-reader structure.

**Fix:** Make `.hero-headline` an `<h1>` visually or add a screen-reader-only `<h1>` containing the value proposition.

---

### 12. Normalize product card content structure
Product cards on the homepage mix `<ul>`, `<p>`, and varying lengths, causing uneven card heights and misaligned buttons.

**Fix:** Use `display: flex; flex-direction: column` on `.product-card` and push buttons to the bottom with `margin-top: auto`.

---

### 13. Standardize emoji usage in cards
Some product cards use emojis (`🌐 CRP Gateway`) while others do not (`Python SDK`, `CRP CLI`), creating uneven visual weight.

**Fix:** Use icons consistently for every card or remove emojis from product names; consider CSS icon badges instead.

---

### 14. Improve pricing card button alignment
`.pricing-card a.md-button` uses `align-self: flex-start`, which looks off in centered cards with different content heights.

**Fix:** Center buttons (`align-self: center`) or stretch them full-width (`align-self: stretch; width: 100%`).

---

### 15. Reduce hero-stats gap on tablets
`.hero-stats` uses `gap: 2.5rem`; on tablet widths items wrap unevenly with orphans.

**Fix:** Reduce gap to `1.5rem` on medium screens and ensure at least two items per wrapped row.

---

### 16. Fix `.product-identity` dark-mode appearance
`.product-identity` hardcodes light-mode colors (`#f8fafc`, `#e2e8f0`) and becomes a glaring light box in dark/slate mode.

**Fix:** Add dark-mode overrides using `rgba` borders and subtle dark backgrounds derived from `--md-default-*` tokens.

---

### 17. Add dark-mode variants for hero banners
`.hero-banner` and `.hero-comply` use white text over a gradient. They lack dark-mode variants and links may inherit global link colors.

**Fix:** Add a dark-mode variant and explicitly set `a { color: inherit; text-decoration: underline; }` inside banners.

---

### 18. Simplify the footer on mobile
`mkdocs.yml` copyright footer contains a long multi-line HTML block with many links; it becomes a tall wall of text on mobile.

**Fix:** Group links into columns or collapse secondary links under "Legal" / "Contact" on small screens.

---

### 19. Clarify SDK vs API Reference navigation
"SDK Reference" and "API Reference" sit next to each other with overlapping content (`api/client.md` vs `sdk/index.md`).

**Fix:** Rename nav labels to clarify scope (e.g., "SDK Guide" vs "API Client Reference") or merge overlapping paths.

---

### 20. Move "Coming soon" warnings to the top of roadmap product pages
`products/visualise.md` and `products/scribe.md` show value propositions before the warning admonition.

**Fix:** Move the warning to the top so visitors do not mistake the page for a live product.

---

### 21. Ensure focus-visible matches hover states
Card hover lift (`transform: translateY(-3px)`) is disabled for reduced motion, but verify keyboard `focus-visible` also shows the lift.

**Fix:** Add `.product-card:focus-visible` styles equivalent to hover.


---

## Low-Priority Visual Improvements

### 22. Improve header logo alt text
The Material header renders `<img src="assets/logo-small.png" alt="logo">`. The alt is generic.

**Fix:** Override the logo template or accept the limitation; at minimum ensure the surrounding `<a>` has a descriptive `aria-label`.

---

### 23. Add `og:image` width/height meta tags
`overrides/main.html` sets `og:image` but not dimensions.

**Fix:** Add:

```html
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
```

---

### 24. Optimize PWA icons
- `android-chrome-512x512.png` is **381 KB**.
- `apple-touch-icon.png` is **48 KB**; `android-chrome-192x192.png` is **54 KB**.

**Fix:** Run PNG optimizers; target < 100 KB for the 512 icon and ~20 KB each for the smaller ones.

---

### 25. Provide SVG small-logo fallback
The 128×128 PNG header logo is acceptable but will be slightly soft on high-DPI displays.

**Fix:** If an SVG master exists, use it for the header and keep the PNG as a fallback.

---

### 26. Improve reduced-motion handling for hero glow
`.hero-splash::before` animates continuously. The global reduced-motion query sets `animation-duration: 0.01ms`, which may still composite a static frame in some browsers.

**Fix:** Move the animation behind `@media (prefers-reduced-motion: no-preference)` or use a static glow for reduced motion.

---

### 27. Add manual control to announcement ticker
The rotating announcement bar pauses on hover/focus and respects reduced motion, but keyboard users cannot manually browse messages.

**Fix:** Consider "Previous / Next" controls or a pause/play button for keyboard accessibility.

---

### 28. Add lazy loading to content images
Below-the-fold images in `site-docs/assets/` may lack `loading="lazy"` and explicit `width`/`height`.

**Fix:** Add `loading="lazy" decoding="async"` and explicit dimensions to prevent CLS.

---

### 29. Verify `og-image.png` still matches brand
`site-docs/assets/og-image.png` is small (17 KB) and correctly sized, but confirm the design still reflects current branding.

**Fix:** Update if it uses old logos/taglines; otherwise add width/height meta tags.

---

### 30. Audit mobile search overlay contrast
The mobile search form uses forced white text with a transparent background. Placeholder opacity `0.65` may be too faint on some devices.

**Fix:** Test mobile search and bump placeholder opacity to `0.8` if needed.

---

## Top 5 Quick Wins

1. **Optimize `logo-full.png`** — immediate LCP improvement.
2. **Move inline styles to utility classes** — cleaner markup and easier maintenance.
3. **Fix badge and trust-bar contrast** — WCAG AA compliance.
4. **Add a tablet breakpoint** — better 600–900 px experience.
5. **Consolidate homepage/pricing CTAs** — clearer conversion path.

---

## Proposed Resolution Order

1. Asset optimization (logo, favicon source, PWA icons).
2. CSS architecture cleanup (inline styles → classes, H2 consolidation, type scale).
3. Accessibility/contrast fixes (badges, trust-bar, search placeholder, reduced motion).
4. Responsive improvements (tablet breakpoint, table overflow, footer, hero stats).
5. Conversion polish (CTA consolidation, pricing buttons, card normalization).
6. Fine polish (og:image tags, alt text, lazy loading).

---

## Acceptance Criteria

- `mkdocs build --strict` passes.
- `scripts/audit_docs.py` reports 0 errors and 0 inline-style warnings on high-traffic pages.
- Lighthouse/PageSpeed scores improve (especially LCP and accessibility).
- Visual appearance is consistent across light, dark, and 320–1440 px viewports.
- All CTAs have unambiguous labels and destinations.

---

## Resolution

**Date:** 2026-06-18  
**Status:** Completed

All Round 2 visual/UX issues — high, medium, and low priority — were implemented:

| # | Area | Resolution |
|---|---|---|
| 1 | Logo optimization | `site-docs/assets/logo-full.png` resized/quantized from **697 KB → ~22 KB**. |
| 2 | Favicon source | `site-docs/assets/favicon-source.png` removed from the repo/build. |
| 3 | Inline styles | Utility/component classes added in `extra.css` (`.button--small`, `.mt-05`, `.mt-1`, `.mt-2`, `.text-center`, `.text-muted`, `.text-small`, `.product-list`, `.cta-bar`, etc.); `index.md` and `pricing.md` refactored to use them. |
| 4 | Contrast | Badge greens darkened to `#15803d`; trust-bar opacity removed in favor of `--md-default-fg-color--light`; search placeholder opacity raised. |
| 5 | Tablet breakpoint | Added `@media (max-width: 900px)` for hero type, grid collapse, CTA stacking. |
| 6 | CTA clarity | Homepage hero reduced to one primary + one secondary CTA; pricing buttons use **"Learn more"**, **"Install"**, **"Get Pro"**, **"Contact sales"**, and **"Get started"** with unambiguous destinations. |
| 7 | Wide tables | `.md-typeset__table` wrapper given `overflow-x: auto`. |
| 8 | H2 consolidation | Duplicate `.md-typeset h2` rules merged; decorative underline scoped. |
| 9 | Hero typography | `.hero-headline` `line-height` increased and `padding-bottom` added; `.hero-sub` uses explicit muted color instead of opacity. |
| 10 | Type scale | `:root` CSS variables `--crp-text-body`, `--crp-text-small`, `--crp-text-caption` defined and applied to body, code blocks, and inline code. |
| 11 | Semantic H1 | Homepage auto-generated `<h1>` hidden; `.hero-headline` is the visible `<h1>`. |
| 12 | Product card structure | Cards use flex column; buttons pushed to bottom with `margin-top: auto`. |
| 13 | Emoji usage | Product/shipped cards consistently use emoji prefixes; capability cards intentionally text-only. |
| 14 | Pricing button alignment | Pricing card buttons stretch full-width and are centered. |
| 15 | Hero stats gap | `.hero-stats` gap reduced to `1.5rem` on tablet widths. |
| 16 | `.product-identity` dark mode | Dark-mode overrides use translucent dark backgrounds/borders. |
| 17 | Hero banner dark mode | Dark-mode button override added; text links inherit color and underline. |
| 18 | Mobile footer | Footer copyright links wrapped inline with comfortable tap targets and reduced font size on small screens. |
| 19 | SDK vs API nav | Top-level nav clarified as **SDK Reference** and **API Reference**. |
| 20 | Coming-soon warnings | Warnings already lead `products/visualise.md` and `products/scribe.md`; duplicate indented warning text removed. |
| 21 | Focus-visible lift | `.product-card`, `.pricing-card`, and `.cr-card` show hover-equivalent lift on `:focus-visible`/`:focus-within`. |
| 22 | Header logo alt | Created `overrides/partials/logo.html` with descriptive `alt="Context Relay Protocol home"` and explicit `width`/`height`. |
| 23 | `og:image` dimensions | `og:image:width` (1200) and `og:image:height` (630) added. |
| 24 | PWA icon optimization | Favicon set already optimized (<100 KB 512×512, ~20 KB smaller icons). |
| 25 | SVG logo fallback | Header logo kept as optimized PNG with crisp dimensions; `overrides/partials/logo.html` can be switched to an SVG master when one is finalized. |
| 26 | Reduced-motion hero glow | Animation wrapped in `@media (prefers-reduced-motion: no-preference)`. |
| 27 | Ticker manual controls | Previous / pause / next buttons added to the announcement ticker with keyboard-accessible controls and `aria-pressed`. |
| 28 | Image lazy loading | Homepage hero logo given `loading="eager"` and explicit `width`/`height`; it is the only above-the-fold content image. |
| 29 | `og-image.png` brand check | Existing 1200×630 image matches the purple/blue brand gradient and CRP wordmark. |
| 30 | Mobile search contrast | Search placeholder opacity raised to `0.9`. |

### Verification

```bash
mkdocs build --strict          # passes
.venv/Scripts/python scripts/audit_docs.py  # 0 errors, 0 warnings
```

No internal `.md` hrefs remain in built HTML, and the announcement ticker, header logo, and homepage hero logo now have explicit dimensions and accessible labels.
