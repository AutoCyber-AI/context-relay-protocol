# CRP — Stripe + Clerk Setup Guide & Live Object Reference

**Account:** AutoCyber AI (`acct_1TLbVkGRBK524I7z`) · **Currency:** USD · **Status:** ALL LIVE
**Auth:** Clerk (organizations) · **Full detail + code:** SPEC-047

## ALL 12 PAYMENT LINKS ARE LIVE

### CRP Comply
| Plan | $/period | Price ID | Payment Link |
|------|----------|----------|--------------|
| Starter monthly | $49/mo | price_1Te0k1GRBK524I7zrLssfPVt | https://buy.stripe.com/fZu00j3WsfIJbKy0uvffy00 |
| Starter annual | $490/yr | price_1Te0k5GRBK524I7zgWdvIRLy | https://buy.stripe.com/3cI3cveB64016qeb99ffy05 |
| Scale monthly | $499/mo | price_1Te0kDGRBK524I7z8zwCrNUD | https://buy.stripe.com/aFaaEXgJefIJaGu0uvffy01 |
| Scale annual | $4990/yr | price_1Te0kGGRBK524I7zQcnbPrPY | https://buy.stripe.com/9B64gz50w2VXbKy6STffy06 |
| Credits $5 | one-time | price_1Te0kOGRBK524I7z8OmtD5Lp | https://buy.stripe.com/dRm28r64A1RT29Yb99ffy0a |
| Credits $20 | one-time | price_1Te0kRGRBK524I7zMOvbrXW5 | https://buy.stripe.com/8x23cv1Okbst6qea55ffy0b |
| Credits $50 | one-time | price_1Te0kUGRBK524I7zTccpMVZc | https://buy.stripe.com/4gM5kD0KgeEF4i6a55ffy0c |

### CRP Scan
| Plan | $/period | Price ID | Payment Link |
|------|----------|----------|--------------|
| Pro (per repo) | $29/mo | price_1Te0kfGRBK524I7zrMHu3BXL | https://buy.stripe.com/00wdR98cI2VX9Cqcddffy02 |
| Business | $299/mo | price_1Te0kmGRBK524I7zBKcUu6h6 | https://buy.stripe.com/14A6oHakQ68901Qa55ffy07 |

### CRP Gateway
| Plan | $/period | Price ID | Payment Link |
|------|----------|----------|--------------|
| Developer monthly | $29/mo | price_1Te0kvGRBK524I7zbhruWdHb | https://buy.stripe.com/28EdR9boU6896qe1yzffy03 |
| Developer annual | $290/yr | price_1Te0kzGRBK524I7zZMQ4r1G7 | https://buy.stripe.com/bJe9ATakQgMNaGu3GHffy08 |
| Team monthly | $199/mo | price_1Te0l6GRBK524I7zk7qU16TX | https://buy.stripe.com/dRm7sLgJe1RTbKy1yzffy04 |
| Team annual | $1990/yr | price_1Te0lAGRBK524I7zac5aYFPK | https://buy.stripe.com/9B63cv50w2VXg0O2CDffy09 |

## PRODUCT IDS
- Comply Starter: prod_UdHIRpesJB0WFu · Scale: prod_UdHIYA1Wd8li76 · Credits: prod_UdHI25gm6SNnIp
- Scan Pro: prod_UdHJBTmWYH1f99 · Business: prod_UdHJyQYThV1Qgg
- Gateway Developer: prod_UdHJhh55IaExpq · Team: prod_UdHJVfhfLrueep

## REMAINING DASHBOARD CONFIG (links all done)
1. Customer Portal — Settings → Billing → Customer Portal (allow plan switching).
2. Stripe Tax — Settings → Tax (AU GST + EU VAT; origin Sydney) → then automatic_tax works.
3. Webhook — Developers → Webhooks → https://<app>/api/webhooks/stripe →
   events: checkout.session.completed, customer.subscription.updated,
   customer.subscription.deleted, invoice.payment_failed → copy signing secret.
4. Dynamic payment methods — Settings → Payment methods (cards + Apple/Google Pay).
5. Branding — Settings → Branding (logo + colours).
6. Clerk — enable Organizations; roles admin/member/billing; set CLERK_SECRET_KEY.

## THE LINK MODEL (Clerk ↔ Stripe ↔ CRP)
- Clerk Organization = the account. Stripe Customer created with metadata.clerkOrgId.
- Clerk org.publicMetadata holds: stripeCustomerId, stripeSubscriptionId, plan, quota, features, creditBalanceCents.
- Checkout Session carries metadata.clerkOrgId → webhook reads it → writes entitlement to the Clerk org.
- Entitlement WRITTEN once (webhook), READ everywhere (TS UI/API + Python runtime).
- Code: SPEC-047 §4 (TypeScript/Clerk) + §5 (Python backend).

## ENV VARS NEEDED
STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, CLERK_SECRET_KEY, NEXT_PUBLIC_URL
GIThub: the CRP Comply GitHub App id + private key (in a secrets manager).

## PAYMENT UX IN ONE LINE PER PRODUCT
- Comply: value first → paywall at quota/checkpoint/evidence-pack → Checkout → return to unlocked surface.
- Scan: free finds + previews fix → paywall at "Open PR" → Checkout → PR opened instantly.
- Gateway: free build + test → paywall at "Deploy as endpoint" → Checkout → endpoint live.
Entitlement granted by VERIFIED webhook only; success page reads (never grants) it.
