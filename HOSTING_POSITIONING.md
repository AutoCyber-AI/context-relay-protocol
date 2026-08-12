# CRP Hosting & Positioning Strategy

## Positioning: "Local-First, Cloud-Ready"

CRP products are available as **hosted SaaS applications** and as **locally deployable software**. The SaaS offering provides instant onboarding via product subdomains, while the local deployment option targets enterprises and regulated environments that require on-premises control — this is AutoCyber AI's go-to for enterprise deployments.

### Deployment Models

| Model | Description | Target |
|---|---|---|
| **SaaS (Hosted)** | Sign up at product subdomains, Stripe billing | Startups, SMBs, developers |
| **Local (Downloadable)** | Self-hosted on-premises or private cloud | Enterprises, regulated industries, government |

The local deployment uses the same codebase — packaged as a downloadable application (future: Tauri desktop app) that runs entirely on the customer's infrastructure. Data never leaves their environment.

### Why SaaS, Not Packages

| Consideration | Package (pip install) | SaaS (hosted) |
|---|---|---|
| **Revenue** | No billing control | Stripe subscription billing |
| **Updates** | User must upgrade manually | Instant, zero-downtime deploys |
| **Security patches** | User may lag behind | Applied immediately |
| **Compliance audit trail** | Stored locally (risky) | HMAC-chained, server-side |
| **PII scanning** | User's responsibility | CRP-managed, always current |
| **Onboarding** | pip install + config | Sign up → start |
| **Support** | Debug user's environment | Controlled environment |
| **Telemetry** | Opt-in only | Built-in usage metrics |

### Product URLs

| Product | URL | Status |
|---|---|---|
| CRP Scribe | `https://scribe.crprotocol.io` | Planned |
| CRP Comply | `https://comply.crprotocol.io` | Planned |
| Marketing site | `https://crprotocol.io` | **LIVE** |
| Documentation | `https://crprotocol.io/docs/` | **LIVE** |

---

## Hosting: Railway

### Why Railway

| Factor | Railway | Vercel | AWS/GCP |
|---|---|---|---|
| **FastAPI support** | Native (Docker) | Serverless only | Manual setup |
| **WebSocket support** | ✓ | Limited | ✓ but complex |
| **Background workers** | ✓ | ✗ | ✓ |
| **Persistent storage** | PostgreSQL, Redis | External only | Managed services |
| **Custom domains** | ✓ (free SSL) | ✓ | Route53 + ACM |
| **Pricing model** | Usage-based ($5/mo hobby) | Per-seat | Pay-as-you-go |
| **Deploy from GitHub** | ✓ (auto-deploy) | ✓ | CodePipeline |
| **Startup friendly** | ✓ | ✓ | ✗ (complex) |

### Railway Service Architecture

```
railway.app
├── crp-scribe-api       (FastAPI, port 8500)
│   ├── Dockerfile
│   ├── PostgreSQL (scribe-db)
│   └── Redis (scribe-cache)
│
├── crp-scribe-web       (Vite static build)
│   └── served via nginx or Railway static hosting
│
├── crp-comply-api       (FastAPI, port 8400)
│   ├── Dockerfile
│   ├── PostgreSQL (comply-db)
│   └── Redis (comply-cache)
│
└── crp-comply-web       (Vite static build)
    └── served via nginx or Railway static hosting
```

### Deployment Tiers

| Environment | Railway Plan | Cost | Purpose |
|---|---|---|---|
| Development | Hobby ($5/mo) | ~$5-10/mo | Dev/test |
| Staging | Pro ($20/mo) | ~$20-40/mo | Pre-production |
| Production | Pro ($20/mo) | ~$50-200/mo | Live customers |

---

## Security: "The Security Is In The Protocol"

CRP products don't need to run in a locked-down VPC because security is embedded at the protocol layer:

| CRP Security Module | What It Does | Where It Runs |
|---|---|---|
| `PIIScanner` | 7-category PII detection | In every proxy request |
| `InjectionDetector` | 21 patterns + ML scoring | In every proxy request |
| `ComplianceAuditTrail` | HMAC-chained audit records | Server-side, append-only |
| `ProcessingRecordKeeper` | GDPR Art. 30 records | Server-side |
| `ErasureManager` | GDPR Art. 17 right to erasure | Server-side |
| `DataClassification` | PUBLIC → CRITICAL classification | Per-request |
| `RiskClassifier` | EU AI Act Art. 6 risk levels | Per-request |
| `ConsentManager` | Purpose-based consent tracking | Server-side |
| `ContextValidator` | Schema + semantic validation | In every request |
| `EncryptionManager` | AES-256-GCM field encryption | At rest + in transit |
| `AccessControl` | RBAC + ABAC policies | Per-request |
| `EnvelopeProtocol` | Signed, versioned message envelopes | Every message |

This means Railway's standard infrastructure (HTTPS, network isolation, managed PostgreSQL with encryption at rest) is **sufficient** — the CRP layer handles application-level security.

---

## Positioning Matrix

### For Investors

> "CRP is a protocol-first company. Our SaaS products (Scribe, Comply) are hosted applications with Stripe subscription billing. Security is built into the protocol itself — we don't need expensive cloud infrastructure to be enterprise-grade."

### For Enterprise Customers

> "CRP Comply runs as a managed service or a locally deployed application — your choice. In SaaS mode, your AI traffic flows through our compliance proxy with PII scanning and audit trails. In local mode, the same software runs entirely on your infrastructure — data never leaves your environment."

### For Regulators

> "All processing records, audit trails, and consent records are maintained with HMAC-chain verification. GDPR Article 30 records and right-to-erasure requests are handled through documented API endpoints with full audit history. For regulated environments, CRP products can be deployed on-premises."

### For Developers

> "Sign up at comply.crprotocol.io or scribe.crprotocol.io. Get an API key. Point your OpenAI calls at our proxy endpoint. Done. The CRP protocol library (`pip install crprotocol`) is available separately for developers who want to build their own CRP-compatible tools."

---

## Key Distinction

| | CRP Protocol (`crprotocol`) | CRP Products (SaaS) | CRP Products (Local) |
|---|---|---|---|
| **Distribution** | PyPI (`pip install crprotocol`) | Hosted SaaS | Downloadable app / Docker |
| **License** | ELv2 | ELv2 | ELv2 (commercial license) |
| **Pricing** | Free (open-source core) | Freemium + Stripe billing | Enterprise license |
| **Target** | Developers building CRP tools | Startups / SMBs | Enterprises / regulated |
| **Auth** | N/A | Clerk | Clerk or customer SSO |
| **Billing** | N/A | Stripe | Invoice / PO |
| **Data residency** | N/A | Railway (AU/US/EU) | Customer's infrastructure |
| **URL** | pypi.org/project/crprotocol | scribe/comply.crprotocol.io | On-premises |
