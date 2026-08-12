# CRP Gateway — Product Overview: Frontend, Backend & Every Page

**For:** the team building CRP Gateway (frontend + backend)
**From:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd
**Companion to:** SPEC-016 (service), SPEC-043 (runtime product + console), CRP-GATEWAY-BLUEPRINT.md
**Purpose:** define what the Gateway IS as a complete product — every web page, its look,
its interactivity, and how each connects to the backend — so it is user-friendly and well designed.

---

## 1. WHAT CRP GATEWAY IS (one screen)

The CRP Gateway is **the governed AI platform** — a managed, hosted, subscription
service where a developer or company points their application at the Gateway and
every LLM call is governed (safety, provenance, compliance signals) plus they get
the full context-management suite (CDR, CDGR, CSO, STL, knowledge, sessions, tools)
— accessed both by **API** and by a **low-code/no-code visual console**.

```
            ┌────────────────────────────────────────────────┐
  USER APP ─┤  api.gateway.crprotocol.io/v1  (OpenAI-compat)  ├─► LLM PROVIDER
            └───────────────┬────────────────────────────────┘
                            │ every call: govern + context + audit
            ┌───────────────▼────────────────────────────────┐
            │  gateway.crprotocol.io  (the CONSOLE — this doc) │
            │  build · test · configure · monitor · deploy     │
            └──────────────────────────────────────────────────┘
```

Two faces of one product: the **runtime API** (machines call it) and the **console**
(humans use it). This document specifies the console (the frontend) and how each page
talks to the backend.

---

## 2. THE AESTHETIC DIRECTION (so it's not generic)

A governed-AI platform should feel **precise, trustworthy, and technical-but-calm** —
the opposite of playful. The committed direction:

- **Tone:** industrial-precision meets editorial clarity. Think a control room that a
  serious engineer trusts, not a consumer toy. Confident, quiet, exact.
- **Theme:** dark-first (a control surface), with an optional light mode. Deep near-black
  canvas (#0a0b0d), one decisive accent — a signal green/lime (#c8f04a-ish, the CRP mark)
  used sparingly for "governed / active / safe", and a warm amber + red reserved strictly
  for risk states. Color carries *meaning* here, never decoration.
- **Typography:** a distinctive technical display face for headings (e.g. a grotesque with
  character — not Inter/Roboto) paired with a highly legible mono for all IDs, headers,
  code, and metrics (governance is full of hashes, header names, scores — mono makes them
  scannable). Body in a refined humanist sans.
- **Motion:** restrained and meaningful. A governed call "passing through" animates as a
  brief signal sweep; a halt snaps red. One orchestrated load reveal per page, not scattered
  fidget. Motion communicates *state*, never fills space.
- **Texture:** subtle grain on the canvas + fine 1px hairline borders (a measured,
  instrument-panel feel). Generous negative space around dense data.
- **The one memorable thing:** every governed call is visibly *alive* — the console shows
  governance happening (risk, grounding, halt) as a living signal, turning invisible
  protection into something you can watch and trust.

This direction must be consistent across every page below.

---

## 3. THE FRONTEND ↔ BACKEND ARCHITECTURE

```
FRONTEND (gateway.crprotocol.io)            BACKEND
─────────────────────────────────          ─────────────────────────────────
React/Next console                          FastAPI/Python Gateway service
  Clerk auth (clerk.crprotocol.io)   ◄────►   verifies Clerk JWT (CLERK_ISSUER)
  calls the Gateway control API      ◄────►   /api/v1/* control plane
  renders governance signals         ◄────►   reads DPE/audit/usage from stores
  Stripe Checkout redirects          ◄────►   /api/v1/billing/* + webhook
                                              ┌──────────────────────────────┐
                                              │ Postgres (tenants, keys,      │
                                              │   pipelines, usage, audit)    │
                                              │ Redis (sessions, hot cache,   │
                                              │   rate limits)                │
                                              │ CKF stores (per-tenant)       │
                                              └──────────────────────────────┘
  THE RUNTIME (separate from console):
    api.gateway.crprotocol.io/v1  → the 22-step lifecycle (BLUEPRINT §1)
```

Two backend surfaces: the **runtime** (`/v1/*`, OpenAI-compatible, what apps call) and
the **control API** (`/api/v1/*`, what the console calls). The console never proxies LLM
traffic; it configures and observes. Auth on both is the shared Clerk JWT; entitlement is
read from the Clerk org metadata (per SPEC-047).

---

## 4. EVERY PAGE — LOOK, INTERACTIVITY, BACKEND WIRING

The console is the authenticated app at `gateway.crprotocol.io/app`. Pages:

### 4.0 Marketing / Landing (public, gateway.crprotocol.io)
- **Look:** dark hero, the living-signal motif (a call flowing through governance), one
  bold line — "The governed AI platform. Every call safe, grounded, and provable." A code
  snippet showing the one-line base_url swap. Pricing teaser → the three tiers.
- **Interactivity:** an animated demo of a call being governed (risk score appearing,
  a halt firing). "Start free" → Clerk signup. "View docs."
- **Backend:** static / none (marketing). CTA → Clerk signup flow.

### 4.1 Onboarding (first run after signup)
- **Look:** a calm, stepped flow on the dark canvas — 4 steps, a progress rail on the left.
- **Steps:** (1) name your first AI system; (2) choose a provider (paste a key, vaulted
  encrypted — with the "your keys, encrypted, never logged" reassurance; or pick local/BYO);
  (3) copy your one-line integration snippet (with a live "waiting for your first call…"
  indicator that turns green when it arrives); (4) "you're governed" confirmation.
- **Interactivity:** the snippet has a copy button; the page live-polls for the first call
  and celebrates when it lands (the memorable activation moment).
- **Backend:** `POST /api/v1/systems` (create system), `POST /api/v1/keys` (vault the
  provider key, AES-256-GCM), websocket/poll `/api/v1/systems/{id}/first-call`.

### 4.2 Dashboard (the home — the control room)
- **Look:** the instrument panel. Top row of large mono metrics: calls today, avg risk,
  grounding %, halts, fabrications caught, est. token savings. A live "recent calls" stream
  where each row shows model, risk chip (green/amber/red), grounding, latency — updating in
  real time with the signal-sweep motion. A quality-trend sparkline.
- **Interactivity:** click any call → a drawer with its full governance detail (DPE report,
  CSO, headers, sources). Filter by system/risk. The live stream can pause/resume.
- **Backend:** `GET /api/v1/metrics/summary`, `GET /api/v1/calls?filters`, websocket
  `/api/v1/calls/stream`, `GET /api/v1/calls/{id}` for the drawer.

### 4.3 Pipelines (the low-code/no-code builder — the differentiator)
- **Look:** a canvas. Capability blocks dragged from a left palette onto a flow:
  [Input] → [Knowledge ▾] → [Depth ▾] → [Safety ▾] → [Checkpoint ▾] → [Tools ▾] →
  [Model ▾] → [Output]. Each block is a clean card with its setting inline. Connections
  are drawn as the signal line. The whole thing feels like wiring an instrument, precise
  and snapping to a grid.
- **Interactivity:** drag to add, click a block to expand its settings (a side panel),
  connect blocks, reorder. A "Test" button opens the playground (4.4) with this pipeline.
  "Deploy as endpoint" (paywalled trigger). "Export as code" generates the SDK/config
  (SPEC-037) in a modal with copy. Pipelines are saved, named, versioned.
- **Backend:** `GET/POST/PUT /api/v1/pipelines`, `POST /api/v1/pipelines/{id}/deploy`
  (returns a live endpoint URL + key), `GET /api/v1/pipelines/{id}/export` (code/config).
  The pipeline is stored as the unified config (SPEC-037); deploy provisions a governed
  endpoint backed by the runtime.

### 4.4 Playground (test a configured pipeline live)
- **Look:** split view — left, a prompt input + the active pipeline shown as a compact rail;
  right, the streamed response WITH a live governance panel beneath it (risk, grounding,
  sources, any halt, the operation sequence if STL is on). The governance panel is the star:
  you watch protection happen.
- **Interactivity:** type a prompt, run, watch the response stream and the governance
  signals populate. Toggle settings (depth, safety) and re-run to see the difference.
  "Save these settings to the pipeline."
- **Backend:** `POST /api/v1/playground/run` (runs through the real runtime with the
  pipeline config, streams tokens + governance events). Same lifecycle as production,
  flagged as a test (not billed against quota, or lightly).

### 4.5 Knowledge (the CKF manager)
- **Look:** a library view. Ingested sources as cards (title, type, fact count, freshness).
  A "what your AI knows" search box that surfaces facts. A storage-location indicator
  (SPEC-038) showing where the CKF lives (native / pgvector / your store).
- **Interactivity:** drag-drop or pick files / paste URLs / paste text to ingest (one
  forgiving control). Search to browse facts. Delete a source (GDPR erasure). Set storage
  backend. See ingestion progress.
- **Backend:** `POST /api/v1/knowledge/ingest`, `GET /api/v1/knowledge/search`,
  `DELETE /api/v1/knowledge/sources/{id}`, `GET /api/v1/knowledge/location`,
  `GET /api/v1/knowledge/stats`.

### 4.6 Safety (the visual Safety Control Plane — SPEC-033)
- **Look:** the governance cockpit. A protection-level selector (Relaxed / Balanced /
  Strict / Custom) as large segmented control. Below, fine-tune controls: grounding slider,
  halt-level dropdown, PII handling, jailbreak/toxicity/secret toggles — each with a one-line
  "what this does" + the regulation it serves. A checkpoints section with a visual builder.
- **Interactivity:** one click sets a preset; sliders/toggles for fine-tuning; "+ Add
  checkpoint" builds a condition→route rule from dropdowns. A live "test against a sample"
  panel. Every change saves to config and is audited.
- **Backend:** `GET/PUT /api/v1/safety/config` (writes the SafetyManifest / unified config),
  `GET /api/v1/safety/registry` (the catalogue), `POST /api/v1/safety/test`.

### 4.7 Analytics (observability — make the invisible visible)
- **Look:** charts with the instrument aesthetic. Calls over time, risk distribution,
  grounding trend, fabrications caught (the value chart), token savings from positioning,
  cost. Per-system breakdown.
- **Interactivity:** date-range, per-system filter, export CSV. Click a data point → the
  calls behind it.
- **Backend:** `GET /api/v1/analytics?range&system&metric`.

### 4.8 Settings → Systems & Keys
- **Look:** list of AI systems; per system, its provider, vaulted key status, EU AI Act
  classification, policy. Provider key management (vaulted / BYOK).
- **Interactivity:** add/edit a system, rotate a key, set per-system safety override.
- **Backend:** `/api/v1/systems`, `/api/v1/keys` (encrypted), `/api/v1/systems/{id}/policy`.

### 4.9 Settings → Billing & Usage
- **Look:** current plan (Free/Developer/Team), usage vs quota (a clear gauge), upgrade
  cards for the tiers, invoices, manage-subscription button.
- **Interactivity:** "Upgrade" → Stripe Checkout (the right price ID, returns to here
  unlocked). "Manage" → Stripe Customer Portal. Usage gauge live.
- **Backend:** `POST /api/v1/billing/create-checkout`, `POST /api/v1/billing/create-portal`,
  `GET /api/v1/billing/usage`. Entitlement read from Clerk org metadata (SPEC-047);
  granted by the verified webhook only.

### 4.10 Settings → API Keys & Team
- **Look:** the tenant's CRP Gateway API keys (create/revoke), team members (Clerk org),
  roles, SSO (on Team+).
- **Interactivity:** create/name/revoke a Gateway key, invite members, set roles.
- **Backend:** `/api/v1/keys`, Clerk org membership APIs.

### 4.11 Docs / Integration (in-console reference)
- **Look:** the one-line snippet front and center, per-framework tabs (OpenAI SDK,
  LangChain, etc.), the governance-header reference, links to full docs.
- **Interactivity:** copy snippets; "test this snippet" → playground.
- **Backend:** static + deep links.

---

## 5. THE NAVIGATION & SHELL

- **Left rail (collapsible):** Dashboard · Pipelines · Playground · Knowledge · Safety ·
  Analytics · Settings. Mono labels, the accent marking the active item.
- **Top bar:** system switcher (which AI system you're viewing), environment (live/test),
  the live "governance active" pulse, account menu (Clerk).
- **Global:** dark/light toggle, command palette (⌘K) to jump anywhere, consistent drawer
  pattern for detail views.

---

## 6. RESPONSIVE & ACCESSIBILITY
- Desktop-first (it's a control console) but the Dashboard, Playground, Safety, and Billing
  must work on tablet/mobile for on-the-go checks. The Pipeline builder is desktop-primary
  with a read-only mobile view.
- Risk states never rely on color alone — always a label/icon too (accessibility + clarity).
- Keyboard navigable; mono metrics have sufficient contrast on the dark canvas.

---

## 7. THE CONNECTING PRINCIPLE
Every page does one of: **configure** the runtime (Pipelines, Safety, Knowledge, Systems),
**observe** it (Dashboard, Analytics, Playground), or **manage** the account (Billing, Team).
The runtime is the engine; the console is the cockpit. The frontend never carries LLM
traffic — it reads governance state from the backend and writes config to it. That clean
split (runtime API vs control API, both Clerk-authed) is what keeps the product fast,
secure, and coherent.

---

## 8. BUILD NOTES
- Frontend: React/Next + Clerk; Stripe via redirect (no card handling in-app); websockets
  for the live call stream and playground.
- Backend control API separate from the runtime path (don't let console load touch the
  <50ms governed-call budget).
- All visual governance signals come from the DPE report + audit chain the runtime already
  produces (BLUEPRINT) — the console renders them, it doesn't compute them.
- Match implementation effort to the aesthetic: the living-signal motif and the playground
  governance panel are the high-impact moments worth polishing most.

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · gateway.crprotocol.io*
