# CRP Comply — Final State & Upgrade Handoff (for the Developer)

**For:** the developer performing the CRP Comply v3→v4 upgrade + GitHub App + billing
**From:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd
**Status:** infrastructure configured by the founder; handlers + upgrade to be built
**Read alongside:** CRP-V4-UPGRADE-PROMPT.md, SPEC-042, SPEC-047, SPEC-048, CRP-GITHUB-APP-GUIDE.md

---

## 0. WHAT THIS DOCUMENT IS

The single source of truth for the *current live state* of CRP Comply's billing,
auth, and integration infrastructure — every ID, URL, credential name, and the
exact work remaining. Everything below marked ✓ is already configured. Everything
marked ▢ is yours to build.

---

## 1. THE LIVE STRIPE CATALOGUE (final — Path B, old products archived)

Account: **AutoCyber AI** `acct_1TLbVkGRBK524I7z` · USD · 7 active products, 2 archived.

### Comply (the product this app sells)
| Tier | Amount | Price ID |
|------|--------|----------|
| Starter monthly | $49/mo | `price_1Te0k1GRBK524I7zrLssfPVt` |
| Starter annual | $490/yr | `price_1Te0k5GRBK524I7zgWdvIRLy` |
| Scale monthly | $499/mo | `price_1Te0kDGRBK524I7z8zwCrNUD` |
| Scale annual | $4,990/yr | `price_1Te0kGGRBK524I7zQcnbPrPY` |
| Credits $5 | one-time | `price_1Te0kOGRBK524I7z8OmtD5Lp` |
| Credits $20 | one-time | `price_1Te0kRGRBK524I7zMOvbrXW5` |
| Credits $50 | one-time | `price_1Te0kUGRBK524I7zTccpMVZc` |

Products: Starter `prod_UdHIRpesJB0WFu` · Scale `prod_UdHIYA1Wd8li76` · Credits `prod_UdHI25gm6SNnIp`

### Comply tier model (IMPORTANT — changed from 3 tiers to 2)
- **Free** ($0): 100 audited calls/mo, local-LLM, local storage, 1 system.
- **Starter** ($49/mo): unlimited systems, hosted vault, checkpoint inbox, evidence
  generation + pack export, Scan remediations, 90-day retention.
- **Scale** ($499/mo): + SSO, multi-team, data residency, custom rules, hosted LLM,
  1-yr retention, priority support.
- **Enterprise**: SALES-LED, no Stripe price. A "Contact sales" link, NOT a checkout.

> CODE CHANGE: the old app used STARTER / PROFESSIONAL / ENTERPRISE (3 tiers).
> Now: STARTER = Starter, PROFESSIONAL var = Scale, ENTERPRISE = contact-sales link.
> Remove any checkout path that charges an Enterprise price.

### Other products (live, for their own apps — not this one)
- Scan Pro `prod_UdHJBTmWYH1f99` $29/repo · Business `prod_UdHJyQYThV1Qgg` $299
- Gateway Developer `prod_UdHJhh55IaExpq` $29 (annual `...kz`) · Team `prod_UdHJVfhfLrueep` $199 (annual `...lA`)

### Archived (do NOT use — kept for history only)
- old "CRP Comply" `prod_UL8XDrEL7YAtjW` (held TQH/TSB/TMS prices)
- "CRP Scribe" `prod_UL8RONclbba9Ow`

---

## 2. STRIPE DASHBOARD STATE ✓ (all configured)

- ✓ Webhook endpoint: `https://comply.crprotocol.io/api/v1/billing/webhook`
  events: `checkout.session.completed`, `customer.subscription.updated`,
  `customer.subscription.deleted`, `invoice.payment_failed`, `invoice.paid`,
  `payment_intent.succeeded`. Signing secret → `STRIPE_WEBHOOK_SECRET`.
- ✓ Customer Portal: Starter + Scale eligible; prorate on change; downgrade at period end.
- ✓ Payment methods: cards, Apple/Google Pay, Link, Klarna, Zip, Pix, etc.
- ✓ Branding configured.
- ▢ TODO: confirm Stripe Tax (AU GST + EU VAT, origin Sydney) if charging tax.

---

## 3. GITHUB APP STATE ✓ (created)

- ✓ App ID: **3971977**
- ✓ Client ID: **Iv23liT20jEe4rCyvTRv**
- ✓ Client secret: generated → `GITHUB_APP_CLIENT_SECRET`
- ✓ Private key (.pem): generated → `GITHUB_APP_PRIVATE_KEY` (full PEM incl. BEGIN/END lines)
- ✓ Webhook secret: configured → `GITHUB_APP_WEBHOOK_SECRET`
- ▢ Set in the GitHub App config (confirm these URLs match the routes you build):
  - Webhook URL: `https://comply.crprotocol.io/api/v1/github/webhook`
  - Callback URL: `https://comply.crprotocol.io/api/v1/github/callback`
  - Setup URL (optional): `https://comply.crprotocol.io/api/v1/github/installed`
- ▢ Permissions to confirm: Contents **Read-only**, Metadata **Read-only**
  (Pull requests Read-write ONLY if auto-PR remediation is enabled).
- ▢ Events subscribed: **Push**, **Pull request** (installation events arrive automatically).
- ▢ Installable on: **Any account**.

### PRIVATE KEY FORMAT (critical)
`GITHUB_APP_PRIVATE_KEY` MUST include the full PEM:
```
<YOUR_GITHUB_APP_PRIVATE_KEY_PEM>
```
If stored single-line with `\n`, the code must do `key.replace('\\n','\n')` before
signing the JWT (RS256). Without BEGIN/END, JWT signing fails.

---

## 4. CLERK STATE

- ✓ Frontend API: `https://clerk.comply.crprotocol.io`
- ✓ Organizations enabled, "Membership optional" (solo users allowed)
- ✓ Publishable key → `VITE_CLERK_PUBLISHABLE_KEY`
- ✓ Secret key exists in Clerk ("default") — API version 2025-11-10
- ▢ **MISSING IN RAILWAY: `CLERK_SECRET_KEY`** (the `sk_...` "default" secret key).
  The backend webhook handler CANNOT write entitlement without it. ADD THIS.

### Entitlement model (personal OR org, because membership is optional)
- Personal account → entitlement on the Clerk **user** publicMetadata.
- Team account → entitlement on the Clerk **organization** publicMetadata.
- Checkout metadata carries whichever applies: `clerkUserId` OR `clerkOrgId`.
- The webhook reads it and writes plan/quota/features to that user or org.

---

## 5. RAILWAY VARIABLES — FINAL REQUIRED SET

### ✓ Present and correct
```
CRP_COMPLY_RAG_BOOTSTRAP, CRP_COMPLY_SEARCH_API_KEY, CRP_COMPLY_SEARCH_URL
CRP_COMPLY_LLM_API_KEY, CRP_COMPLY_LLM_BASE_URL, CRP_COMPLY_LLM_MODEL
RESEND_API_KEY
GITHUB_APP_ID, GITHUB_APP_CLIENT_ID, GITHUB_APP_CLIENT_SECRET,
GITHUB_APP_PRIVATE_KEY, GITHUB_APP_WEBHOOK_SECRET
STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_METER_EVENT_NAME
STRIPE_COMPLY_STARTER_PRICE_ID, STRIPE_COMPLY_PROFESSIONAL_PRICE_ID (= Scale),
STRIPE_COMPLY_CREDITS_5_PRICE_ID, _20_, _50_
VITE_CLERK_PUBLISHABLE_KEY
```

### ▢ MUST ADD
```
CLERK_SECRET_KEY=<YOUR_CLERK_SECRET_KEY>   (CRITICAL — backend entitlement)
STRIPE_COMPLY_STARTER_ANNUAL_PRICE_ID   = price_1Te0k5GRBK524I7zgWdvIRLy
STRIPE_COMPLY_SCALE_ANNUAL_PRICE_ID     = price_1Te0kGGRBK524I7zQcnbPrPY
```

### ▢ VERIFY THE VALUES (names already exist — confirm they point to NEW IDs)
```
STRIPE_COMPLY_STARTER_PRICE_ID       → price_1Te0k1GRBK524I7zrLssfPVt   ($49/mo)
STRIPE_COMPLY_PROFESSIONAL_PRICE_ID  → price_1Te0kDGRBK524I7z8zwCrNUD   ($499/mo Scale)
STRIPE_COMPLY_CREDITS_5_PRICE_ID     → price_1Te0kOGRBK524I7z8OmtD5Lp
STRIPE_COMPLY_CREDITS_20_PRICE_ID    → price_1Te0kRGRBK524I7zMOvbrXW5
STRIPE_COMPLY_CREDITS_50_PRICE_ID    → price_1Te0kUGRBK524I7zTccpMVZc
```
> NAMING NOTE: `PROFESSIONAL` now means **Scale**. Consider adding a clear alias
> `STRIPE_COMPLY_SCALE_PRICE_ID` pointing at the same ID to avoid a wrong-charge bug.

### ▢ NEEDED FOR THE v4 UPGRADE (add when building SPEC-042)
```
APP_BASE_URL            = https://comply.crprotocol.io   (Checkout success/cancel, GH callback)
CRP_GATEWAY_URL         = <the CRP Gateway endpoint>      (when proxy → Gateway, SPEC-042)
CRP_GATEWAY_KEY         = <gateway api key>
```

---

## 6. THE ROUTES YOU MUST BUILD (URLs point here; handlers don't exist yet)

| Route | Purpose | Spec |
|-------|---------|------|
| `POST /api/v1/billing/webhook` | Stripe events → verify sig → write entitlement to Clerk | SPEC-047 §4 |
| `POST /api/v1/billing/create-checkout` | create Checkout Session (sub or credits) | SPEC-047 §4.2 |
| `POST /api/v1/billing/create-portal` | open Customer Portal | SPEC-047 §4.6 |
| `POST /api/v1/github/webhook` | GitHub push/PR/installation → verify sig → re-scan | GH-APP-GUIDE §7 |
| `GET  /api/v1/github/callback` | OAuth identify after authorize | GH-APP-GUIDE §2 |
| `GET  /api/v1/github/installed` | post-install setup → record installation_id ↔ tenant | GH-APP-GUIDE §2 |

The dashboards/App config POST to these URLs. The URLs are NOT env vars — they are
routes in this application. The SECRETS that verify them ARE env vars
(`STRIPE_WEBHOOK_SECRET`, `GITHUB_APP_WEBHOOK_SECRET`).

---

## 7. THE BUILD WORK (in order)

### Phase 0 — Billing plumbing (do first; unlocks revenue)
1. Build `POST /api/v1/billing/webhook` (SPEC-047 §4): verify Stripe signature with
   `STRIPE_WEBHOOK_SECRET`; on `checkout.session.completed` read metadata
   (`clerkUserId`/`clerkOrgId`), look up the plan from the price ID, write
   plan/quota/features to Clerk metadata via `CLERK_SECRET_KEY`. Idempotent (dedupe
   on event id). Entitlement granted ONLY here, never client-side.
2. Build create-checkout + create-portal routes. success_url returns to the exact
   surface; metadata carries the Clerk user/org id.
3. Map price IDs → plans (SPEC-047 §4.4). Remember PROFESSIONAL var = Scale.
4. Reconcile job: nightly compare Stripe subs ↔ Clerk entitlement (catch missed webhooks).

### Phase 1 — Comply v2→v4: Gateway swap (SPEC-042, biggest correctness win)
5. Replace the bespoke proxy: route `comply.crprotocol.io/v1` through the CRP Gateway
   (`CRP_GATEWAY_URL`). Preserve the `X-CRP-Comply-*` header contract. Audit-only →
   fully governed, no customer breakage.

### Phase 2 — Safety layer (SPEC-033/034)
6. Activate DPE risk scoring, Safety Policy, halt. Surface the Safety Control Plane in
   Settings. Populate the Inbox with checkpoints.

### Phase 3 — GitHub connection + Scan (SPEC-048, GH-APP-GUIDE, SPEC-039)
7. Build the install flow, short-lived token minting, transient clone→scan→delete,
   the GitHub webhook handler. Connect Repo surface. Result-preserving signup (anon
   token → claim on signup; public-repo/SARIF only pre-auth).

### Phase 4 — Agent on v4 retrieval (SPEC-042 §6)
8. Migrate the agent's corpus retrieval to CDR/CDGR/CSO/STL; re-index the regulatory
   corpus into a v4 CKF (consistent embeddings).

### Phase 5 — No-code governance translator (SPEC-048 Part A)
9. The Scan-finding → plain-language → config+code translator (an ADA over the CRP specs).

---

## 8. SECURITY INVARIANTS (do not violate)
- Entitlement granted ONLY by the verified webhook. The browser success page READS
  entitlement, never grants it.
- Never store long-lived GitHub tokens — mint short-lived (~1h) per scan, discard.
- GitHub private key in env/secrets only; full PEM incl. BEGIN/END.
- Private-repo scanning requires the authenticated GitHub App; anonymous/pre-signup
  scans = public repos or user-uploaded SARIF ONLY.
- Remediations are PRs to a dedicated branch — never direct commits, never protected branches.
- Verify every webhook signature (Stripe + GitHub) before acting.

---

## 9. QUICK VERIFICATION CHECKLIST
```
[ ] CLERK_SECRET_KEY added to Railway
[ ] Two annual price-ID vars added
[ ] Existing Stripe price vars verified against the NEW Te0k... IDs
[ ] GitHub App: permissions (Contents/Metadata read), events (push/PR), Any account
[ ] GitHub App: webhook + callback URLs match the routes built
[ ] GITHUB_APP_PRIVATE_KEY includes BEGIN/END PEM lines
[ ] App code: Enterprise = contact-sales link, not a checkout
[ ] App code: PROFESSIONAL var understood as Scale tier
[ ] Stripe webhook handler built + signature-verified + idempotent
[ ] GitHub webhook handler built + signature-verified
[ ] Tested full loop in Stripe TEST mode before relying on live
```

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · comply.crprotocol.io*
