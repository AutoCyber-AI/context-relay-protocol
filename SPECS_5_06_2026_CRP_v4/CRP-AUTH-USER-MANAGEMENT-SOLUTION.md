# CRP — User Management & Authentication: Production-Ready Solution (Comply + Gateway)

**For:** the developer fixing auth across CRP Comply and CRP Gateway
**From:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd
**Problems being solved:**
- CRP Gateway has no proper sign-in/sign-up/authentication.
- CRP Comply's user management is fragmented / only partly functional.
- No seamless SSO between the products despite one Clerk instance.
**Goal:** ONE identity across the CRP series — sign in once, use Comply and Gateway,
with per-user/per-org tailored, fully functional experiences.

---

## 1. THE TARGET ARCHITECTURE (one identity, two products)

```
                  ┌──────────────────────────────────────────────┐
                  │   ONE CLERK INSTANCE: clerk.crprotocol.io      │
                  │   (Frontend API URL / issuer)                  │
                  │   - all users, all orgs, all sessions live here│
                  └───────────────┬───────────────┬───────────────┘
                                  │               │
              same session cookie │               │ same session cookie
              on .crprotocol.io    │               │ on .crprotocol.io
                                  ▼               ▼
                  ┌───────────────────┐   ┌───────────────────┐
                  │ comply.crprotocol  │   │ gateway.crprotocol │
                  │ .io (Comply app)   │   │ .io (Gateway app)  │
                  │ verifies Clerk JWT │   │ verifies Clerk JWT │
                  └───────────────────┘   └───────────────────┘

ONE user. ONE login. Works on both subdomains = SSO.
Entitlement per product stored on Clerk org/user metadata:
   { comply_plan: "scale", gateway_plan: "developer", scan_plan: "pro" }
```

The key fact: **both products already use the same Clerk instance
(`clerk.crprotocol.io`).** That is exactly what makes SSO possible — we just have to
configure and consume it correctly. Right now it's "somewhat functional" because the
products verify Clerk independently and don't share the session cookie / don't read a
common entitlement model. This document makes it seamless.

---

## 2. HOW SSO ACTUALLY WORKS HERE (the mechanism)

Clerk issues a session as a cookie scoped to a domain. To share the session across
`comply.crprotocol.io` and `gateway.crprotocol.io`, the cookie must be set on the
**parent domain `.crprotocol.io`**, and both apps must point at the **same Clerk
instance** with the **same publishable/secret keys** for that instance.

### 2.1 The three requirements for seamless SSO
1. **Same Clerk instance** on both apps — ✅ you have this (`clerk.crprotocol.io`).
2. **Same Clerk keys** — both apps use the SAME `<YOUR_CLERK_PUBLISHABLE_KEY>` (publishable) and each its
   own backend uses the SAME instance's `<YOUR_STRIPE_SECRET_KEY>` (secret). (You showed
   `<YOUR_CLERK_PUBLISHABLE_KEY>` — that's the shared one. Use it in BOTH apps.)
3. **Cookie on the parent domain.** In the Clerk Dashboard, the production instance is
   attached to `crprotocol.io`; satellite/subdomains share it. Because both apps are
   subdomains of `crprotocol.io`, a session created on one is visible to the other.

### 2.2 Result
A user who signs in on `comply.crprotocol.io` is ALSO signed in on
`gateway.crprotocol.io` — no second login. That is the SSO you want, and it comes
essentially for free once both apps use the same instance + keys and the cookie is on
`.crprotocol.io`.

---

## 3. CLERK CONFIGURATION (do this once, in the Clerk Dashboard)

```
[ ] Production instance domain = crprotocol.io (parent), Frontend API = clerk.crprotocol.io
[ ] Both apps registered as allowed origins:
       https://comply.crprotocol.io
       https://gateway.crprotocol.io
       https://crprotocol.io
[ ] Organizations: ENABLED, "Membership optional" (solo users allowed)
[ ] Roles: org:admin (manage billing + members), org:member (use the product)
[ ] Session token: default; ensure it includes org_id + org_role claims
[ ] (Optional) a custom session claim exposing entitlement for fast client checks
```

If Clerk asks about "satellite domains": the primary app domain is `crprotocol.io`;
both subdomains operate under the one instance. Configure them so the session cookie is
issued for `.crprotocol.io` (parent), not per-subdomain.

---

## 4. THE IDENTITY MODEL — user vs org, and entitlement

Because membership is optional, a CRP customer is EITHER:
- a **personal account** (a Clerk user, no org) — a solo developer/student, OR
- an **organization** (a Clerk org with members) — a team/company.

**Entitlement lives in metadata, per product:**
```jsonc
// On the Clerk ORG (team) publicMetadata — OR the USER publicMetadata (personal):
{
  "comply_plan":  "scale",      // free | starter | scale
  "gateway_plan": "developer",  // free | developer | team
  "scan_plan":    "pro",        // free | pro | business
  "stripeCustomerId": "cus_...",
  "comply_quota": 50000,
  "gateway_quota": 500000,
  "creditBalanceCents": 2000
}
```
Each product reads ONLY its own keys (`comply_*` / `gateway_*`). A user can be paid on
one product and free on the other — independent subscriptions, one identity.

### 4.1 Resolving "the account" in code (the helper both apps use)
```python
def resolve_account(identity):
    # team context if an org is active, else the personal user
    if identity.org_id:
        return ("org", identity.org_id)
    return ("user", identity.user_id)
```
Entitlement, GitHub installations, data — all keyed by this (type, id) pair so personal
and team accounts both work.

---

## 5. THE BACKEND: VERIFYING CLERK (both apps, identical)

```python
# crp/auth.py  — shared pattern for Comply AND Gateway
import os, requests, jwt
from jwt import PyJWKClient
from fastapi import Request, HTTPException
from dataclasses import dataclass

CLERK_ISSUER = os.environ["CLERK_ISSUER"]          # https://clerk.crprotocol.io
JWKS = PyJWKClient(f"{CLERK_ISSUER}/.well-known/jwks.json")

@dataclass
class Identity:
    user_id: str
    org_id: str | None
    org_role: str | None

def current_clerk_identity(request: Request) -> Identity:
    token = (request.headers.get("Authorization") or "").replace("Bearer ", "")
    if not token:
        raise HTTPException(401, "no token")
    try:
        signing_key = JWKS.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, signing_key, algorithms=["RS256"],
                            issuer=CLERK_ISSUER, options={"verify_aud": False})
    except Exception:
        raise HTTPException(401, "invalid token")
    return Identity(
        user_id = claims["sub"],
        org_id  = claims.get("org_id"),
        org_role= claims.get("org_role"),
    )
```
Both products drop in this exact verifier (same issuer, same JWKS). That consistency is
half the battle — fragmented auth usually comes from each app verifying differently.

### 5.1 Reading entitlement (per product)
```python
import requests, os
CLERK_SECRET = os.environ["CLERK_SECRET_KEY"]

def get_entitlement(identity, product: str) -> dict:
    kind, _id = resolve_account(identity)
    base = "organizations" if kind == "org" else "users"
    r = requests.get(f"https://api.clerk.com/v1/{base}/{_id}",
                     headers={"Authorization": f"Bearer {CLERK_SECRET}"}, timeout=5)
    meta = r.json().get("public_metadata", {})
    return {
        "plan":  meta.get(f"{product}_plan", "free"),
        "quota": meta.get(f"{product}_quota", 100),
        "credits": meta.get("creditBalanceCents", 0),
    }
```

---

## 6. THE FRONTEND: SIGN-IN / SIGN-UP (fixes Gateway's missing auth)

Both apps use Clerk's components, pointed at the SAME instance.

```tsx
// Gateway AND Comply — same setup, same publishable key
// .env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = <YOUR_CLERK_PUBLISHABLE_KEY>   // the shared instance

// _app / layout
import { ClerkProvider } from "@clerk/nextjs";
<ClerkProvider>{children}</ClerkProvider>

// sign-in / sign-up pages (Gateway is MISSING these — add them)
// app/sign-in/[[...sign-in]]/page.tsx
import { SignIn } from "@clerk/nextjs";
export default () => <SignIn routing="path" path="/sign-in"
  afterSignInUrl="/app" signUpUrl="/sign-up" />;

// app/sign-up/[[...sign-up]]/page.tsx
import { SignUp } from "@clerk/nextjs";
export default () => <SignUp routing="path" path="/sign-up"
  afterSignUpUrl="/app" signInUrl="/sign-in" />;

// protect the app
// middleware.ts
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
const isProtected = createRouteMatcher(["/app(.*)"]);
export default clerkMiddleware((auth, req) => { if (isProtected(req)) auth().protect(); });
```

Because the publishable key + instance are identical to Comply, a session from Comply is
already valid here — the user lands on the Gateway already signed in (SSO).

### 6.1 Org switcher + user button (tailored experiences)
```tsx
import { OrganizationSwitcher, UserButton } from "@clerk/nextjs";
// top bar:
<OrganizationSwitcher afterSelectOrganizationUrl="/app" hidePersonal={false} />
<UserButton afterSignOutUrl="/" />
```
This gives every page the "who am I / which org" context that drives per-user/per-org
tailoring — the fragmentation fix.

---

## 7. THE FUNNEL: ONE ACCOUNT, BOTH PRODUCTS

```
User signs up on Comply (or Gateway)            -> Clerk user/org created
Subscribes to Comply Scale                      -> webhook writes comply_plan=scale
Later visits gateway.crprotocol.io              -> ALREADY SIGNED IN (SSO)
Subscribes to Gateway Developer                 -> webhook writes gateway_plan=developer
Both products read their own *_plan from the SAME org/user metadata
```
A cross-product upsell becomes trivial: from Comply, "Run your governed AI in production →
open the Gateway" links straight to `gateway.crprotocol.io/app` with the user already
authenticated.

---

## 8. WHY COMPLY WAS FRAGMENTED — likely causes + fixes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Some pages know the user, some don't | mixed auth (some routes verify Clerk, some don't) | use the §5 verifier on ALL backend routes; §6 middleware on ALL app routes |
| Org vs personal confusion | code assumes org always exists | use `resolve_account()` everywhere (§4.1) |
| Entitlement sometimes wrong | read from a local DB out of sync with Stripe | single source: Clerk metadata, written only by the Stripe webhook |
| GitHub connect "forgets" the user | install not linked to identity | the state-token flow in the GitHub solution doc |
| Gateway has no login | sign-in/up pages never built | §6 adds them |

---

## 9. RAILWAY VARS (both apps) — final auth set
```
# BOTH apps — identical Clerk instance
CLERK_ISSUER             = https://clerk.crprotocol.io
CLERK_SECRET_KEY=<YOUR_CLERK_SECRET_KEY>        (this instance's secret)
CLERK_PUBLISHABLE_KEY    = <YOUR_CLERK_PUBLISHABLE_KEY>   (or VITE_/NEXT_PUBLIC_ variant)
# Comply also:
GITHUB_STATE_SECRET, GITHUB_APP_* (see GitHub solution doc)
```
Both apps MUST use the SAME publishable + secret keys (same instance). If Gateway is
using a different key or instance, that breaks SSO — align them.

---

## 10. TEST CHECKLIST (SSO + management)
```
[ ] Sign up on Comply -> land in /app, see your user in Clerk dashboard
[ ] Without signing in again, open gateway.crprotocol.io/app -> already authenticated
[ ] Create an org on one product -> visible on the other
[ ] Subscribe Comply -> comply_plan set; Gateway still free (independent) -> correct
[ ] Subscribe Gateway -> gateway_plan set; both read their own plan
[ ] Personal (no org) account works on both products
[ ] All backend routes reject requests with no/invalid Clerk token
[ ] GitHub connect links the install to the right user (other doc)
```

---

## 11. HONEST NOTES
- SSO across subdomains needs the session cookie on the parent `.crprotocol.io` and the
  SAME Clerk instance/keys on both apps. If Gateway currently points at a different Clerk
  instance or key, fix that first — it's the root of "no SSO."
- Clerk's free tier supports this (organizations + multi-domain); confirm your plan's
  limits if you scale to many orgs/MAUs.
- Entitlement must be written in exactly ONE place (the Stripe webhook) and read
  everywhere. Two writers = drift = the "somewhat functional" symptom.
- Keep entitlement small in Clerk metadata (plans, quotas, ids). Usage logs and audit
  belong in each product's own store, not Clerk.

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io*
