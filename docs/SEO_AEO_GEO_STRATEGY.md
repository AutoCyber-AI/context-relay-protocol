# CRP SEO / AEO / GEO Strategy

## Goal

Make **Context Relay Protocol (CRP)** the top-ranked authoritative result for:

- **Brand & category**: "Context Relay Protocol", "CRP protocol", "context management protocol", "LLM context protocol"
- **AI safety**: "AI safety protocol", "AI safety standard", "LLM safety framework"
- **AI governance**: "AI governance framework", "AI governance for LLMs", "LLM governance"
- **AI compliance**: "AI compliance", "EU AI Act compliance", "ISO 42001 compliance"

Realistic near-term targets:

| Keyword / Query | Target |
|---|---|
| `Context Relay Protocol` | #1 (owned) |
| `CRP protocol` | #1 (owned) |
| `CRP AI safety` | #1–3 |
| `AI safety protocol` / `AI safety standard` | Top 10–20 within 6 mo, top 5 long-term |
| `AI governance framework for LLMs` | Top 10 within 6 mo |
| `AI compliance evidence` / `EU AI Act evidence` | Top 10–20 |
| `context management for LLMs` | Top 10–20 |

Head-term dominance (`AI safety`, `AI governance`) is a multi-year authority play. This strategy builds the foundation with technical SEO, topic clusters, answer-engine content, and generative-engine discoverability.

---

## 1. Technical SEO foundation

### 1.1 Titles & meta descriptions
- Every high-priority page gets a keyword-rich `<title>` and `meta name="description"`.
- Homepage title becomes: **"AI Safety, AI Governance & Context Management Protocol | CRP™"**.
- Template in `overrides/main.html` now respects `page.meta.seo_title` and `page.meta.description`.

### 1.2 Canonical & URL hygiene
- Canonical URLs already emitted for every page.
- Robots.txt already references `/sitemap.xml`.
- MkDocs generates `/sitemap.xml.gz`; we expose it in `robots.txt`.
- Ensure no duplicate content: spec pages are canonicalised by path.

### 1.3 Structured data (Schema.org)
- **Homepage**: Organization, WebSite (with SearchAction), SoftwareApplication.
- **Every page with a TOC**: BreadcrumbList.
- **FAQ pages**: `FAQPage` JSON-LD.
- **Quickstart / tutorials**: `HowTo` JSON-LD.
- **Spec pages**: `TechArticle` / `ScholarlyArticle` JSON-LD with citations.

### 1.4 Open Graph / Twitter
- Per-page `og:title`, `og:description`, `twitter:title`, `twitter:description`.
- Static `og-image.png` retained (social plugin skipped on Windows dev box).

### 1.5 Performance & accessibility
- `navigation.instant`, prefetch, minify, privacy plugin already active.
- All images have alt text; logo alt improved.
- Keep CLS low: explicit image dimensions, CSS utility classes.

---

## 2. Content architecture — topic clusters

Create a **Topics** hub with four pillar pages. Each pillar links into existing products, protocol, safety, compliance, spec, and SDK docs.

```
/topics/
├── index.md                 (cluster hub)
├── ai-safety.md             (pillar)
├── ai-governance.md         (pillar)
├── ai-compliance.md         (pillar)
├── context-management.md    (pillar)
└── crp-vs-rag-mcp.md        (comparison / long-tail)
```

### 2.1 Pillar page template
- **H1**: exact target keyword phrase.
- **Definition block**: concise answer (40–60 words) for featured snippets.
- **What it means for LLMs**: why traditional approaches fail.
- **CRP approach**: protocol-level capabilities mapped to the topic.
- **Standards alignment**: EU AI Act / ISO 42001 / NIST AI RMF / GDPR.
- **FAQ schema**: 6–10 questions.
- **See also**: internal links to product, spec, compliance, and SDK pages.
- **CTA**: Gateway waitlist, quickstart, GitHub.

### 2.2 Comparison / "vs" content
- `crp-vs-rag-mcp.md` targets long-tail queries like:
  - "CRP vs RAG"
  - "MCP vs context management"
  - "LLM context protocol comparison"
- Include a decision table and "when to use each" guidance.

### 2.3 FAQ page
- `/faq.md` targets answer boxes and People Also Ask.
- Covers: What is CRP? How does CRP improve AI safety? Does CRP replace RAG? Is CRP open source? What standards does CRP support? How do I get started?

---

## 3. AEO — Answer Engine Optimization

### 3.1 Featured snippets
- Place a concise definition in the first 100 words of every pillar page.
- Use definition lists, tables, and ordered lists where Google commonly pulls snippets.
- Example format: *"AI governance is the system of policies, processes, and controls that ensure AI is developed and used safely, transparently, and accountably."*

### 3.2 People Also Ask
- Each pillar page includes an FAQ section that directly answers PAA-style questions.
- Mark up with `FAQPage` JSON-LD.

### 3.3 Voice / conversational search
- Write headings as natural-language questions: "What is AI safety?", "How does CRP enforce AI governance?", "What is context management in LLMs?"
- Keep answers under 30 words where possible, then expand.

---

## 4. GEO — Generative Engine Optimization

### 4.1 Make CRP easy to cite
- Add a **Cite CRP** page with BibTeX, MLA, APA, and Chicago citations for the IETF drafts and site pages.
- Every spec page ends with a "Cite this specification" block.
- Use stable URLs and canonical tags so LLMs attribute correctly.

### 4.2 Authoritative definitions
- Define CRP, Context Envelope, CKF, DPE, Safety Policy, and context management in Wikipedia-neutral language.
- Publish definitions in standalone glossary-style pages; LLM training corpora favour clear definitions.

### 4.3 External knowledge graphs
- Ensure Organization schema `sameAs` links to GitHub, LinkedIn, X, AutoCyber AI, and eventually Wikipedia / Crunchbase.
- Add `knowsAbout` array to Organization schema for target topics.

### 4.4 Research & standards citations
- Link to IETF drafts, ISO 42001, EU AI Act, NIST AI RMF, OWASP LLM Top 10.
- Where possible, get CRP cited in independent research, conference papers, and standards submissions.

---

## 5. Internal linking

### 5.1 Global signals
- Add **Topics** to main navigation so every page links to the cluster hub.
- Tag every page with relevant tags; the Tags page becomes a semantic internal-link hub.
- Update section `.meta.yml` files to include `ai-safety`, `ai-governance`, `ai-compliance`, and `context-management` where relevant.

### 5.2 Contextual links
- Add "See also" admonitions to pillar pages pointing to protocol, SDK, compliance, and product pages.
- Link from product pages back to relevant pillar pages.

### 5.3 Anchor text strategy
- Use descriptive anchors: "AI governance framework" not "click here".
- Avoid over-optimised exact-match anchors; mix branded, partial-match, and natural phrases.

---

## 6. Off-page & authority building

### 6.1 Existing assets
- IETF drafts already provide high-authority backlinks (ietf.org, datatracker.ietf.org).
- AutoCyber AI main site links to crprotocol.io.

### 6.2 Backlog
- Publish guest posts / technical deep-dives on:
  - ACM / IEEE blogs
  - OWASP AI security working groups
  - LF AI & Data Foundation
  - AI safety newsletters (e.g., AI Safety Newsletter, Import AI)
- Get listed in AI governance tooling directories (e.g., NIST AI RMF resource page, EU AI Act Observatory, AI Verify).
- Create a **Press & Media Kit** page with approved boilerplate, logos, and quotes.

### 6.3 Community signals
- GitHub README links to crprotocol.io.
- LinkedIn / X posts use canonical URLs.
- Encourage citations in academic papers with the BibTeX block.

---

## 7. Measurement

### 7.1 KPIs
- Organic sessions and clicks for `/topics/*` pages.
- Rankings for target keyword list (track weekly via Search Console + a rank tracker).
- Featured snippet / PAA capture.
- Brand mention volume and LLM citation share (manual / Perplexity/Copilot sampling).
- Backlinks and referring domains (Ahrefs / Search Console).

### 7.2 Tools
- Google Search Console (sitemap submitted).
- Bing Webmaster Tools.
- Ahrefs / Semrush for keyword & competitor research.
- Perplexity / ChatGPT / Gemini queries sampled monthly for "What is the best AI safety protocol?" etc.

---

## 8. Immediate deliverables (this round)

1. `docs/SEO_AEO_GEO_STRATEGY.md` — this document.
2. `overrides/main.html` — per-page SEO title/description support.
3. `site-docs/topics/*` — four pillar pages + comparison + hub.
4. `site-docs/faq.md` — general FAQ with FAQPage schema.
5. `site-docs/cite.md` — citation page with BibTeX.
6. Section `.meta.yml` updates — add AI topic tags.
7. `site-docs/tags.md` — improved title/description.
8. Per-page `seo_title` / `description` front matter on homepage and key pages.
9. `mkdocs.yml` nav update for Topics + FAQ + Cite.
10. Strict build verification with `scripts/audit_docs.py`.

---

## 9. Next rounds (prioritised)

1. **Blog / changelog as SEO engine** — publish weekly answer-oriented posts (e.g., "EU AI Act Article 50 evidence requirements", "NIST AI RMF GOVERN function with CRP").
2. **Case studies** — customer evidence with schema.org `CaseStudy` markup.
3. **Interactive tools** — EU AI Act risk classifier, compliance readiness checker.
4. **Schema expansion** — `HowTo` on quickstart, `Course` for tutorials.
5. **Internationalization** — language variants for EU / APAC compliance terms.
6. **Video schema** — demo videos with transcripts.
