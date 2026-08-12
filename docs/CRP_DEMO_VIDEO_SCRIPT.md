# CRP Demo Video Production Guide

This guide is for producing marketing/demo videos of CRP Gateway, CRP Comply,
and the CRP v4.1 protocol demo **without touching the production repositories**.

> **Rule:** Demo videos live only in `context-relay-protocol/video-production/output/`
> and `media/demos/`. They are **never** copied into `crp-gateway/frontend/public/`,
> `crp-gateway/static/`, or `crp-comply/frontend/public/`. The production landing
> pages should embed videos from a CDN (e.g. Cloudflare Stream, AWS S3 + CloudFront)
> or from a dedicated demo site, not from the production app bundle.

## Existing tooling

The repo already contains a programmatic video pipeline:

```text
video-production/
├── src/record-gateway.ts      # CRP Gateway landing + console flow
├── src/record-comply.ts       # CRP Comply landing + scan flow
├── src/record-protocol-demo.ts # CRP v4.1 local-LLM protocol demo
├── src/helpers.ts             # Playwright recording helpers
└── output/                    # Generated .webm / .mp4 files
```

Install and run:

```bash
cd video-production
npm install
npx playwright install chromium

# Record each demo
npx tsx src/record-gateway.ts
npx tsx src/record-comply.ts
npx tsx src/record-protocol-demo.ts

# Convert to MP4 (if the recorder did not already)
ffmpeg -i output/gateway-demo.webm -c:v libx264 -preset fast -crf 28 output/gateway-demo.mp4
```

## Storyboard & scripts

### 1. CRP Gateway — "One-line safety upgrade"

**Goal:** Show a developer switching their OpenAI client base URL and getting
CRP safety headers back.

| Time | Visual | Script / on-screen text |
|------|--------|------------------------|
| 0:00 | Landing page hero | "CRP Gateway is an OpenAI-compatible governance proxy." |
| 0:05 | Terminal / code snippet | "Change one line: `base_url='https://gateway.crprotocol.io/v1'`" |
| 0:10 | Dashboard → API keys | "Create an API key. Copy it." |
| 0:15 | Code editor running a chat completion | "Keep using the official OpenAI SDK." |
| 0:20 | Response headers panel | "Every response carries `CRP-Safety-Hallucination-Risk`, `CRP-Provenance-Window-HMAC`, and `CRP-Agent-Safety-Budget`." |
| 0:25 | Policy editor with `halt-on HIGH` | "Set a safety policy. CRP halts risky calls before they reach your users." |
| 0:28 | CTA | "Deploy in minutes. Audit for life." |

### 2. CRP Comply — "Governance that ships with your code"

**Goal:** Show a public repo being scanned, a SARIF result, and a remediation PR.

| Time | Visual | Script / on-screen text |
|------|--------|------------------------|
| 0:00 | Comply landing page | "CRP Comply turns AI governance into a daily engineering habit." |
| 0:05 | Paste GitHub repo URL | "Paste any public repo." |
| 0:10 | Scan progress + results | "CRP scans for AI-safety risks, data leaks, and compliance gaps." |
| 0:18 | SARIF / report view | "Get a SARIF report mapped to EU AI Act and NIST AI RMF controls." |
| 0:23 | Remediation PR diff | "Open a remediation PR directly from the findings." |
| 0:27 | Billing/plans panel | "Start free, scale when you ship." |

### 3. CRP v4.1 Protocol Demo — "See every signal"

**Goal:** Show the local-LLM demo running through CRP and surfacing every
governance signal.

| Time | Visual | Script / on-screen text |
|------|--------|------------------------|
| 0:00 | Demo UI landing | "CRP v4.1 governs a local model running in LM Studio." |
| 0:05 | Dispatch tab, send "What is CRP?" | "Every call gets a context envelope built from the Context Knowledge Fabric." |
| 0:12 | Metrics: Risk LOW, Quality tier B, Grounding 100% | "Grounded answers score LOW risk and high quality." |
| 0:17 | Send a fabricated query | "Ask something ungrounded…" |
| 0:22 | HTTP 451 halt screen | "…and CRP halts the call before the bad answer is delivered." |
| 0:26 | Active safety tab | "Input validation, injection detection, and PII scanning run on every message." |
| 0:30 | Audit chain tab, tamper button | "Every window is HMAC-chained. Tamper with one, and the chain breaks." |

## Recording conventions

- **Viewport:** 1280×720 for landscape web demos; 390×844 only for mobile snippets.
- **Clip length:** keep each clip under 30 s; concatenate for longer stories.
- **File size:** target ≤ 20 MB per embedded video.
- **Audio:** no narration required; use a music track or captions. If you narrate,
  record separately and mux with ffmpeg.
- **Cursor:** enable Playwright's mouse cursor highlight so viewers can follow clicks.

## Post-processing

```bash
# Trim first/last seconds
ffmpeg -ss 00:00:01 -to 00:00:31 -i output/gateway-demo.webm -c copy output/gateway-demo-trimmed.webm

# Convert to MP4 for broader compatibility
ffmpeg -i output/gateway-demo.webm -c:v libx264 -preset slow -crf 28 -movflags +faststart output/gateway-demo.mp4

# Generate poster frame at 5 s
ffmpeg -i output/gateway-demo.mp4 -ss 00:00:05 -vframes 1 output/gateway-demo-poster.jpg
```

## Publishing (NOT in the production app bundle)

1. Upload `output/*.mp4` and poster JPGs to a CDN or a dedicated demo site.
2. On the production landing page, embed via a CDN URL:

   ```tsx
   <video
     src="https://cdn.crprotocol.io/demos/gateway-demo.mp4"
     poster="https://cdn.crprotocol.io/demos/gateway-demo-poster.jpg"
     autoPlay
     muted
     loop
     playsInline
     className="rounded-xl border border-border shadow-2xl"
   />
   ```

3. Never add videos to `frontend/public/demos/` or `static/demos/` in
   `crp-gateway` or `crp-comply`; that bloats the production build and can leak
   draft/demo content.

## Checklist before publishing

- [ ] All demo-mode bypasses are removed from Gateway/Comply.
- [ ] Videos were recorded against local/dev instances, not production.
- [ ] No real API keys, Stripe secrets, or live credentials appear on screen.
- [ ] PII is fictional (e.g. `alex@example.com`, `+1 555 0100`).
- [ ] Videos are hosted on a CDN, not inside the production repos.
