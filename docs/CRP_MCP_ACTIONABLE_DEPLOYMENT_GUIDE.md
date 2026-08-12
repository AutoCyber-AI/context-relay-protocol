---
seo_title: CRP MCP Server — Actionable Deployment Guide
description: Step-by-step guide to deploy the CRPv4 MCP server in local and hosted modes (stdio and HTTP) with full security controls and AI-agent integration capabilities.
---

# CRP MCP Server — Actionable Deployment Guide

This guide turns the code-complete CRPv4 MCP server into a running, secure, multi-transport service that AI agents can use to build with the Context Relay Protocol.

**Current state:**

- 59 MCP tools, 8 resources, 7 prompts registered.
- Clerk JWT auth, Stripe billing, Gateway/Comply/Scan backend clients.
- Checkpoint service with HMAC signatures, multi-approver, escalation, policy compiler.
- Audit forwarder, role-based permissions, allow/deny lists.
- **Code tests pass:** 237 passed, 0 failed for MCP + checkpoint + safety suites.

**What this guide fixes:** the remaining configuration gaps that prevent the hosted server from talking to real backends and notifying real review channels.

---

## Local vs Hosted MCP — what is the difference?

**It is the same server code.** The only difference is the environment variables you load.

| | Local mode | Hosted mode |
|---|---|---|
| **Transport** | stdio by default; HTTP if you set `CRP_MCP_MODE=hosted` without Clerk | `streamable_http` with Clerk Bearer auth |
| **Authentication** | None required | Clerk JWT enforced at transport layer |
| **Billing** | Skipped | Stripe plan/entitlement checks enforced |
| **Backend calls** | Returns safe stubs (`not_configured`) | Calls live Gateway / Comply / Scan |
| **Checkpoints** | Preview only | Real notifications via Slack/Gmail/FCM/etc. |
| **Audit** | Optional local file | Local file + forwarded to `CRP_AUDIT_ENDPOINT` |
| **Role** | Defaults to `admin` | Defaults to `user` |
| **Use case** | Development, local agent building, demos | Production multi-tenant deployment |

**Why hosted has everything local has:** all 59 tools, 8 resources, and 7 prompts are registered in both modes. Hosted simply turns on the account-linked backends. If a backend env var is missing, a hosted tool degrades to the same stub as local mode rather than crashing.

**Where it is hosted:** The MCP server is a Python process you run yourself — locally via stdio, or on a server (Railway, VPS, Kubernetes) behind a TLS-terminating reverse proxy for HTTP. AutoCyber AI does **not** host the MCP server for you; we host the optional Gateway/Comply/Scan backends that the MCP server calls.

---

## Phase 0 — Security hygiene (do this first)

### 0.1 Rotate the exposed GitHub App private key

A GitHub App private key (`GITHUB_APP_PRIVATE_KEY`) was printed in an earlier terminal output. Treat it as compromised.

**Where to do it:**

1. Open the GitHub App settings page: `https://github.com/settings/apps/<your-app-name>` (or the org-level equivalent).
2. Click **General** → scroll to **Private keys**.
3. Click **Generate a private key**.
4. Download the `.pem` file.
5. Delete the old key.
6. Update the value in your deployment secret store / `crp_mcp/.env.hosted`.

**Do not paste the PEM into chat.** Tell me when it is rotated and I will update the env templates.

### 0.2 Confirm auth bypass is off

```bash
# Should print nothing
printenv CRP_MCP_HOSTED_BYPASS_AUTH
```

If it returns anything other than empty/`false`/`0`, unset it:

```bash
unset CRP_MCP_HOSTED_BYPASS_AUTH
```

---

## Phase 1 — Give me the values I need to wire everything together

I need the following values to build the correct `.env.hosted` and local configuration. **Do not paste secrets in this chat.** Either:

- (A) set them in `crp_mcp/.env.hosted` on disk and tell me "ready", or
- (B) share them through a secure password manager / 1Password link.

I need **exactly** these items:

### Clerk (authentication)

| Variable | What it is | Example |
|---|---|---|
| `CLERK_ISSUER` | Your Clerk issuer URL | `https://clerk.comply.crprotocol.io` |
| `CLERK_AUTHORIZED_PARTIES` | Allowed `aud`/`azp` values, space or comma separated | `https://crprotocol.io,https://dashboard.crprotocol.io` |
| `CLERK_SECRET_KEY` | Clerk backend secret | starts with `sk_test_` or `sk_live_` |
| `CLERK_PUBLISHABLE_KEY` | Frontend publishable key (optional for MCP) | starts with `pk_test_` or `pk_live_` |

### Stripe (billing)

| Variable | What it is | Example |
|---|---|---|
| `STRIPE_SECRET_KEY` | Stripe secret key | starts with `sk_test_` or `sk_live_` |
| `STRIPE_WEBHOOK_SECRET` | Webhook endpoint secret | starts with `whsec_` |
| `STRIPE_GATEWAY_DEVELOPER_PRICE_ID` | Price ID for Gateway Developer plan | `<YOUR_STRIPE_PRICE_ID>` |
| `STRIPE_GATEWAY_TEAM_PRICE_ID` | Price ID for Gateway Team plan | `<YOUR_STRIPE_PRICE_ID>` |
| `STRIPE_GATEWAY_DEVELOPER_ANNUAL_PRICE_ID` | Annual Gateway Developer price | `<YOUR_STRIPE_PRICE_ID>` |
| `STRIPE_GATEWAY_TEAM_ANNUAL_PRICE_ID` | Annual Gateway Team price | `<YOUR_STRIPE_PRICE_ID>` |
| `STRIPE_COMPLY_STARTER_PRICE_ID` | Comply Starter price | `<YOUR_STRIPE_PRICE_ID>` |
| `STRIPE_COMPLY_SCALE_PRICE_ID` | Comply Scale price | `<YOUR_STRIPE_PRICE_ID>` |
| `STRIPE_COMPLY_STARTER_ANNUAL_PRICE_ID` | Annual Comply Starter price | `<YOUR_STRIPE_PRICE_ID>` |
| `STRIPE_COMPLY_SCALE_ANNUAL_PRICE_ID` | Annual Comply Scale price | `<YOUR_STRIPE_PRICE_ID>` |
| `STRIPE_COMPLY_CREDITS_5_PRICE_ID` | Comply credit pack price | `<YOUR_STRIPE_PRICE_ID>` |
| `STRIPE_COMPLY_CREDITS_20_PRICE_ID` | Comply credit pack price | `<YOUR_STRIPE_PRICE_ID>` |
| `STRIPE_COMPLY_CREDITS_50_PRICE_ID` | Comply credit pack price | `<YOUR_STRIPE_PRICE_ID>` |

If you do not have Scan plans yet, we can leave those price IDs empty for now.

### CRP backends

| Variable | What it is | Example |
|---|---|---|
| `CRP_GATEWAY_URL` | Gateway service base URL | `https://gateway.crprotocol.io/v1` |
| `CRP_COMPLY_BASE_URL` | Comply service base URL | `https://comply.crprotocol.io` |
| `CRP_SCAN_BASE_URL` | Scan service base URL | `https://scan.crprotocol.io` |
| `CRP_PUBLIC_ORIGIN` | Public domain for status/checkout URLs | `https://crprotocol.io` |
| `CRP_HOSTED_API_KEY` | Service-to-service bearer token for backend calls | generate a 256-bit random string |

`CRP_HOSTED_API_KEY` does not exist in your current backend env files. You must create it.

### Checkpoint review channels (choose the ones you want)

You do not need all of these. Pick the minimum set that lets a human approve risky actions.

**Slack:**

- `SLACK_WEBHOOK_URL` — from `https://api.slack.com/messaging/webhooks`

**Gmail (free transactional email):**

- `GMAIL_USER` — e.g. `alerts@crprotocol.io`
- `GMAIL_APP_PASSWORD` — 16-character app password from Google Account settings
- `GMAIL_TO` — comma-separated recipient addresses

**Firebase Cloud Messaging (push):**

- `FIREBASE_SERVICE_ACCOUNT_JSON` — full service-account JSON from Firebase Project Settings → Service Accounts
- `FIREBASE_PROJECT_ID`
- `FCM_DEVICE_TOKENS` — comma-separated device registration tokens

**PagerDuty (critical incidents):**

- `PAGERDUTY_ROUTING_KEY` — integration key from a PagerDuty Events API v2 integration

### Audit & tamper evidence

| Variable | What it is | Example |
|---|---|---|
| `CRP_MCP_AUDIT_LOG` | Writable append-only JSONL path | `/var/log/crp_mcp/audit.jsonl` |
| `CRP_MCP_AUDIT_HMAC_SECRET` | Strong random secret for signing | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CRP_AUDIT_ENDPOINT` | Centralized audit sink URL | `https://comply.crprotocol.io/v1/audit` |
| `CRP_AUDIT_API_KEY` | API key for the audit sink | generate or copy from Comply |

### GitHub App (after rotating the key)

| Variable | What it is |
|---|---|
| `GITHUB_APP_ID` | Numeric app ID |
| `GITHUB_APP_CLIENT_ID` | Client ID |
| `GITHUB_APP_CLIENT_SECRET` | Client secret |
| `GITHUB_APP_PRIVATE_KEY` | The newly rotated PEM |
| `GITHUB_APP_WEBHOOK_SECRET` | Webhook secret |

---

## Phase 2 — Create the local and hosted env files

I will create these files for you once you provide the values. Until then, here is exactly what each file should contain.

### File A: `crp_mcp/.env.local`

This file is for **local stdio** development. No secrets required.

```bash
# Mode
CRP_MCP_MODE=local

# Default role: admin so developers can call every tool locally
CRP_MCP_ROLE=admin

# No Clerk, no Stripe, no live backends in local mode
# Tools automatically fall back to safe stubs and previews.

# Optional local audit file (relative path is fine for dev)
CRP_MCP_AUDIT_LOG=./crp_sessions/local_audit.jsonl

# NEVER enable in production
CRP_MCP_HOSTED_BYPASS_AUTH=false
```

### File B: `crp_mcp/.env.hosted`

This file is for **hosted stdio and hosted HTTP**. Paste the values from Phase 1 here (never commit it).

```bash
# Mode
CRP_MCP_MODE=hosted

# Role & permissions
CRP_MCP_ROLE=user
CRP_MCP_TOOLS_ALLOW=
CRP_MCP_TOOLS_DENY=

# Clerk auth
CLERK_ISSUER=https://...
CLERK_AUTHORIZED_PARTIES=https://...,https://...
CLERK_SECRET_KEY=<YOUR_CLERK_SECRET_KEY>
CLERK_PUBLISHABLE_KEY=<YOUR_CLERK_PUBLISHABLE_KEY>

# CRP backends
CRP_GATEWAY_URL=https://gateway.crprotocol.io/v1
CRP_COMPLY_BASE_URL=https://comply.crprotocol.io
CRP_SCAN_BASE_URL=https://scan.crprotocol.io
CRP_HOSTED_API_KEY=<generate-a-random-256-bit-token>
CRP_PUBLIC_ORIGIN=https://crprotocol.io

# Stripe
STRIPE_SECRET_KEY=<YOUR_STRIPE_SECRET_KEY>
STRIPE_WEBHOOK_SECRET=<YOUR_STRIPE_WEBHOOK_SECRET>
STRIPE_GATEWAY_DEVELOPER_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_GATEWAY_TEAM_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_GATEWAY_DEVELOPER_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_GATEWAY_TEAM_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_STARTER_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_SCALE_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_STARTER_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_SCALE_ANNUAL_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_CREDITS_5_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_CREDITS_20_PRICE_ID=<YOUR_STRIPE_PRICE_ID>
STRIPE_COMPLY_CREDITS_50_PRICE_ID=<YOUR_STRIPE_PRICE_ID>

# Audit & tamper evidence
CRP_MCP_AUDIT_LOG=/var/log/crp_mcp/audit.jsonl
CRP_MCP_CHECKPOINT_LOG=/var/log/crp_mcp/checkpoints.jsonl
CRP_MCP_AUDIT_HMAC_SECRET=<generate-a-random-secret>
CRP_AUDIT_ENDPOINT=https://comply.crprotocol.io/v1/audit
CRP_AUDIT_API_KEY=<audit-sink-api-key>

# Checkpoints
CRP_MCP_CHECKPOINT_CONNECTORS=console,slack,gmail
CRP_MCP_CHECKPOINT_ESCALATION=[{"after_seconds":900,"channels":["slack"]},{"after_seconds":3600,"on_timeout":"reject"}]
CRP_MCP_CHECKPOINT_ROUTES=[{"condition":"risk >= HIGH","connector":"slack","route_to":"#safety"},{"condition":"tool_call == 'deploy_endpoint'","connector":"pagerduty"}]

# Review-channel connectors (fill in the ones you chose)
SLACK_WEBHOOK_URL=<YOUR_SLACK_WEBHOOK_URL>

GMAIL_USER=alerts@crprotocol.io
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
GMAIL_TO=team@crprotocol.io,ops@crprotocol.io

FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
FIREBASE_PROJECT_ID=your-project-id
FCM_DEVICE_TOKENS=token1,token2

PAGERDUTY_ROUTING_KEY=

# GitHub App (for crp_connect_repo_link)
GITHUB_APP_ID=
GITHUB_APP_CLIENT_ID=
GITHUB_APP_CLIENT_SECRET=
GITHUB_APP_PRIVATE_KEY="<YOUR_GITHUB_APP_PRIVATE_KEY_PEM>"
GITHUB_APP_WEBHOOK_SECRET=

# NEVER enable in production
CRP_MCP_HOSTED_BYPASS_AUTH=false
```

### File C: `.gitignore` (confirm these lines exist)

```gitignore
crp_mcp/.env.local
crp_mcp/.env.hosted
crp_*_railway.env
.env
```

If they are missing, tell me and I will add them.

---

## Phase 3 — Local stdio mode

This is the fastest way to develop and test the MCP server from Claude Code, Cursor, or any stdio MCP client.

### 3.1 Run the server

```bash
cd C:/Users/User/Desktop/context-relay-protocol
.venv/Scripts/python -m crp_mcp.server
```

Expected behaviour:

- Server starts without errors.
- stdout is the MCP transport; no application logs go to stdout.
- `CRP_MCP_MODE` defaults to `local`.

### 3.2 Connect from Claude Code / Cursor

Add a configuration like this:

**Claude Code:**

```json
{
  "mcpServers": {
    "crp-local": {
      "command": "C:/Users/User/Desktop/context-relay-protocol/.venv/Scripts/python",
      "args": ["-m", "crp_mcp.server"],
      "env": {
        "CRP_MCP_MODE": "local"
      }
    }
  }
}
```

**Cursor:**

In Settings → MCP, add:

```json
{
  "name": "crp-local",
  "command": "C:/Users/User/Desktop/context-relay-protocol/.venv/Scripts/python -m crp_mcp.server",
  "env": {
    "CRP_MCP_MODE": "local"
  }
}
```

### 3.3 Sanity checks in local mode

Ask the agent to run these tools:

```text
Use crp_quickstart to show me how to integrate CRP.
Use crp_explain with topic="context envelope".
Use crp_generate_config to create a balanced CRP config.
Use crp_safety_checkpoint with trigger="TEST" and confirm=false.
```

Expected results:

- `crp_quickstart` returns an integration checklist.
- `crp_explain` returns a spec-grounded explanation.
- `crp_generate_config` returns a YAML config.
- `crp_safety_checkpoint` returns a preview checkpoint (no real alert sent).

---

## Phase 4 — Local HTTP mode

Use this for local testing of HTTP clients or when you want to test the Streamable HTTP transport without Clerk.

### 4.1 Run with hosted transport but no Clerk

```bash
cd C:/Users/User/Desktop/context-relay-protocol
# Leave Clerk env unset so auth middleware stays disabled
CRP_MCP_MODE=hosted PORT=8000 .venv/Scripts/python -m crp_mcp.server
```

Because `CLERK_ISSUER`/`CLERK_SECRET_KEY` are not set, `hosted_available()` returns `False`, so:

- Transport is `streamable_http`.
- Auth middleware is **not** enabled.
- Backend tools fall back to safe stubs.

### 4.2 Test with curl

```bash
curl -N http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Expected: a JSON-RPC response listing tools.

---

## Phase 5 — Hosted stdio mode

Use this when the client itself handles authentication and passes a Bearer token through the MCP context.

### 5.1 Run with the hosted env file

```bash
cd C:/Users/User/Desktop/context-relay-protocol
# On Linux/macOS:
set -a && source crp_mcp/.env.hosted && set +a
# On Windows PowerShell:
# Get-Content crp_mcp/.env.hosted | ForEach-Object { if ($_ -match "^([^#][^=]+)=(.*)$") { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process") } }
.venv/Scripts/python -m crp_mcp.server
```

Expected:

- Server starts.
- If Clerk env is valid, FastMCP Bearer auth middleware is active.
- Any request without a valid Clerk JWT is rejected at the transport layer.

### 5.2 Connect a stdio client with a token

Most stdio MCP clients do not natively pass Bearer tokens. For testing, you can use the `CRP_MCP_HOSTED_BYPASS_AUTH=1` flag **only in a private test environment**:

```bash
CRP_MCP_HOSTED_BYPASS_AUTH=1 .venv/Scripts/python -m crp_mcp.server
```

Then call a hosted tool:

```text
Use crp_whoami.
Use crp_create_api_key with name="test-key" and confirm=false.
```

Expected:

- `crp_whoami` returns identity/plan info.
- `crp_create_api_key` returns `requires_confirmation: true`.

**Remove the bypass before production.**

---

## Phase 6 — Hosted HTTP mode

This is the production deployment shape.

### 6.1 Run the server

```bash
cd C:/Users/User/Desktop/context-relay-protocol
# Load env as shown in Phase 5
CRP_MCP_MODE=hosted PORT=8000 .venv/Scripts/python -m crp_mcp.server
```

### 6.2 Put a TLS-terminating reverse proxy in front

Never expose port 8000 directly.

**Caddy example:**

```caddy
mcp.crprotocol.io {
    reverse_proxy localhost:8000
}
```

**Nginx example:**

```nginx
server {
    listen 443 ssl http2;
    server_name mcp.crprotocol.io;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
    }
}
```

### 6.3 Connect an HTTP MCP client

Clients must send a valid Clerk session JWT as a Bearer token in the `Authorization` header.

```bash
curl -N https://mcp.crprotocol.io/mcp \
  -H "Authorization: Bearer <clerk_session_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

---

## Phase 7 — Backend service-to-service key

`CRP_HOSTED_API_KEY` is missing from your current env files. Create it now.

### 7.1 Generate the key

```bash
.venv/Scripts/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 7.2 Where to set it

- **Railway:** add `CRP_HOSTED_API_KEY` as a variable to the MCP service and to the Gateway/Comply/Scan services so they accept it.
- **Local env:** add it to `crp_mcp/.env.hosted`.

### 7.3 Verify backend reachability

After setting it, run:

```bash
.venv/Scripts/python scripts/validate_crp_mcp.py
```

Expected: the ❌ items for Gateway/Comply/Scan turn into ✅ status codes.

---

## Phase 8 — Checkpoint review channels

The validator currently shows only the `console` connector configured. To enable real human-in-the-loop approvals, configure at least one additional channel.

### 8.1 Minimum viable free stack

Set these three and update the connector list:

```bash
CRP_MCP_CHECKPOINT_CONNECTORS=console,slack,gmail
SLACK_WEBHOOK_URL=<YOUR_SLACK_WEBHOOK_URL>
GMAIL_USER=alerts@crprotocol.io
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
GMAIL_TO=team@crprotocol.io
```

### 8.2 Test a real checkpoint

Run the server with the hosted env and ask the agent:

```text
Use crp_safety_checkpoint with trigger="DEPLOYMENT", message="Approve production deploy?", confirm=true.
```

Expected:

- A Slack message and email are sent.
- The checkpoint appears in `CRP_MCP_CHECKPOINT_LOG`.
- Approving via Slack/email/Comply UI resolves the checkpoint.

### 8.3 Escalation policy

The default escalation in `.env.hosted` is:

```bash
CRP_MCP_CHECKPOINT_ESCALATION=[{"after_seconds":900,"channels":["slack"]},{"after_seconds":3600,"on_timeout":"reject"}]
```

This means:

- After 15 minutes, re-notify Slack.
- After 1 hour, auto-reject the checkpoint (fail-safe).

Adjust `after_seconds` and channels to your team.

---

## Phase 9 — Audit, monitoring, and alerts

### 9.1 Audit log

Ensure the directory exists and is writable:

```bash
# Linux/macOS
mkdir -p /var/log/crp_mcp
chmod 750 /var/log/crp_mcp

# Windows (PowerShell run as admin)
New-Item -ItemType Directory -Path "C:\ProgramData\crp_mcp" -Force
```

Set:

```bash
CRP_MCP_AUDIT_LOG=/var/log/crp_mcp/audit.jsonl
```

### 9.2 Audit signatures

Generate and set:

```bash
.venv/Scripts/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set:

```bash
CRP_MCP_AUDIT_HMAC_SECRET=<the-generated-secret>
```

### 9.3 Audit forwarder

If your Comply service exposes an audit sink:

```bash
CRP_AUDIT_ENDPOINT=https://comply.crprotocol.io/v1/audit
CRP_AUDIT_API_KEY=<comply-audit-api-key>
```

Records are POSTed fire-and-forget to `{CRP_AUDIT_ENDPOINT}/events`.

### 9.4 Log rotation

Add a `logrotate` config:

```bash
# /etc/logrotate.d/crp_mcp
/var/log/crp_mcp/*.jsonl {
    daily
    rotate 365
    compress
    delaycompress
    missingok
    notifempty
    create 0640 crp crp
}
```

### 9.5 Recommended alerts

| Alert | How to detect |
|---|---|
| Auth bypass enabled | `printenv CRP_MCP_HOSTED_BYPASS_AUTH` returns non-empty |
| Spike in permission denials | grep `allowed=false` in audit log |
| Checkpoint timeout rate > 5% | grep `checkpoint_timeout` in audit log |
| Audit forwarder lag | compare log timestamp to arrival time at `CRP_AUDIT_ENDPOINT` |

---

## Phase 10 — Enable AI agents to build with CRP

The MCP server is designed to be the CRP "co-builder". Agents should use these tools in order.

### 10.1 Discovery

| Tool | Purpose |
|---|---|
| `crp_quickstart` | Onboarding checklist |
| `crp_explain` | Spec-grounded explanations |
| `crp_spec_lookup` | Fetch a specific spec by ID |
| `crp_list_specs` | Browse the spec corpus |
| `crp_list_topics` | Browse protocol topics |

### 10.2 Design & scaffold

| Tool | Purpose |
|---|---|
| `crp_generate_config` | Generate a `crp.config.yaml` |
| `crp_validate_config` | Validate a config against the schema |
| `crp_scaffold_integration` | Produce integration code |
| `crp_sdk_example` | Copy-paste SDK snippet |
| `crp_build_integration_plan` | Step-by-step integration plan |
| `crp_generate_gateway_compose` | Docker Compose for Gateway |
| `crp_generate_scan_workflow` | CI workflow for scanning |

### 10.3 Safety & governance

| Tool | Purpose |
|---|---|
| `crp_generate_safety_policy` | Create a CRP-Safety-Policy directive |
| `crp_validate_safety_policy` | Validate a policy |
| `crp_safety_checkpoint` | Pause for human approval |
| `crp_safety_checkpoint_when` | Auto-fire checkpoint on policy condition |
| `crp_resolve_checkpoint` | Resolve a checkpoint programmatically |
| `crp_safety_registry` | Browse safety capabilities |

### 10.4 Account & operations (hosted only)

| Tool | Purpose |
|---|---|
| `crp_whoami` | Current identity and plan |
| `crp_get_plan` | Entitlements |
| `crp_create_api_key` | Mint a Gateway API key |
| `crp_test_call` | Test Gateway |
| `crp_deploy_endpoint` | Deploy a Gateway endpoint |
| `crp_scan_repo` / `crp_scan_status` / `crp_scan_report` | Repo scanning |
| `crp_comply_repo` / `crp_comply_status` / `crp_comply_diff` | Compliance analysis |
| `crp_connect_repo_link` | Link a GitHub repo via the GitHub App |
| `crp_upgrade_link` | Stripe checkout for plan upgrades |

### 10.5 Prompts

| Prompt | Use |
|---|---|
| `discover_crp` | First-time user intro |
| `integrate_crp` | Walk through adding CRP to a stack |
| `write_safety_policy` | Generate a safety policy |
| `context_strategy_for_task` | Recommend context settings |
| `audit_ai_calls` | Audit a codebase for ungoverned AI calls |

---

## Phase 11 — Verification matrix

Run these before every deployment.

```bash
# 1. Tests
cd C:/Users/User/Desktop/context-relay-protocol
.venv/Scripts/python -m pytest tests/test_crp_mcp.py tests/test_crp_mcp_coverage.py tests/test_crp_mcp_permissions.py tests/test_sdk_namespaces.py tests/test_crp_mcp_auth.py tests/test_crp_mcp_connectors.py tests/test_crp_mcp_checkpoint.py tests/test_crp_mcp_checkpoint_policy.py tests/test_crp_mcp_billing.py tests/test_crp_mcp_backends.py tests/test_checkpoint_inbox.py tests/test_safety_control_plane.py -q
# Expected: 237 passed

# 2. Lint
.venv/Scripts/python -m ruff check crp_mcp/server.py crp_mcp/types.py crp_mcp/permissions.py crp_mcp/resources.py crp_mcp/checkpoint_service.py crp_mcp/checkpoint_policy.py crp_mcp/safety_tools.py crp_mcp/auth.py crp_mcp/billing.py crp_mcp/backend_client.py scripts/validate_crp_mcp.py tests/test_crp_mcp_permissions.py tests/test_crp_mcp_coverage.py tests/test_crp_mcp_checkpoint.py tests/test_crp_mcp_checkpoint_policy.py tests/test_crp_mcp_auth.py tests/test_crp_mcp_billing.py tests/test_crp_mcp_backends.py tests/test_crp_mcp_connectors.py
# Expected: no errors

# 3. Docs build
DISABLE_MKDOCS_2_WARNING=true .venv/Scripts/python scripts/audit_docs.py
# Expected: no findings

# 4. Production readiness validator
.venv/Scripts/python scripts/validate_crp_mcp.py
# Expected: no ❌ items

# 5. Manual stdio smoke test (local)
CRP_MCP_MODE=local .venv/Scripts/python -m crp_mcp.server
# Then ask the agent to run crp_quickstart and crp_safety_checkpoint.

# 6. Manual HTTP smoke test (hosted auth disabled for this test only)
CRP_MCP_MODE=hosted PORT=8000 .venv/Scripts/python -m crp_mcp.server
curl -N http://localhost:8000/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# 7. Confirm bypass auth is off
printenv CRP_MCP_HOSTED_BYPASS_AUTH
# Expected: empty
```

---

## Phase 12 — Go-live runbook

1. **Staging (Day -7):**
   - Deploy with Clerk test tenant, Stripe test mode, and real but non-production backends.
   - Run the verification matrix.
   - Send a real checkpoint through Slack/Gmail.

2. **Secret rotation (Day -1):**
   - Rotate `CLERK_SECRET_KEY`, `STRIPE_SECRET_KEY`, `CRP_HOSTED_API_KEY`, `CRP_AUDIT_API_KEY`, and `GITHUB_APP_PRIVATE_KEY`.
   - Confirm `CRP_MCP_HOSTED_BYPASS_AUTH` is unset.

3. **Production (Day 0):**
   - Deploy with `CRP_MCP_ROLE=user`.
   - Enable audit log and audit forwarder.
   - Set `CRP_MCP_TOOLS_DENY` for any tools the deployment does not need.

4. **Post-launch (Day +1 to +7):**
   - Monitor permission denials, audit volume, checkpoint resolution times.
   - Review first week audit sample for anomalies.

---

## What I need from you right now

To progress from code-complete to running in all four modes, provide me with:

1. **Confirmation** that the GitHub App private key has been rotated.
2. Either:
   - the filled-in `crp_mcp/.env.hosted` file (do not commit it), or
   - a secure list of the Phase 1 values.
3. **Decision** on which checkpoint connectors you want enabled (Slack, Gmail, FCM, PagerDuty, SMS).
4. **Decision** on the public origin (`https://crprotocol.io` or a subdomain like `https://mcp.crprotocol.io`).
5. **Decision** on whether you want a dedicated hosted HTTP deployment subdomain or just stdio for now.

Once I have those, I will:

- Create `crp_mcp/.env.local` and `crp_mcp/.env.hosted`.
- Update `crp_mcp/.env.example` if any new variables are needed.
- Generate a `CRP_HOSTED_API_KEY` for you.
- Update the production checklist and run the full verification matrix.
- Test local stdio, local HTTP, hosted stdio, and hosted HTTP end-to-end.
