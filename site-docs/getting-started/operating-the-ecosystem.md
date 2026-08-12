# Operating the CRP Ecosystem

CRP is not a single binary - it is an **ecosystem** of services, headers, and
policies that work together to keep AI output governed, attributable, and
compliant. This page tells you what you need to run and why each piece matters.

!!! info "Deployment status"
    **Managed cloud** CRP Gateway and CRP Comply are on the waitlist at
    `gateway.crprotocol.io` and `comply.crprotocol.io`.
    **Self-hosted CRP** is also available for Enterprise and white-label deployments.

## What you are operating

| Component | Why it exists | Minimum to operate |
|-----------|---------------|--------------------|
| **CRP Gateway** | The OpenAI-compatible API that enforces safety policies, manages sessions, and attaches CRP headers to every response. | Use the managed-cloud waitlist, or one self-hosted service + a Postgres DB + Redis (for multi-replica) + LLM provider keys. |
| **CRP Comply** | The customer dashboard, audit/compliance layer, and GitHub integration. | Use the managed-cloud waitlist, or one self-hosted service + a Postgres DB + identity provider + billing provider. |
| **CRP Client SDK** | How applications call the Gateway and read CRP headers. | `pip install crprotocol` + a Gateway URL + a Gateway API key. |
| **Safety Control Plane (SCP)** | Lives inside the Gateway; defines the active safety profile/policy. | Configured via `CRP-Safety-Policy` header or a named profile (`strict`, `balanced`, `permissive`, `research`). |
| **Session token** | Cryptographically carries session state across windows without server-side session pinning. | Gateway signs it with a service secret; clients echo it back. |

## Pre-flight checklist (self-hosted)

1. **Provision Postgres** for each service (gateway DB and comply DB). They
   must be separate logical databases or instances - the Gateway expects tenant
   tables; Comply expects audit/compliance tables.
2. **Provision Redis** if you run more than one Gateway replica. Redis is used
   for distributed rate-limit counters and idempotency keys.
3. **Configure an identity provider** (e.g. Clerk) for auth. Both services share
   the same identity provider instance.
4. **Configure a billing provider** for subscriptions if you are running a
   paid multi-tenant deployment.
5. **Set the public base URL** on Comply so checkout links and GitHub OAuth callbacks
   point at the right domain.
6. **Set inter-service URLs and keys** so Gateway and Comply can exchange audit
   events securely.
7. **Set LLM provider keys** per tenant on the Gateway. The Gateway uses these
   to route to providers; do not set them as global service variables in production.
8. **Run migrations** on both databases.
9. **Deploy and health-check** both services (`/health` on Gateway,
   `/api/v1/health` on Comply).
10. **Point DNS / custom domains** at your hosting platform, then set public
    HTTPS URLs in the service configuration.

!!! tip "Detailed deployment variables"
    The full environment-variable checklist, architecture diagrams, and
    operational runbook are shared with Enterprise and white-label customers
    under NDA. Contact [sales@crprotocol.io](mailto:sales@crprotocol.io) for
    access.

## Why these are separate services

- **Gateway must be stateless** so it can scale horizontally. Session state
  travels in the signed token; only rate-limit/idempotency state needs Redis.
- **Comply must own billing identity** because it talks to the billing and
  identity providers about users/organisations. You do not want the hot Gateway
  path blocked by billing lookups.
- **The SDK is thin** by design: it forwards headers, parses the CRP risk
  summary, and lets the application decide what to do with `CRITICAL` or
  `HALT` responses.

## Typical request flow

```text
App / SDK  ──►  CRP Gateway  ──►  LLM provider (OpenAI/Anthropic/local)
                  │
                  ├── strips CRP-* headers before provider call (Axiom 4)
                  ├── runs DPE + safety policy enforcement
                  ├── extends HMAC audit chain
                  ├── decrements safety budget
                  └── returns CRP-* response headers

Comply  ◄──────  audit stream / webhooks  ◄──────  Gateway
```

## Safety policies in production

The Gateway resolves a policy in this order:

1. `CRP-Safety-Policy` request header (highest priority).
2. Named profile from `CRP-Safety-Profile` (`strict`, `balanced`, `permissive`,
   `research`).
3. Default `balanced` profile.

Example header:

```http
CRP-Safety-Policy: default-src context; halt-on CRITICAL; require-grounding 0.70
```

From the SDK, configure a profile once per client:

```python
import crp

client = crp.SDKClient()
client.configure(safety_profile="strict")

response = client.complete("Generate a financial summary.")
print(f"Risk: {response.crp.risk}, Compliant: {response.crp.compliant}")
```

## Environment variable summary

The canonical per-service variable checklist is no longer published on the
public site because it exposed internal service configuration and secrets
placeholders. It is available to Enterprise and white-label customers under NDA.

The most commonly missed configuration values are:

- Database connection string (must point to the **correct logical DB** for each service)
- Cache connection string (required for multi-replica Gateway)
- Identity-provider backend key (backend key, not the publishable key)
- Inter-service JWT signing secret
- Public base URL (Comply only)
- Gateway URL + inter-service key (Comply only, for Gateway proxy/audit)
