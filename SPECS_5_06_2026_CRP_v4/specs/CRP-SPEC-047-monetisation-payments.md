# CRP-SPEC-047: Monetisation, Payments & Clerk–Stripe Account Linkage

**Document:** CRP-SPEC-047  
**Title:** Context Relay Protocol (CRP) — Complete Monetisation, Payment Tracking, Verification & Clerk–Stripe Account Linkage  
**Version:** 2.0.0 — LIVE Stripe objects + Clerk integration  
**Status:** Foundational — Revenue-Critical, Implementation-Ready  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Stripe account:** AutoCyber AI (acct_1TLbVkGRBK524I7z) · USD · LIVE  
**Auth provider:** Clerk (organizations-based B2B)  
**Prerequisites:** CRP-SPEC-040, 042, 043, 036

---

## Abstract

This document is the complete, implementation-ready specification for monetising the three CRP products. It contains every live Stripe object ID, the full Clerk–Stripe account-linkage architecture, the payment-tracking and verification flow, and the code (TypeScript for the Clerk-native auth/entitlement layer; Python for CRP's own backend services). The design goal is a seamless, professional payment experience where every payment is tracked, verified, and correctly linked to the paying account, and where entitlement (what a customer can use) is always an accurate reflection of what they have paid for. All Stripe products, prices, and payment links referenced are live on the AutoCyber AI account. Authentication and account modelling use Clerk organizations; Stripe is linked to Clerk so that a subscription is owned by a Clerk organization and entitlement is stored on that organization, verified by signed webhooks.

---

## 1. Complete Live Stripe Object Reference

Every object below is LIVE on `acct_1TLbVkGRBK524I7z`.

### 1.1 CRP Comply

| Plan | Amount | Product ID | Price ID | Payment Link |
|------|--------|-----------|----------|--------------|
| Starter monthly | $49/mo | `prod_UdHIRpesJB0WFu` | `price_1Te0k1GRBK524I7zrLssfPVt` | https://buy.stripe.com/fZu00j3WsfIJbKy0uvffy00 |
| Starter annual | $490/yr | `prod_UdHIRpesJB0WFu` | `price_1Te0k5GRBK524I7zgWdvIRLy` | https://buy.stripe.com/3cI3cveB64016qeb99ffy05 |
| Scale monthly | $499/mo | `prod_UdHIYA1Wd8li76` | `price_1Te0kDGRBK524I7z8zwCrNUD` | https://buy.stripe.com/aFaaEXgJefIJaGu0uvffy01 |
| Scale annual | $4,990/yr | `prod_UdHIYA1Wd8li76` | `price_1Te0kGGRBK524I7zQcnbPrPY` | https://buy.stripe.com/9B64gz50w2VXbKy6STffy06 |
| Credits $5 | one-time | `prod_UdHI25gm6SNnIp` | `price_1Te0kOGRBK524I7z8OmtD5Lp` | https://buy.stripe.com/dRm28r64A1RT29Yb99ffy0a |
| Credits $20 | one-time | `prod_UdHI25gm6SNnIp` | `price_1Te0kRGRBK524I7zMOvbrXW5` | https://buy.stripe.com/8x23cv1Okbst6qea55ffy0b |
| Credits $50 | one-time | `prod_UdHI25gm6SNnIp` | `price_1Te0kUGRBK524I7zTccpMVZc` | https://buy.stripe.com/4gM5kD0KgeEF4i6a55ffy0c |

### 1.2 CRP Scan

| Plan | Amount | Product ID | Price ID | Payment Link |
|------|--------|-----------|----------|--------------|
| Pro (per repo) | $29/repo/mo | `prod_UdHJBTmWYH1f99` | `price_1Te0kfGRBK524I7zrMHu3BXL` | https://buy.stripe.com/00wdR98cI2VX9Cqcddffy02 |
| Business | $299/mo | `prod_UdHJyQYThV1Qgg` | `price_1Te0kmGRBK524I7zBKcUu6h6` | https://buy.stripe.com/14A6oHakQ68901Qa55ffy07 |

### 1.3 CRP Gateway

| Plan | Amount | Product ID | Price ID | Payment Link |
|------|--------|-----------|----------|--------------|
| Developer monthly | $29/mo | `prod_UdHJhh55IaExpq` | `price_1Te0kvGRBK524I7zbhruWdHb` | https://buy.stripe.com/28EdR9boU6896qe1yzffy03 |
| Developer annual | $290/yr | `prod_UdHJhh55IaExpq` | `price_1Te0kzGRBK524I7zZMQ4r1G7` | https://buy.stripe.com/bJe9ATakQgMNaGu3GHffy08 |
| Team monthly | $199/mo | `prod_UdHJVfhfLrueep` | `price_1Te0l6GRBK524I7zk7qU16TX` | https://buy.stripe.com/dRm7sLgJe1RTbKy1yzffy04 |
| Team annual | $1,990/yr | `prod_UdHJVfhfLrueep` | `price_1Te0lAGRBK524I7zac5aYFPK` | https://buy.stripe.com/9B63cv50w2VXg0O2CDffy09 |

### 1.4 Price ID Constants (for the codebase)

```typescript
// crp-pricing.ts — single source of truth for price IDs
export const PRICES = {
  comply: {
    starter_monthly: 'price_1Te0k1GRBK524I7zrLssfPVt',
    starter_annual:  'price_1Te0k5GRBK524I7zgWdvIRLy',
    scale_monthly:   'price_1Te0kDGRBK524I7z8zwCrNUD',
    scale_annual:    'price_1Te0kGGRBK524I7zQcnbPrPY',
    credits_5:       'price_1Te0kOGRBK524I7z8OmtD5Lp',
    credits_20:      'price_1Te0kRGRBK524I7zMOvbrXW5',
    credits_50:      'price_1Te0kUGRBK524I7zTccpMVZc',
  },
  scan: {
    pro_per_repo:    'price_1Te0kfGRBK524I7zrMHu3BXL',
    business:        'price_1Te0kmGRBK524I7zBKcUu6h6',
  },
  gateway: {
    developer_monthly: 'price_1Te0kvGRBK524I7zbhruWdHb',
    developer_annual:  'price_1Te0kzGRBK524I7zZMQ4r1G7',
    team_monthly:      'price_1Te0l6GRBK524I7zk7qU16TX',
    team_annual:       'price_1Te0lAGRBK524I7zac5aYFPK',
  },
} as const;

export const PRODUCTS = {
  comply_starter: 'prod_UdHIRpesJB0WFu',
  comply_scale:   'prod_UdHIYA1Wd8li76',
  comply_credits: 'prod_UdHI25gm6SNnIp',
  scan_pro:       'prod_UdHJBTmWYH1f99',
  scan_business:  'prod_UdHJyQYThV1Qgg',
  gateway_developer: 'prod_UdHJhh55IaExpq',
  gateway_team:      'prod_UdHJVfhfLrueep',
} as const;

export const STRIPE_ACCOUNT = 'acct_1TLbVkGRBK524I7z';
export const STRIPE_API_VERSION = '2025-12-15.clover'; // Clerk-compatible; update if SDK errors
```

---

## 2. The Account-Linkage Architecture (Clerk ↔ Stripe ↔ CRP)

### 2.1 The Three-Way Link

```
┌──────────────┐     owns      ┌──────────────┐    pays via   ┌──────────────┐
│ CLERK        │──────────────▶│ CRP TENANT   │──────────────▶│ STRIPE       │
│ Organization │               │ (the account)│               │ Customer     │
│ org_xxx      │◀──────────────│              │◀──────────────│ cus_xxx      │
└──────────────┘  entitlement  └──────────────┘  subscription └──────────────┘
       │            stored on org metadata            │
       │                                               │
   the identity                                  the money
   (who they are)                                (what they paid)

LINK KEYS:
  Clerk org.publicMetadata.stripeCustomerId      = cus_xxx
  Clerk org.publicMetadata.stripeSubscriptionId  = sub_xxx
  Clerk org.publicMetadata.plan                   = "free|starter|scale|..."
  Stripe customer.metadata.clerkOrgId             = org_xxx
  Stripe checkout.metadata.clerkOrgId             = org_xxx
```

The Clerk **organization** is the account. The Stripe **customer** is created with `clerkOrgId` in its metadata, and the Clerk org stores `stripeCustomerId`. This bidirectional link means: given a Clerk org you can find its Stripe customer, and given a Stripe webhook you can find the Clerk org to update. Entitlement (`plan`, quotas, features) lives on the Clerk org's `publicMetadata`, so it is available everywhere Clerk auth is — client, server, middleware — without a separate database lookup.

### 2.2 Why Clerk Organizations, Not Users

CRP's products are B2B (companies become audit-ready, teams run governed AI). The billable account is an organization, not an individual. Clerk organizations model this natively: members, roles (admin/member/billing), and per-org metadata for entitlement. Billing is managed by org admins; entitlement applies to the whole org. (For solo users, Clerk still creates a personal-style org or you allow personal accounts — but the B2B default is `hidePersonal`.)

---

## 3. The Complete Payment + Verification Flow

### 3.1 End-to-End

```
1. User (org admin) clicks Upgrade in-app
2. Server creates a Stripe Checkout Session:
     - customer = the org's stripeCustomerId (created if absent)
     - line_items = the chosen Price ID (§1)
     - metadata.clerkOrgId = org_xxx   ← the link
     - success_url / cancel_url → back to the exact surface
3. User redirected to Stripe-hosted Checkout (cards, wallets, dynamic PMs)
4. User pays on Stripe (PCI handled by Stripe)
5. Stripe redirects to success_url
6. Stripe fires webhook checkout.session.completed (signed)
7. Webhook handler VERIFIES the signature, reads metadata.clerkOrgId,
   and writes entitlement to the Clerk org:
     plan, stripeSubscriptionId, quota, features
8. The success page reads the updated entitlement (polling if needed)
   and shows the unlocked capability ACTIVE
```

### 3.2 Verification Is Non-Negotiable

Two verification layers, both required:
- **Signature verification:** every webhook is verified with `stripe.webhooks.constructEvent(body, sig, WEBHOOK_SECRET)`. An unverified webhook is rejected — this prevents a forged "payment succeeded" call from granting free access.
- **Entitlement reconciliation:** entitlement is granted ONLY by the verified webhook, never by the browser returning to success_url (the browser can be spoofed). The success page *reads* entitlement; it never *grants* it. A nightly reconciliation job compares Stripe subscriptions to Clerk org entitlement and corrects any drift (a missed webhook).

---

## 4. The Code — Clerk-Native Layer (TypeScript)

This is the auth + entitlement layer, using Clerk's organization model. (Clerk's SDK is JS/TS; this is the canonical integration.)

### 4.1 Stripe client + customer creation linked to a Clerk org

```typescript
// lib/stripe.ts
import Stripe from 'stripe';
export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: '2025-12-15.clover',
});

// lib/billing.ts
import { clerkClient } from '@clerk/nextjs/server';
import { stripe } from './stripe';

export async function getOrCreateStripeCustomer(orgId: string, orgName: string, email: string) {
  const client = await clerkClient();
  const org = await client.organizations.getOrganization({ organizationId: orgId });

  let customerId = org.publicMetadata?.stripeCustomerId as string | undefined;
  if (!customerId) {
    const customer = await stripe.customers.create({
      name: orgName,
      email,
      metadata: { clerkOrgId: orgId },   // ← the link, Stripe → Clerk
    });
    customerId = customer.id;
    await client.organizations.updateOrganization(orgId, {
      publicMetadata: { ...org.publicMetadata, stripeCustomerId: customerId },
    });
  }
  return customerId;
}
```

### 4.2 Checkout session (subscription or one-time credits)

```typescript
// app/api/billing/create-checkout/route.ts
import { auth, clerkClient } from '@clerk/nextjs/server';
import { stripe } from '@/lib/stripe';
import { getOrCreateStripeCustomer } from '@/lib/billing';

export async function POST(req: Request) {
  const { userId, orgId, orgRole } = await auth();
  if (!userId || !orgId) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  if (orgRole !== 'org:admin') return Response.json({ error: 'Admins only' }, { status: 403 });

  const { priceId, mode, returnTo } = await req.json();
  // mode: 'subscription' for tiers, 'payment' for credit top-ups

  const client = await clerkClient();
  const org = await client.organizations.getOrganization({ organizationId: orgId });
  const customerId = await getOrCreateStripeCustomer(orgId, org.name, /* admin email */ '');

  const session = await stripe.checkout.sessions.create({
    customer: customerId,
    mode: mode ?? 'subscription',
    line_items: [{ price: priceId, quantity: 1 }],
    // return the user to the EXACT surface they were on:
    success_url: `${process.env.NEXT_PUBLIC_URL}${returnTo}?upgraded=1&cs={CHECKOUT_SESSION_ID}`,
    cancel_url:  `${process.env.NEXT_PUBLIC_URL}${returnTo}?canceled=1`,
    client_reference_id: orgId,
    metadata: { clerkOrgId: orgId, priceId },   // ← the link, Checkout → Clerk
    allow_promotion_codes: true,
    // Stripe Tax (AU GST / EU VAT) — enable in dashboard, then:
    automatic_tax: { enabled: true },
  });
  return Response.json({ url: session.url });
}
```

### 4.3 The webhook — grant/verify entitlement (the heart of it)

```typescript
// app/api/webhooks/stripe/route.ts
import { clerkClient } from '@clerk/nextjs/server';
import { stripe } from '@/lib/stripe';
import { planFromPriceId, quotaFor, featuresFor } from '@/lib/entitlement';

export async function POST(req: Request) {
  const body = await req.text();
  const sig = req.headers.get('stripe-signature')!;
  let event;
  try {
    event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET!);
  } catch {
    return Response.json({ error: 'Invalid signature' }, { status: 400 }); // verification
  }
  const client = await clerkClient();

  switch (event.type) {
    case 'checkout.session.completed': {
      const s = event.data.object;
      const orgId = s.metadata?.clerkOrgId;
      if (!orgId) break;

      if (s.mode === 'subscription') {
        const sub = await stripe.subscriptions.retrieve(s.subscription as string);
        const priceId = sub.items.data[0].price.id;
        const plan = planFromPriceId(priceId);     // 'starter' | 'scale' | 'developer' | 'team' | ...
        await client.organizations.updateOrganization(orgId, {
          publicMetadata: {
            plan,
            stripeSubscriptionId: sub.id,
            quota: quotaFor(plan),
            features: featuresFor(plan),
            currentPeriodEnd: sub.current_period_end,
          },
        });
      } else if (s.mode === 'payment') {
        // credit top-up — increment the org's prepaid balance
        const org = await client.organizations.getOrganization({ organizationId: orgId });
        const addCents = creditCentsFromPriceId(s.metadata?.priceId);
        const balance = (org.publicMetadata?.creditBalanceCents as number ?? 0) + addCents;
        await client.organizations.updateOrganization(orgId, {
          publicMetadata: { ...org.publicMetadata, creditBalanceCents: balance },
        });
      }
      break;
    }
    case 'customer.subscription.updated': {
      const sub = event.data.object;
      const orgId = await orgIdFromCustomer(sub.customer as string);
      if (orgId) {
        const plan = planFromPriceId(sub.items.data[0].price.id);
        await client.organizations.updateOrganization(orgId, {
          publicMetadata: { plan, quota: quotaFor(plan), features: featuresFor(plan),
                            currentPeriodEnd: sub.current_period_end },
        });
      }
      break;
    }
    case 'customer.subscription.deleted': {
      const sub = event.data.object;
      const orgId = await orgIdFromCustomer(sub.customer as string);
      if (orgId) {
        await client.organizations.updateOrganization(orgId, {
          publicMetadata: { plan: 'free', stripeSubscriptionId: null,
                            quota: quotaFor('free'), features: featuresFor('free') },
        });
      }
      break;
    }
    case 'invoice.payment_failed': {
      // dunning: notify the org admin, set a grace flag
      const inv = event.data.object;
      const orgId = await orgIdFromCustomer(inv.customer as string);
      if (orgId) await client.organizations.updateOrganization(orgId, {
        publicMetadata: { paymentIssue: true },
      });
      break;
    }
  }
  return Response.json({ received: true });
}

async function orgIdFromCustomer(customerId: string): Promise<string | undefined> {
  const customer = await stripe.customers.retrieve(customerId);
  return (customer as any).metadata?.clerkOrgId;
}
```

### 4.4 Entitlement mapping (the single source of plan→capability)

```typescript
// lib/entitlement.ts
import { PRICES } from './crp-pricing';

export function planFromPriceId(priceId: string): string {
  const map: Record<string,string> = {
    [PRICES.comply.starter_monthly]: 'comply_starter',
    [PRICES.comply.starter_annual]:  'comply_starter',
    [PRICES.comply.scale_monthly]:   'comply_scale',
    [PRICES.comply.scale_annual]:    'comply_scale',
    [PRICES.scan.pro_per_repo]:      'scan_pro',
    [PRICES.scan.business]:          'scan_business',
    [PRICES.gateway.developer_monthly]: 'gateway_developer',
    [PRICES.gateway.developer_annual]:  'gateway_developer',
    [PRICES.gateway.team_monthly]:      'gateway_team',
    [PRICES.gateway.team_annual]:       'gateway_team',
  };
  return map[priceId] ?? 'free';
}

export function quotaFor(plan: string): number {
  return ({ free: 100, comply_starter: 5000, comply_scale: 50000,
            gateway_developer: 50000, gateway_team: 500000 } as Record<string,number>)[plan] ?? 100;
}
export function featuresFor(plan: string): string[] {
  // what each plan unlocks — checked by the app + Clerk <Show when={{plan}}>
  const f: Record<string,string[]> = {
    free: ['governance'],
    comply_starter: ['governance','checkpoint_inbox','evidence_pack','hosted_vault','scan_remediations'],
    comply_scale:   ['governance','checkpoint_inbox','evidence_pack','hosted_vault','scan_remediations','sso','data_residency','custom_rules','hosted_llm'],
    gateway_developer: ['governance','context_suite','console','deploy_endpoint'],
    gateway_team:      ['governance','context_suite','console','deploy_endpoint','shared_pipelines','sso'],
    scan_pro: ['scan_remediation_pr'],
    scan_business: ['scan_remediation_pr','unlimited_repos','campaigns'],
  };
  return f[plan] ?? ['governance'];
}
```

### 4.5 Checking entitlement (gating capability)

```typescript
// Client: Clerk's Show component gates UI by plan/feature
import { Show } from '@clerk/nextjs';
<Show when={{ feature: 'evidence_pack' }} fallback={<UpgradePrompt plan="starter" />}>
  <ExportEvidencePackButton />
</Show>

// Server: gate an API by reading org entitlement
import { auth, clerkClient } from '@clerk/nextjs/server';
export async function POST() {
  const { orgId } = await auth();
  const org = await (await clerkClient()).organizations.getOrganization({ organizationId: orgId! });
  const features = org.publicMetadata?.features as string[] ?? [];
  if (!features.includes('evidence_pack')) return Response.json({ error: 'upgrade_required' }, { status: 402 });
  // ... do the work
}
```

### 4.6 Customer portal (self-serve management)

```typescript
// app/api/billing/create-portal/route.ts
import { auth, clerkClient } from '@clerk/nextjs/server';
import { stripe } from '@/lib/stripe';
export async function POST() {
  const { orgId, orgRole } = await auth();
  if (orgRole !== 'org:admin') return Response.json({ error: 'Admins only' }, { status: 403 });
  const org = await (await clerkClient()).organizations.getOrganization({ organizationId: orgId! });
  const session = await stripe.billingPortal.sessions.create({
    customer: org.publicMetadata?.stripeCustomerId as string,
    return_url: `${process.env.NEXT_PUBLIC_URL}/dashboard/billing`,
  });
  return Response.json({ url: session.url });
}
```

---

## 5. The Code — Python Backend Option (for CRP's own services)

CRP's runtime services (the Gateway, Scan, the metering engine) are likely Python. They don't manage Clerk auth (that's the web layer) but they DO need to (a) verify entitlement when serving a request, and (b) report usage for metering. Here is the Python side.

### 5.1 Verifying entitlement on a governed request (Gateway/Comply runtime)

```python
# crp/billing/entitlement.py
import os, time, requests

CLERK_SECRET = os.environ["CLERK_SECRET_KEY"]

def get_org_entitlement(org_id: str) -> dict:
    """Read entitlement from the Clerk org's public metadata."""
    r = requests.get(
        f"https://api.clerk.com/v1/organizations/{org_id}",
        headers={"Authorization": f"Bearer {CLERK_SECRET}"},
        timeout=5,
    )
    r.raise_for_status()
    meta = r.json().get("public_metadata", {})
    return {
        "plan": meta.get("plan", "free"),
        "quota": meta.get("quota", 100),
        "features": meta.get("features", ["governance"]),
        "credit_balance_cents": meta.get("creditBalanceCents", 0),
        "current_period_end": meta.get("currentPeriodEnd"),
    }

def require_feature(org_id: str, feature: str):
    ent = get_org_entitlement(org_id)
    if feature not in ent["features"]:
        raise PermissionError(f"upgrade_required:{feature}")
    return ent
```

### 5.2 Metering usage (the audited-call quota)

```python
# crp/billing/metering.py
# CRP counts audited calls per org per period and enforces the quota.
# When quota is exceeded, draw from prepaid credits; else return 402.

def record_audited_call(org_id: str, usage_store) -> dict:
    ent = get_org_entitlement(org_id)
    used = usage_store.increment(org_id, period_key())  # atomic counter
    if used <= ent["quota"]:
        return {"status": "ok", "used": used, "quota": ent["quota"]}
    # over quota — try prepaid credits
    if ent["credit_balance_cents"] >= CREDIT_COST_PER_CALL_CENTS:
        usage_store.draw_credit(org_id, CREDIT_COST_PER_CALL_CENTS)
        return {"status": "ok_credit", "used": used}
    return {"status": "quota_exceeded", "used": used, "quota": ent["quota"],
            "action": "prompt_topup_or_upgrade"}
```

### 5.3 Reporting usage to Stripe (for usage-based components, optional)

```python
# If any plan has metered (usage-based) billing rather than flat quota:
import stripe
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
stripe.api_version = "2025-12-15.clover"

def report_usage(subscription_item_id: str, quantity: int):
    stripe.SubscriptionItem.create_usage_record(
        subscription_item_id,
        quantity=quantity,
        timestamp=int(time.time()),
        action="increment",
    )
```

### 5.4 Note on the split

The TypeScript/Clerk layer owns **auth, checkout, the webhook, and entitlement writes**. The Python layer owns **reading entitlement to gate the runtime, metering usage, and quota enforcement**. Entitlement is written in one place (the webhook → Clerk org metadata) and read in many (TS UI, TS APIs, Python runtime). One source of truth (the Clerk org), many readers.

---

## 6. The Payment UX Per Product (when / where / what)

(Full detail unchanged from the product specs; summarised here as the implementation contract.)

| Product | Paywall trigger | mode | Price | Returns to |
|---------|----------------|------|-------|-----------|
| Comply | quota hit / open checkpoint / export evidence pack | subscription | Starter/Scale | the surface they were on, unlocked |
| Comply | credits run out mid-task | payment | $5/$20/$50 | the paused task, resumed |
| Scan | click "Open PR" on a remediation | subscription | Scan Pro | findings view, PR opened immediately |
| Gateway | click "Deploy as endpoint" | subscription | Developer/Team | console, endpoint live + URL shown |

Principle: value first, paywall at the moment of need, return to the exact context with the capability active. Entitlement is granted by the webhook; the success page polls entitlement (read) until it flips, then reveals the unlocked capability — never grants it client-side.

---

## 7. Remaining Manual Steps (Stripe Dashboard) — now mostly done

All 12 payment links are LIVE (§1). Remaining dashboard config:
1. **Customer Portal** — Settings → Billing → Customer Portal → activate; allow switching among the CRP prices (§1).
2. **Stripe Tax** — Settings → Tax → enable; origin Sydney (AU GST + EU VAT). Then `automatic_tax.enabled` (§4.2) works.
3. **Webhook endpoint** — Developers → Webhooks → add `https://<app>/api/webhooks/stripe` for: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`. Copy the signing secret to `STRIPE_WEBHOOK_SECRET`.
4. **Dynamic payment methods** — Settings → Payment methods → enable cards + Apple/Google Pay.
5. **Branding** — Settings → Branding → CRP logo + colours for Checkout + Portal.
6. **Clerk** — enable Organizations; set roles (admin/member/billing); configure the webhook env (`CLERK_SECRET_KEY`).
7. **Test mode first** — replicate and test the full loop (Checkout → webhook → Clerk entitlement → success page) before relying on it live.

---

## 8. Honest Status & Limits

The Stripe objects and links are live. The integration code (§4/5) is the real build — accurate to Clerk's current B2B billing pattern and Stripe best practice, but it must be wired to CRP's actual app, env vars set, and tested end-to-end in Stripe test mode before going live.

The API version `2025-12-15.clover` is Clerk's documented compatible version; if the latest Stripe SDK raises a version mismatch, update it (Stripe is backward-compatible within reason). Stripe's own guidance favours the newest version; reconcile the two by testing.

Entitlement-on-Clerk-metadata is convenient (available everywhere via auth) but Clerk metadata is eventually-consistent and size-limited — keep it small (plan, ids, quota, features, balance), not a full usage log. Usage/metering data belongs in CRP's own store, not Clerk metadata.

The webhook is the single point that grants access; it must be reliable and idempotent (handle duplicate deliveries). Use the event ID to dedupe. The nightly reconciliation job (§3.2) is the safety net for missed webhooks and must be built, not skipped.

Pricing remains a hypothesis to validate with real conversion data.

---

## 9. References

- CRP-SPEC-040/042/043/036 — the products and their paywall triggers
- Clerk B2B SaaS + Stripe billing integration (organizations, entitlement metadata)
- Stripe Checkout, Billing, Customer Portal, Webhooks, Tax

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. Live Stripe objects on acct_1TLbVkGRBK524I7z (AutoCyber AI). Auth via Clerk organizations.*
