# CRP MCP Server — Environment Variable Mapping

**Classification:** Internal / Operational — do not commit secret values.  
**Source env files:** `crp_gateway_railway.env`, `crp_comply_railway.env` (kept at repo root, gitignored).

---

## How to read the source files safely

The `*_railway.env` files contain production secrets. Open them locally only on a trusted machine and treat the values as sensitive. When sharing or logging, redact values:

```python
import re

with open("crp_gateway_railway.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        # Skip multi-line values (e.g. PEM blocks)
        if "BEGIN" in val or "END" in val:
            continue
        print(f"{key}=***REDACTED***")
```

Never paste the full contents into chat, CI logs, or Git.

---

## Variables the MCP server needs

### Required for hosted mode authentication

| MCP server variable | Maps from | Purpose |
|---|---|---|
| `CLERK_ISSUER` | `CLERK_ISSUER` in either railway env | Issuer URL for Clerk JWT validation |
| `CLERK_AUTHORIZED_PARTIES` | `CLERK_AUTHORIZED_PARTIES` in either railway env | Allowed client origins |
| `CLERK_SECRET_KEY` | `CLERK_SECRET_KEY` in either railway env | Clerk secret key for session verification |

### Required for hosted backends

| MCP server variable | Maps from | Purpose |
|---|---|---|
| `CRP_GATEWAY_URL` | `CRP_GATEWAY_URL` in `crp_gateway_railway.env` | Base URL for live Gateway calls |
| `CRP_HOSTED_API_KEY` | **Generate separately** or use service-to-service secret | API key the MCP server uses to call the Gateway on behalf of a tenant |
| `CRP_COMPLY_BASE_URL` | `CRP_COMPLY_BASE_URL` in `crp_comply_railway.env` | Base URL for CRP Comply API |
| `CRP_COMPLY_JWT_SECRET` | `CRP_COMPLY_JWT_SECRET` in either railway env | Shared secret for service-to-service Comply requests |

### Billing

| MCP server variable | Maps from | Purpose |
|---|---|---|
| `STRIPE_SECRET_KEY` | `STRIPE_SECRET_KEY` in either railway env | Stripe secret key for plan/price lookups |
| `STRIPE_WEBHOOK_SECRET` | `STRIPE_WEBHOOK_SECRET` in either railway env | Stripe webhook verification (if the MCP server handles webhooks) |
| `STRIPE_GATEWAY_*_PRICE_ID` | `STRIPE_GATEWAY_*_PRICE_ID` in `crp_gateway_railway.env` | Price IDs for Gateway checkout links |
| `STRIPE_COMPLY_*_PRICE_ID` | `STRIPE_COMPLY_*_PRICE_ID` in `crp_comply_railway.env` | Price IDs for Comply checkout links |

### MCP server specific

| MCP server variable | Suggested value | Purpose |
|---|---|---|
| `CRP_MCP_MODE` | `hosted` | Run in hosted streamable-HTTP mode |
| `PORT` | `8000` | HTTP port |
| `CRP_MCP_ROLE` | `user` | Default least-privilege role |
| `CRP_MCP_TOOLS_ALLOW` | leave blank | Optional whitelist |
| `CRP_MCP_TOOLS_DENY` | leave blank | Optional blacklist |
| `CRP_MCP_AUDIT_LOG` | `/var/log/crp_mcp_audit.jsonl` | Append-only audit log path |

### Variables the MCP server does **not** need

These belong to the backend services, not the MCP server:

- `DATABASE_URL`, `REDIS_URL` (Gateway/Comply internal databases)
- `AWS_*`, `BACKUP_R2_*` (Comply backup storage)
- `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_*` (Comply GitHub App integration)
- `CRP_COMPLY_LLM_*`, `CRP_COMPLY_SEARCH_*` (Comply internal AI/search providers)
- `RESEND_API_KEY` (Comply email provider)
- `VITE_CLERK_PUBLISHABLE_KEY` (frontend only)
- `APP_BASE_URL`, `SECRET_KEY` (Gateway service internals)

---

## Example `.env` for the MCP server

Create a file named `crp_mcp.env` (gitignored) next to the server code. **Do not commit it.**

```bash
# Mode
CRP_MCP_MODE=hosted
PORT=8000

# Auth (from Clerk / railway env files)
CLERK_ISSUER=https://your-clerk-issuer.clerk.accounts.dev
CLERK_AUTHORIZED_PARTIES=https://your-app.com,https://crprotocol.io
CLERK_SECRET_KEY=<YOUR_CLERK_SECRET_KEY>

# Backends
CRP_GATEWAY_URL=https://gateway.crprotocol.io/v1
CRP_COMPLY_BASE_URL=https://comply.crprotocol.io
CRP_COMPLY_JWT_SECRET=your-service-secret
CRP_HOSTED_API_KEY=your-tenant-service-key

# Billing
STRIPE_SECRET_KEY=<YOUR_STRIPE_SECRET_KEY>
STRIPE_WEBHOOK_SECRET=<YOUR_STRIPE_WEBHOOK_SECRET>
STRIPE_GATEWAY_DEVELOPER_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_GATEWAY_TEAM_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_STARTER_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_SCALE_PRICE_ID=<YOUR_STRIPE_PRICE_ID>

# Permissions & audit
CRP_MCP_ROLE=user
CRP_MCP_AUDIT_LOG=/var/log/crp_mcp_audit.jsonl
```

Load it when running the server:

```bash
set -a
source crp_mcp.env
set +a
python -m crp_mcp.server
```

---

## Security notes

1. **Never commit `.env` files.** The repo `.gitignore` now ignores `*.env`, `*_railway.env`, and PEM/key files.
2. **Rotate the GitHub App private key** if it has ever been printed or copied to an untrusted location.
3. Use a secret manager (Railway variables, Doppler, 1Password, AWS Secrets Manager) in production instead of `.env` files.
4. Run the MCP server with the least-privilege role by default: `CRP_MCP_ROLE=user`.
5. Enable audit logging from day one: `CRP_MCP_AUDIT_LOG`.
