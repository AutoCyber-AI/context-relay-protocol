# CRP Product Monetisation — Stripe Integration Plan

> **Business**: AutoCyber AI Pty Ltd · ABN 22 697 087 166  
> **Currency**: USD (display) · AUD (settlement)  
> **Auth**: Clerk · **Billing**: Stripe  

---

## Stripe Pricing Models — Which One and Why

Stripe supports these recurring pricing models:

| Model | How It Works | Best For |
|---|---|---|
| **Flat-rate** | Fixed price per billing period (e.g. $39/mo) | Simple SaaS tiers — **this is what we use for base plans** |
| **Per-seat** | Price × number of users (e.g. $10/seat/mo) | Collaboration tools — not us (single-user accounts) |
| **Package** | Price per group of units (e.g. $5 per 1,000 API calls) | Bulk unit pricing — not needed yet |
| **Graduated** | Different price per unit at each tier band | Complex volume discounts — overkill for launch |
| **Volume** | Single unit price based on total quantity | Wholesale discounts — not applicable |
| **Usage-based (metered)** | Charge based on actual consumption via Stripe Meters | API call overages — **future add-on for proxy requests** |
| **Customer chooses price** | Payer decides amount | Donations — not applicable |

### Our Model: **Flat-Rate Recurring** (launch) + **Usage-Based Metered** (future)

**Phase 1 (launch)**: Every paid tier is a **flat-rate recurring monthly subscription**. One fixed price, billed monthly, auto-renews. This is the simplest model — select "Flat-rate pricing" + "Recurring" + "Monthly" in Stripe Dashboard.

**Phase 2 (future)**: Add usage-based metered billing for proxy request overages using Stripe Meters. Customers on Pro who exceed 10,000 requests/mo get charged per additional 1,000 requests.

---

## Product 1: CRP Scribe

### Stripe Product Setup

| Field | Value |
|---|---|
| **Name** | `CRP Scribe` |
| **Description** | `AI-powered document generation for compliance, technical writing, and regulatory documentation. Generate DPIA reports, risk assessments, and technical docs from structured prompts using multiple LLM providers.` |
| **Image** | Upload CRP Scribe logo (JPEG/PNG/WEBP, < 2MB) |
| **Statement descriptor** | `CRPROTOCOL SCRIBE` (≤22 chars, what appears on bank statements) |
| **Unit label** | `workspace` (shows "per workspace" on invoices) |
| **Tax code** | `txcd_10103001` — "Software as a service (SaaS) - business use" |
| **Marketing feature list** | (Visible to customers in Pricing Tables. Add these in order:) |

**Marketing features to add** (click "+ Add feature" for each):

1. `AI-powered document generation`
2. `Multiple LLM providers (OpenAI, Anthropic, Google, Mistral)`
3. `DPIA, risk assessment, and technical doc templates`
4. `Markdown, PDF, and DOCX export`
5. `Version history and document library`
6. `Built on the Context Relay Protocol`

### Prices to Create

#### Free Tier — No Stripe Price Needed

The free tier is enforced in app code when no active subscription exists. No Stripe product/price required.

#### Price 1: Scribe Pro

| Field | Value |
|---|---|
| **Pricing model** | `Flat-rate pricing` |
| **Recurring / One time** | `Recurring` |
| **Amount** | `$39.00` |
| **Currency** | `USD` |
| **Billing period** | `Monthly` |
| **Price description** (internal, customers don't see) | `Scribe Pro — all templates, all LLM providers, 500 generations/mo` |
| **Lookup key** | `scribe_pro_monthly` |

#### Price 2: Scribe Enterprise

| Field | Value |
|---|---|
| **Pricing model** | `Flat-rate pricing` |
| **Recurring / One time** | `Recurring` |
| **Amount** | `$299.00` |
| **Currency** | `USD` |
| **Billing period** | `Monthly` |
| **Price description** (internal) | `Scribe Enterprise — unlimited generations, custom templates, SSO/SAML, dedicated Slack` |
| **Lookup key** | `scribe_enterprise_monthly` |

### Feature Breakdown by Tier

| Feature | Free | Pro ($39/mo) | Enterprise ($299/mo) |
|---|---|---|---|
| Templates | 2 basic | All 5+ templates | All + custom |
| LLM Providers | 1 (OpenAI) | All 4 providers | All + private models |
| Generations/mo | 50 | 500 | Unlimited |
| Max doc length | 5,000 words | 50,000 words | Unlimited |
| Export formats | Markdown | MD, PDF, DOCX | All + API export |
| Version history | 7 days | 90 days | Unlimited |
| Priority support | — | Email | Dedicated Slack |
| Clerk auth | ✓ | ✓ | ✓ + SSO/SAML |

---

## Product 2: CRP Comply

### Stripe Product Setup

| Field | Value |
|---|---|
| **Name** | `CRP Comply` |
| **Description** | `AI governance and EU AI Act compliance platform. OpenAI-compatible proxy with real-time PII scanning, prompt injection detection, HMAC-chained audit trails, GDPR Article 30 processing records, and automated DPIA generation. Built on the Context Relay Protocol.` |
| **Image** | Upload CRP Comply logo (JPEG/PNG/WEBP, < 2MB) |
| **Statement descriptor** | `CRPROTOCOL COMPLY` (≤22 chars) |
| **Unit label** | `organisation` (shows "per organisation" on invoices) |
| **Tax code** | `txcd_10103001` — "Software as a service (SaaS) - business use" |
| **Marketing feature list** | (Visible to customers in Pricing Tables. Add these in order:) |

**Marketing features to add** (click "+ Add feature" for each):

1. `OpenAI-compatible compliance proxy`
2. `Real-time PII scanning (7 categories)`
3. `Prompt injection detection (21 patterns + ML)`
4. `HMAC-chained audit trails`
5. `GDPR Article 30 processing records`
6. `EU AI Act risk classification`
7. `Automated DPIA generation`
8. `Right to erasure (GDPR Article 17)`
9. `Built on the Context Relay Protocol`

### Prices to Create

#### Free Tier — No Stripe Price Needed

Enforced in app code. No Stripe product/price required.

#### Price 1: Comply Pro

| Field | Value |
|---|---|
| **Pricing model** | `Flat-rate pricing` |
| **Recurring / One time** | `Recurring` |
| **Amount** | `$149.00` |
| **Currency** | `USD` |
| **Billing period** | `Monthly` |
| **Price description** (internal) | `Comply Pro — all 7 frameworks, 10K proxy req/mo, full PII scanning, chain verification, GDPR erasure` |
| **Lookup key** | `comply_pro_monthly` |

#### Price 2: Comply Enterprise

| Field | Value |
|---|---|
| **Pricing model** | `Flat-rate pricing` |
| **Recurring / One time** | `Recurring` |
| **Amount** | `$699.00` |
| **Currency** | `USD` |
| **Billing period** | `Monthly` |
| **Price description** (internal) | `Comply Enterprise — 100K proxy req/mo, EU AI Act risk classification, DPIA, regulatory export, RBAC, human oversight` |
| **Lookup key** | `comply_enterprise_monthly` |

#### Price 3: Comply Cloud

| Field | Value |
|---|---|
| **Pricing model** | `Flat-rate pricing` |
| **Recurring / One time** | `Recurring` |
| **Amount** | `$1,999.00` |
| **Currency** | `USD` |
| **Billing period** | `Monthly` |
| **Price description** (internal) | `Comply Cloud — unlimited proxy requests, dedicated infrastructure, 7-year audit retention, 99.95% SLA, dedicated CSM` |
| **Lookup key** | `comply_cloud_monthly` |

### Feature Breakdown by Tier

| Feature | Free | Pro ($149/mo) | Enterprise ($699/mo) | Cloud ($1,999/mo) |
|---|---|---|---|---|
| Frameworks | 2 (EU AI Act, GDPR) | All 7 frameworks | All + custom | All + custom |
| Proxy requests/mo | 100 | 10,000 | 100,000 | Unlimited |
| PII scanning | Basic (CRP PIIScanner) | Full 7-category | Full + custom patterns | Full + ML-enhanced |
| Injection detection | 21 patterns | 21 patterns + alerts | 21 + ML backends | Full CRP stack |
| Audit retention | 7 days | 90 days | 1 year | 7 years |
| GDPR Art. 30 records | ✓ | ✓ | ✓ | ✓ |
| Right to erasure | — | ✓ | ✓ | ✓ |
| Data classification | — | ✓ | ✓ | ✓ |
| Risk classification | — | — | ✓ (EU AI Act Art. 6) | ✓ |
| Chain verification | — | ✓ | ✓ | ✓ |
| Regulatory export | — | — | ✓ | ✓ + automated |
| DPIA generation | — | — | ✓ | ✓ |
| Human oversight | — | — | ✓ | ✓ |
| RBAC | — | — | ✓ | ✓ |
| Dedicated infra | — | — | — | ✓ |
| SLA | — | 99.5% | 99.9% | 99.95% |
| Support | Community | Email | Priority + Slack | Dedicated CSM |

---

## Future: Usage-Based Metered Billing (Phase 2)

For customers who exceed their tier's proxy request allowance, we'll add overage pricing using **Stripe Meters**.

### Stripe Meter Setup ✅ (Created)

| Field | Value |
|---|---|
| **Meter name** | `CRP Comply Proxy Requests` |
| **Event name** | `comply_proxy_requests` |
| **Aggregation method** | `Sum` |
| **Event time window** | `Raw` |
| **Value key override** | `value` |

### Overage Price ✅ (Created)

| Field | Value |
|---|---|
| **Pricing model** | `Usage-based` |
| **Pricing structure** | `Per package` |
| **Amount** | `$0.50` per `1,000` units |
| **Meter** | `CRP Comply Proxy Requests` |
| **Currency** | `USD` |
| **Tax behavior** | `Auto` (include tax in price) |
| **Billing period** | `Monthly` (billed in arrears at end of cycle) |
| **Price description** | `overage price used for exceeding the limit of proxy requests` |
| **Lookup key** | `overage_price` |

### How It Works at Subscription Level

The overage price is added as a **second line item** on the customer's subscription alongside their flat-rate base price. For example, a Pro customer's subscription would have:

| Line Item | Type | Amount |
|---|---|---|
| Comply Pro | Flat-rate, recurring | $149.00/mo |
| Proxy request overage | Usage-based, metered | $0.50 per 1,000 requests (billed in arrears) |

The backend reports usage to Stripe on each proxy request:

```python
import stripe

stripe.billing.MeterEvent.create(
    event_name="comply_proxy_requests",
    payload={
        "value": "1",                    # 1 proxy request
        "stripe_customer_id": "cus_...",  # customer's Stripe ID
    },
)
```

At the end of each billing cycle, Stripe sums all meter events and charges the overage automatically. For example, a Pro customer who made 12,500 requests (2,500 over the 10,000 included) would see a line item for `ceil(2500/1000) × $0.50 = $1.50` overage on their invoice.

> **Note**: The included requests per tier (e.g. 10,000 for Pro) are enforced in app code — only requests *above* the tier allowance should be reported to the meter. Alternatively, report all requests and use Stripe's graduated pricing to make the first N units free.

---

## Stripe Dashboard Step-by-Step Setup

### Step 1: Create Stripe Account

1. Go to [dashboard.stripe.com/register](https://dashboard.stripe.com/register)
2. Business name: **AutoCyber AI Pty Ltd**
3. Country: **Australia**
4. ABN: **22 697 087 166**
5. Toggle **Test mode** (top-right switch)

### Step 2: Create Products

1. Go to **More → Product catalog → + Add product**
2. Create **CRP Scribe** — fill in Name, Description, Image, Statement descriptor, Unit label, Tax code exactly as specified above
3. Add **Price 1** (Pro $39/mo): Select `Flat-rate pricing` → `Recurring` → enter `$39.00 USD` → `Monthly` → set Lookup key → **Add product**
4. Go back to the product → **Pricing section → Add another price**
5. Add **Price 2** (Enterprise $299/mo): same process
6. Repeat for **CRP Comply** with its 3 prices

### Step 3: Copy Price IDs

After creating prices, Stripe assigns IDs like `price_1Abc123...`. Copy these into your `.env`:

```env
# CRP Scribe
STRIPE_SCRIBE_PRO_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_SCRIBE_ENTERPRISE_PRICE_ID=<YOUR_STRIPE_PRICE_ID>

# CRP Comply
STRIPE_COMPLY_PRO_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_ENTERPRISE_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_CLOUD_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
```

### Step 4: Configure Webhooks

1. Go to **Developers → Webhooks → + Add endpoint**
2. Endpoint URL: `https://comply.crprotocol.io/api/v1/billing/webhook`
3. Select events:
   - `checkout.session.completed`
   - `invoice.paid`
   - `invoice.payment_failed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Click **Add endpoint**
5. Copy the **Signing secret** (`<YOUR_STRIPE_WEBHOOK_SECRET>`) → paste into `.env` as `STRIPE_WEBHOOK_SECRET`
6. Repeat for Scribe: `https://scribe.crprotocol.io/api/v1/billing/webhook`

### Step 5: Configure Customer Portal

1. Go to **Settings → Billing → Customer portal**
2. Enable:
   - ✅ Invoices — view and download
   - ✅ Payment methods — update card
   - ✅ Subscriptions — switch plans (list available prices)
   - ✅ Subscriptions — cancel
   - ✅ Receipts — download tax invoices
3. Set **Default return URL**: `https://comply.crprotocol.io/settings`

### Step 6: Configure Tax (Stripe Tax)

1. Go to **Settings → Tax**
2. Set **Origin address**: AutoCyber AI Pty Ltd business address (Australia)
3. Enable **Automatic tax collection**
4. Register for:
   - 🇦🇺 Australia — GST (10%)
   - 🇪🇺 EU — VAT (via One Stop Shop if applicable)
   - 🇺🇸 US — Sales tax (nexus states, if applicable)

### Step 7: Local Testing with Stripe CLI

```bash
# Install Stripe CLI
# macOS: brew install stripe/stripe-cli/stripe
# Windows: scoop install stripe

# Login
stripe login

# Forward webhook events to local backend
stripe listen --forward-to localhost:8400/api/v1/billing/webhook

# Copy the webhook signing secret it prints → put in .env as STRIPE_WEBHOOK_SECRET

# Trigger a test event
stripe trigger checkout.session.completed
```

### Step 8: Go Live

1. Complete Stripe account verification (ID + bank account)
2. In Stripe Dashboard, go to each product → click **Copy to live mode**
3. Update `.env` with live keys:
   - `STRIPE_SECRET_KEY=<YOUR_STRIPE_SECRET_KEY>` (from Developers → API keys)
   - `STRIPE_WEBHOOK_SECRET=<YOUR_STRIPE_WEBHOOK_SECRET>` (from live webhook endpoint)
   - `STRIPE_*_PRICE_ID=<YOUR_STRIPE_PRICE_ID>` (from live product prices)
4. Remove `sk_test_` keys from production

---

## Integration Architecture

### Checkout Flow

```
User clicks "Upgrade to Pro" in app
    │
    ▼
Frontend calls useAuth().getToken() from Clerk
    │
    ▼
POST /api/v1/billing/create-checkout-session
  { price_id: "<YOUR_STRIPE_PRICE_ID>", success_url: "...", cancel_url: "..." }
  Authorization: Bearer <clerk_session_token>
    │
    ▼
Backend creates stripe.checkout.Session.create()
  - mode: "subscription"
  - line_items: [{ price: "<YOUR_STRIPE_PRICE_ID>", quantity: 1 }]
  - customer_email: from Clerk session claims
  - metadata: { crp_user_id: "clerk:user_...", product: "crp-comply" }
    │
    ▼
Backend returns { checkout_url, session_id }
    │
    ▼
Frontend redirects to Stripe-hosted Checkout page
    │
    ▼
Customer enters payment → Stripe processes
    │
    ▼
Success → redirect to success_url
    │
    ▼
Stripe fires webhook: checkout.session.completed
    │
    ▼
POST /api/v1/billing/webhook (signature verified via <YOUR_STRIPE_WEBHOOK_SECRET>)
  → Extract crp_user_id from metadata
  → Retrieve subscription → get price_id → map to tier
  → auth.set_user_tier(user_id, Tier.PRO)
  → Store stripe_customer_id on user record
    │
    ▼
User is now on Pro tier — features unlocked
```

### Key Webhook Events

| Event | Action |
|---|---|
| `checkout.session.completed` | Activate subscription, upgrade tier, store Stripe customer ID |
| `invoice.paid` | Confirm renewal, log successful payment |
| `invoice.payment_failed` | Log warning — Stripe handles retry/dunning automatically (3 retries over ~3 weeks) |
| `customer.subscription.updated` | Handle plan changes (upgrade Pro→Enterprise, downgrade Enterprise→Pro) |
| `customer.subscription.deleted` | Downgrade to FREE tier, remove subscription ID |

### Environment Variables (Backend)

```env
# Stripe
STRIPE_SECRET_KEY=<YOUR_STRIPE_SECRET_KEY>              # From Developers → API keys
STRIPE_WEBHOOK_SECRET=<YOUR_STRIPE_WEBHOOK_SECRET>            # From webhook endpoint signing secret

# CRP Scribe price IDs
STRIPE_SCRIBE_PRO_PRICE_ID=<YOUR_STRIPE_PRICE_ID>       # $39/mo flat-rate recurring
STRIPE_SCRIBE_ENTERPRISE_PRICE_ID=<YOUR_STRIPE_PRICE_ID># $299/mo flat-rate recurring

# CRP Comply price IDs
STRIPE_COMPLY_PRO_PRICE_ID=<YOUR_STRIPE_PRICE_ID>       # $149/mo flat-rate recurring
STRIPE_COMPLY_ENTERPRISE_PRICE_ID=<YOUR_STRIPE_PRICE_ID># $699/mo flat-rate recurring
STRIPE_COMPLY_CLOUD_PRICE_ID=<YOUR_STRIPE_PRICE_ID>     # $1,999/mo flat-rate recurring

# App
CRP_COMPLY_BASE_URL=https://comply.crprotocol.io
```

---

## Pricing Summary — All Products

| Product | Tier | Stripe Pricing Model | Amount | Billing | Lookup Key |
|---|---|---|---|---|---|
| CRP Scribe | Free | — (no Stripe price) | $0 | — | — |
| CRP Scribe | Pro | Flat-rate, Recurring | $39/mo | Monthly | `scribe_pro_monthly` |
| CRP Scribe | Enterprise | Flat-rate, Recurring | $299/mo | Monthly | `scribe_enterprise_monthly` |
| CRP Comply | Free | — (no Stripe price) | $0 | — | — |
| CRP Comply | Pro | Flat-rate, Recurring | $149/mo | Monthly | `comply_pro_monthly` |
| CRP Comply | Enterprise | Flat-rate, Recurring | $699/mo | Monthly | `comply_enterprise_monthly` |
| CRP Comply | Cloud | Flat-rate, Recurring | $1,999/mo | Monthly | `comply_cloud_monthly` |

**Total Stripe objects to create: 2 products, 5 prices.**
