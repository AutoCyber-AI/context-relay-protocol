# CRP Comply Upgrade — Comprehensive Builder Prompt

**To:** the developer upgrading CRP Comply (v3/v2-era → v4) and wiring billing + GitHub
**From:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd
**Read first:** CRP-COMPLY-UPGRADE-HANDOFF.md (the exact live state: IDs, URLs, env vars)
**All specs in:** CRP-COMPLETE-PACKAGE.zip

---

## THE SITUATION (read this first)

CRP Comply is LIVE (comply.crprotocol.io) but built on an early CRP version. Today it:
- audits AI calls but does NOT govern them (no risk gating, no halt, no checkpoints),
- runs on a weak bespoke proxy instead of the CRP Gateway,
- is not connected to CRP Scan,
- uses a basic agent retrieval instead of CRP v4 (CDR/CDGR/CSO/STL).

Your job: upgrade it into a properly-governed, Gateway-backed, Scan-connected,
v4-powered product — WITHOUT breaking the live experience — and finish the billing
and GitHub plumbing. The infrastructure (Stripe catalogue, GitHub App, Clerk, Railway
vars) is already configured by the founder; you build the handlers and the upgrades.

The governing principle, never violate it:
> CRP Core is millisecond, any-model, governance-only. Comply does not reimplement
> CRP — it BECOMES the management + compliance plane over properly-deployed CRP.

---

## THE SPECS THAT MATTER, AND EXACTLY WHAT EACH IS FOR

Build in the phase order below. Each phase names its spec(s) and the work.

### PHASE 0 — Billing plumbing (do first; turns payment into access)
**Specs: SPEC-047 (monetisation/payments). Reference: HANDOFF doc §1,5,6.**
- Build `POST /api/v1/billing/webhook`: verify the Stripe signature with
  `STRIPE_WEBHOOK_SECRET`; on `checkout.session.completed`, read the Checkout
  `metadata` (`clerkUserId` or `clerkOrgId`), map the purchased price ID → plan,
  and write `plan`/`quota`/`features` to the Clerk user OR org publicMetadata via
  `CLERK_SECRET_KEY`. Handle `customer.subscription.updated/deleted`,
  `invoice.payment_failed`. Idempotent (dedupe on event id).
- Build `create-checkout` and `create-portal` routes (SPEC-047 §4.2, §4.6).
- Entitlement is granted ONLY by the verified webhook. The browser success page
  READS entitlement (poll until it flips), never grants it.
- Plan↔price map uses the LIVE ids (HANDOFF §1). Comply is now TWO paid tiers:
  Starter ($49) and Scale ($499). Enterprise = a "Contact sales" link, NOT a checkout.
- Credits: one-time `mode: payment` → increment a prepaid balance; metering draws
  from it past quota (`STRIPE_METER_EVENT_NAME = comply_proxy_requests`).

### PHASE 1 — The Gateway swap (biggest correctness win)
**Specs: SPEC-042 (the migration) + SPEC-016 + CRP-GATEWAY-BLUEPRINT.md.**
- Replace the bespoke proxy: route `comply.crprotocol.io/v1` through the CRP Gateway
  (`CRP_GATEWAY_URL`/`CRP_GATEWAY_KEY`). Preserve the existing `X-CRP-Comply-*` header
  contract so current customers don't break. Audit-only → fully governed.
- This is non-breaking and the highest-value single change. Ship it before the rest.

### PHASE 2 — The safety layer (what Comply is missing entirely)
**Specs: SPEC-005 (DPE), SPEC-006 (Safety Policy), SPEC-033 (Control Plane),
SPEC-034 (checkpoint lifecycle + coverage).**
- Turn on DPE risk scoring, Safety Policy enforcement, HTTP 451 halt on every governed
  call (now that calls go through the Gateway).
- Build the Safety Control Plane in Settings (visual: grounding slider, halt dropdown,
  PII handling, jailbreak/toxicity/secret toggles) — SPEC-033 §2.
- Build the Checkpoint inbox in the existing Inbox surface — SPEC-034 §2 (the
  approve/reject/edit/timeout lifecycle). These produce EU AI Act Art. 14 evidence.

### PHASE 3 — GitHub connection + Scan (the no-code loop)
**Specs: SPEC-048 (no-code + GitHub + signup), SPEC-039 (semantic ingestion),
SPEC-036 (remediation). Guide: CRP-GITHUB-APP-GUIDE.md.**
- Build the GitHub App flow (App ID 3971977): install → record installation_id↔tenant;
  mint short-lived (~1h) tokens per scan; transient clone → scan → delete; never store
  long-lived tokens. Routes: `/api/v1/github/{webhook,callback,installed}`.
- Build "Connect Repo" (SPEC-042 §5): GitHub OAuth OR SARIF upload.
- Scan findings → Inbox remediations (PRs / config) + Programme evidence + score.
- Semantic ingestion (SPEC-039): ingest the repo into a per-tenant code-CKF, trace
  calls through wrappers via CDGR. Remediations are PRs to a dedicated branch only.
- Result-preserving signup (SPEC-048 Part C): anonymous result token → claim on signup;
  pre-auth scans = public repos / uploaded SARIF ONLY (never private pre-auth).

### PHASE 4 — Agent on CRP v4 retrieval (the showcase)
**Specs: SPEC-024 (CDR), SPEC-025 (CDGR), SPEC-030 (CSO), SPEC-031 (STL),
SPEC-009 (CKF). Reference: SPEC-042 §6.**
- Migrate the compliance agent's regulatory-corpus retrieval to v4: CDR (no repetition
  across long deliverables), CDGR (multi-hop across related articles), CSO (coherent
  interview state), STL (positioned generation).
- Re-index the regulatory corpus into a v4 CKF with consistent embeddings (SPEC-027 §2.5).
- The agent IS an Authoritative Domain Agent (SPEC-044) — grounded only in the official
  regulatory corpus, citing articles, refusing to fabricate.

### PHASE 5 — Truly no-code governance translator
**Specs: SPEC-048 Part A, SPEC-044 (ADA), SPEC-037 (unified config).**
- Build the Scan-finding → plain-language → config+code translator: it presents
  applicable governance per finding, captures the user's plain-language intent, and
  translates it into exact CRP config + code. It is an ADA whose corpus is the CRP
  specs — it maps intent only to real capabilities, cites the spec, refuses to invent.
- Output lands in the unified config (SPEC-037) and as a reviewable PR.

---

## SPECS YOU CAN IGNORE FOR THIS WORK
- SPEC-020 (CLD), 021 (ROS), 022 (PEF) — opt-in amplification for weak local models.
  OFF by default, async only, governed by SPEC-023. Do NOT build into Comply now.
- SPEC-018/019 — keep only error-quarantine + failure detection if relevant; not core here.
- Gateway console (SPEC-043), Scan/Gateway pricing (their own apps) — separate products.

---

## REFERENCE DOCS (what to open when)
| Doc | Use it for |
|-----|-----------|
| **CRP-COMPLY-UPGRADE-HANDOFF.md** | the exact live state — every ID, URL, env var, route |
| **CRP-V4-UPGRADE-PROMPT.md** | the protocol-level v3→v4 build plan + invariants |
| **CRP-GITHUB-APP-GUIDE.md** | the GitHub App implementation (code) |
| **CRP-STRIPE-SETUP-GUIDE.md** | all live price IDs + payment links |
| SPEC-040 | what CRP Comply IS (the 3-layer product, aligned to live) |
| SPEC-042 | THE migration (proxy→Gateway, safety, Scan connect, agent v4) |
| SPEC-047 | billing code (webhook, checkout, entitlement) |
| SPEC-048 | no-code governance + GitHub + result-preserving signup |
| SPEC-033/034 | the safety control plane + checkpoints |
| SPEC-039 | semantic codebase scanning |
| SPEC-044 | the agent/translator as an Authoritative Domain Agent |

---

## NON-NEGOTIABLE INVARIANTS
1. Entitlement granted ONLY by the verified Stripe webhook (never client-side).
2. Verify every webhook signature (Stripe + GitHub) before acting.
3. Preserve the `X-CRP-Comply-*` header contract during the Gateway swap (no breakage).
4. Never store long-lived GitHub tokens; mint short-lived per scan.
5. Private-repo scanning requires auth; anonymous scans = public/SARIF only.
6. Remediations are PRs to a dedicated branch — never direct commits / protected branches.
7. Comply does not run its own runtime — it routes through the Gateway.
8. The translator/agent only maps to REAL CRP capabilities; never fabricates governance.

---

## DEFINITION OF DONE
- A user can pay (Starter/Scale/credits) and be unlocked automatically via the webhook.
- Every governed call goes through the Gateway with DPE + Safety Policy + halt + audit.
- A user can connect a GitHub repo (or upload SARIF), see findings, and apply fixes.
- The agent answers from the regulatory corpus with citations, on v4 retrieval.
- A user can set governance visually (no code) and it translates to real config + a PR.
- Tested end-to-end in Stripe TEST mode before relying on live.

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · comply.crprotocol.io*
