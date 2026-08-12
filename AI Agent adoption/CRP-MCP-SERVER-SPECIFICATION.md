# CRP MCP Server — Full Specification & Implementation (Python, Authenticated, OWASP-Aligned)

**For:** the developer who owns and will implement the CRP MCP server
**From:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd
**Stack:** Python, FastMCP (official MCP Python SDK). Local = stdio; Hosted = Streamable HTTP.
**Security baseline:** OWASP MCP Top 10 (2025, v0.1) — every item mapped to a control below.
**Status:** specification + initial implementation in `crp_mcp/`. Sections marked
**[DEV-NOTE]** are where backend-specific wiring (Clerk, Stripe, live Gateway calls) must be
completed — they are called out deliberately rather than hand-waved.

**Implementation quickstart:**
```bash
pip install -e ".[mcp]"
crp-mcp                              # local stdio mode
CRP_MCP_MODE=hosted crp-mcp          # hosted Streamable HTTP mode
```

---

## 0. HOW TO READ THIS DOCUMENT
- §1 capability split (local vs hosted) — the contract.
- §2 the tool catalogue with exact modes, annotations, auth, and HITL.
- §3 authentication (the hosted tier) — device-flow + token verification.
- §4 the OWASP MCP Top 10 mapping — the security spine. Do not skip.
- §5 human-in-the-loop policy.
- §6 the Python implementation skeleton.
- §7 deployment, §8 testing, §9 the DEV-NOTE register (everything to finish/research).

---

## 1. CAPABILITY SPLIT — LOCAL vs HOSTED (the contract)

### 1.1 LOCAL server (stdio) — runs on the developer's machine
**Purpose:** learning, building, developing, and static verification. No CRP account, no
network to CRP, no secrets. Pure knowledge + code generation + local validation.

**Can do:**
- Explain any CRPv4 concept; look up/cite the specs; compare CRP to MCP/A2A/AIPREF.
- Scaffold an integration (the base_url swap + minimal config) for a stack.
- Generate a `crp.config.yaml` / Safety Policy from plain-language intent.
- Generate SDK snippets; give v3→v4 migration guidance.
- Validate a config against the schema; lint `CRP-*` header usage; run conformance
  vectors — all locally, on text the user provides.

**Cannot do (by design):**
- Touch any CRP account, tenant, plan, or billing.
- Run a live governed call, deploy anything, or read user data.
- Hold or transmit any secret.

**Why local:** zero infra cost, offline, private, no attack surface against CRP. This is
where most agent interaction happens and it needs no trust.

### 1.2 HOSTED server (Streamable HTTP @ mcp.crprotocol.io) — operated by AutoCyber AI
**Purpose:** account-linked and live-runtime actions. Requires authentication; gated by
the user's CRP entitlement; metered against their plan.

**Can do (all require auth, see §3):**
- `crp_whoami` — report the signed-in user's products/plans/quotas.
- `crp_get_plan` — current Gateway/Comply/Scan plan + remaining quota.
- `crp_create_api_key` — mint a scoped, revocable Gateway API key (HITL-confirmed).
- `crp_test_call` — run ONE real governed call and return the governance panel
  (risk/grounding/halt/sources). Metered against the user's plan.
- `crp_deploy_endpoint` — deploy a built pipeline as a live endpoint (HITL-confirmed;
  entitlement-gated).
- `crp_benchmark` — run an SQB-style quality check (metered).

**Signup & billing = REDIRECT ONLY (no in-protocol account creation or payment):**
- `crp_signup_link` — returns the signup URL for the human to open. Does NOT create an account.
- `crp_upgrade_link` — returns the Stripe Checkout URL for a chosen plan. Does NOT take payment.
- `crp_connect_repo_link` — returns the GitHub App install URL. Does NOT install.
These tools **only return links**; the human completes auth/payment/installation in their
own browser. The agent never holds credentials, never pays, never creates accounts.

**Why hosted:** these need the user's identity, their entitlement, and your runtime —
none of which can or should live on a local stdio server.

### 1.3 The one-package, two-mode rule
Ship ONE Python package. An env flag (`CRP_MCP_MODE=local|hosted`) selects mode. Hosted-only
tools, if called in local mode, return a clear message: "This action needs the hosted CRP
MCP server and sign-in. Connect to https://mcp.crprotocol.io." Local tools also run within
the hosted server (superset).

---

## 2. TOOL CATALOGUE (modes, annotations, auth, HITL)

Legend: **Mode** L=local-ok, H=hosted+auth. **HITL** = human-in-the-loop required.

| Tool | Mode | readOnly | destructive | Auth | HITL | Purpose |
|------|------|----------|-------------|------|------|---------|
| `crp_explain` | L | ✓ | ✗ | none | no | explain a CRPv4 concept (cited) |
| `crp_spec_lookup` | L | ✓ | ✗ | none | no | retrieve authoritative spec text |
| `crp_compare` | L | ✓ | ✗ | none | no | CRP vs MCP/A2A/AIPREF/vector-DB |
| `crp_scaffold_integration` | L | ✓ | ✗ | none | no | generate integration code |
| `crp_generate_config` | L | ✓ | ✗ | none | no | crp.config.yaml from intent |
| `crp_generate_safety_policy` | L | ✓ | ✗ | none | no | Safety Policy from intent |
| `crp_sdk_example` | L | ✓ | ✗ | none | no | SDK snippet for a task |
| `crp_migrate_v3_v4` | L | ✓ | ✗ | none | no | migration guidance |
| `crp_validate_config` | L | ✓ | ✗ | none | no | validate config vs schema |
| `crp_lint_headers` | L | ✓ | ✗ | none | no | lint CRP-* usage |
| `crp_conformance_check` | L | ✓ | ✗ | none | no | run conformance vectors |
| `crp_whoami` | H | ✓ | ✗ | yes | no | who is signed in + plans |
| `crp_get_plan` | H | ✓ | ✗ | yes | no | plan + quota |
| `crp_signup_link` | H | ✓ | ✗ | none* | no | RETURN signup link only |
| `crp_upgrade_link` | H | ✓ | ✗ | yes | no | RETURN Stripe checkout link only |
| `crp_connect_repo_link` | H | ✓ | ✗ | yes | no | RETURN GitHub App install link only |
| `crp_create_api_key` | H | ✗ | ✗ | yes | YES | mint a Gateway API key |
| `crp_test_call` | H | ✗ | ✗ | yes | YES | run ONE real governed call (metered) |
| `crp_deploy_endpoint` | H | ✗ | ✓ | yes | YES | deploy a pipeline as a live endpoint |
| `crp_benchmark` | H | ✗ | ✗ | yes | YES | run an SQB-style check (metered) |

*`crp_signup_link` needs no auth because the user has no account yet; it only returns a URL.

**Annotation rule:** annotations are HINTS, not security (per MCP spec). Real enforcement is
in §3/§4 — never gate security on an annotation.

**[DEV-NOTE 2a]** Decide whether `crp_test_call` should be allowed at all on the free tier
(it consumes a real provider call). Recommendation: allow a small free quota, then require
upgrade — but confirm the cost model with your provider economics.

---

## 3. AUTHENTICATION (hosted tier) — device-flow + token verification

### 3.1 The model
The hosted server authenticates the END USER to their CRP account using a **device
authorization flow** (RFC 8628 style), because the caller is an AI agent in a client the
user controls, not a browser. The agent never sees a password or a long-lived token.

```
1. Agent calls crp_signup_link or, if the user has an account, crp_link_start
2. Server returns: a short user_code + a verification_url (https://crprotocol.io/device)
3. Human opens the URL in their browser, signs in with Clerk, approves the connection
4. Server (polling or callback) exchanges the device code for a SESSION-SCOPED token
   bound to that Clerk user/org, with a short TTL
5. Subsequent hosted tool calls present that session token; server verifies it per call
```

### 3.2 Token verification (every hosted call)
- The server verifies the Clerk-issued session/JWT on EVERY hosted tool call against the
  Clerk JWKS (`https://clerk.crprotocol.io/.well-known/jwks.json`), checking issuer and
  expiry, and **`authorized_parties`** to prevent subdomain token reuse (see §4 MCP07).
- Tokens are **session-scoped and short-lived**; never long-lived, never stored in logs,
  never returned to the agent in full.
- The session token authorizes the server to act for that tenant; the server then reads
  entitlement from Clerk metadata and gates accordingly.

### 3.3 What the agent holds vs what the server holds
- **Agent holds:** a short-lived session reference (opaque), nothing else.
- **Server holds:** the verification logic + the ability to mint short-lived CRP/GitHub
  installation tokens on demand (never persisted) — exactly as in the CRP auth + GitHub
  solution docs.
- **Neither holds:** the user's provider keys (vaulted per-tenant in CRP), the user's
  password, or any long-lived secret.

**[DEV-NOTE 3a]** Implement the device-flow endpoints on the CRP side
(`/device`, `/device/token`) — this is real work; see RFC 8628. Clerk may offer a flow that
helps; **research whether Clerk supports a device-authorization or CLI-style flow directly**,
otherwise implement the code/exchange table yourself (short TTL, one-time use, rate-limited).

**[DEV-NOTE 3b]** Decide session-token TTL and refresh behaviour. Recommendation: short
(e.g. 1 hour), no silent refresh for destructive tools — re-confirm for high-risk actions.

---

## 4. OWASP MCP TOP 10 (2025) — MAPPED TO CONTROLS

Every item from the OWASP MCP Top 10 with the concrete control in THIS server. This is the
security spine — implement all of it.

### MCP01 — Token Mismanagement & Secret Exposure
- No hard-coded credentials anywhere; all secrets via env/secret manager.
- Session tokens short-lived + scoped; provider keys never touch the MCP server (vaulted in
  CRP per-tenant). Tokens never logged, never returned in full to the agent.
- Local server holds NO secrets at all.
- **Control:** secret-scanning in CI on this repo; deny-list token patterns in any logged output.

### MCP02 — Privilege Escalation via Scope Creep
- Each hosted tool checks the SPECIFIC entitlement/feature it needs (e.g. `deploy_endpoint`)
  from Clerk metadata; no blanket "is authed → can do anything".
- API keys minted by `crp_create_api_key` are scoped + revocable; default least-privilege.
- **Control:** session tokens carry no standing privilege beyond the tenant; every action
  re-checks entitlement at call time, not at session start.

### MCP03 — Tool Poisoning (rug pulls, schema poisoning, tool shadowing)
- Pin tool schemas; version the server; publish signed releases (see MCP04).
- `crp_explain`/`crp_spec_lookup` answer ONLY from the authoritative CRP spec corpus (an ADA,
  SPEC-044) and must refuse to fabricate — so a poisoned context can't make them invent
  capabilities.
- **Control:** the spec corpus the LEARN tools read is integrity-checked (hash-pinned) so a
  tampered local copy is detected.
- **[DEV-NOTE 4a]** Decide how the local server gets the spec corpus (bundled vs fetched).
  If fetched, verify a signature/hash. If bundled, version it with the release.

### MCP04 — Software Supply Chain Attacks & Dependency Tampering
- Pin all dependencies (hashes); monitor with a vulnerability scanner; sign releases.
- Publish provenance for the PyPI package (`crp-mcp`).
- **[DEV-NOTE 4b]** Set up signed releases + SBOM + dependency monitoring in CI. Research
  PyPI Trusted Publishing + Sigstore for provenance.

### MCP05 — Command Injection & Execution
- The server NEVER executes shell/system commands built from tool inputs.
- `crp_scaffold_integration`/`crp_generate_*` RETURN code as text; they do not run it.
- Config validation parses with a safe YAML loader (`yaml.safe_load`), never `eval`/exec.
- **Control:** no `subprocess`, no `os.system`, no `eval`/`exec` anywhere with user input.
  (Repo scanning/cloning, if ever added here, uses the GitHub-solution token flow, not shell
  interpolation — but note repo cloning belongs in Comply/Scan, not this server.)

### MCP06 — Prompt Injection via Contextual Payloads / Intent Flow Subversion
- The LEARN tools treat retrieved spec text as DATA, not instructions; they summarise/cite,
  never execute embedded instructions.
- Tool outputs are clearly delimited and labelled as data.
- Destructive/account tools require explicit HITL confirmation (§5) so an injected
  instruction in some context cannot silently trigger a deploy/key-mint/payment.
- **Control:** HITL on every state-changing tool is the primary defence against intent-flow
  subversion — a hijacked "intent" still cannot act without the human's explicit approval.

### MCP07 — Insufficient Authentication & Authorization
- Every hosted tool verifies the Clerk token per call (issuer, expiry, signature, JWKS).
- **`authorized_parties` set** to the CRP subdomains to prevent cross-subdomain token reuse
  (the documented Clerk subdomain risk).
- Authorization (entitlement) checked per action, not just authentication.
- Local tools expose nothing sensitive, so they need no auth.
- **[DEV-NOTE 7a]** Implement and TEST token verification carefully; this is the highest-risk
  area. Use Clerk's backend SDK / JWKS verification; do not roll your own crypto.

### MCP08 — Lack of Audit and Telemetry
- Log every hosted tool invocation (who/tenant, which tool, when, allowed/denied, metered
  units) to an immutable audit store — reuse CRP's HMAC audit chain (SPEC-011) where possible.
- Never log secrets or full tokens or user data; log identifiers + outcomes.
- **Control:** alert on anomalies (e.g. repeated denied entitlement checks, burst of
  key-mints). **[DEV-NOTE 8a]** Define the alerting thresholds + where logs go.

### MCP09 — Shadow MCP Servers
- ONE official hosted endpoint (`mcp.crprotocol.io`) and ONE published package (`crp-mcp`).
- Document the official endpoints so users can verify they're connecting to the real one.
- Hosted server bound correctly (not `0.0.0.0` in local; TLS only in hosted) with Origin
  validation (see below).
- **Control:** publish the official server identity/fingerprint in docs so a rogue/typo-
  squatted server is detectable. **[DEV-NOTE 9a]** Register/defend the package name and
  watch for typosquats.

### MCP10 — Context Injection & Over-Sharing
- Strict per-tenant isolation: a session token only ever accesses its own tenant's data;
  no tool returns another tenant's information.
- Tool outputs are minimal — return what's needed, not whole records (data minimisation).
- No shared/persistent context across users on the hosted server.
- **Control:** every hosted data path filtered by the authenticated tenant id; review each
  tool's output for over-sharing.

### Cross-cutting (best-practice baseline)
- **Input validation:** Pydantic models on every tool (constraints, types, `extra='forbid'`).
- **DNS-rebinding / Origin (hosted, esp. if ever local-HTTP):** validate the `Origin`
  header; bind local HTTP to `127.0.0.1`; TLS for the hosted endpoint.
- **Rate limiting:** per-tenant and per-IP on the hosted server.
- **Error handling:** actionable messages to the agent; never leak internals/stack traces.

---

## 5. HUMAN-IN-THE-LOOP (HITL) POLICY

HITL is REQUIRED for any tool that changes state, spends money/quota, or creates
credentials. The agent must surface a confirmation the human approves before the action
runs. Specifically:

| Action | HITL requirement |
|--------|------------------|
| Signup / upgrade / connect-repo | The tool returns a LINK; the human acts in their browser. (HITL is inherent — the human does it, not the agent.) |
| `crp_create_api_key` | Explicit confirm: "Create a new Gateway API key for <tenant>? It grants API access." |
| `crp_deploy_endpoint` | Explicit confirm: "Deploy pipeline <id> as a LIVE endpoint? This goes to production and may consume quota." |
| `crp_test_call` | Confirm + cost notice: "Run a real governed call? Uses 1 of your <N> remaining free calls." |
| `crp_benchmark` | Confirm + cost notice (metered). |

Implementation: use the MCP client's confirmation/elicitation capability where available;
otherwise the tool returns a "requires confirmation" result the agent must echo and the user
must approve before a second, explicit call proceeds.

**[DEV-NOTE 5a]** MCP client support for human confirmation/elicitation varies. Research the
current MCP spec elicitation capability and the behaviour of your target clients (Claude
Code, Cursor). Implement a fallback "confirm token" pattern (tool returns
`{requires_confirmation:true, confirm_token}`; the human-approved second call passes the
token) so HITL holds even on clients without native confirmation UI.

---

## 6. PYTHON IMPLEMENTATION SKELETON (FastMCP)

> Reference skeleton. Fill the **[DEV-NOTE]** points. Uses Pydantic input models, per-tool
> annotations, centralised auth + entitlement, and the local/hosted split.

```python
# crp_mcp/server.py
import os, json, hmac, hashlib
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP, Context

# ---- local building blocks (no secrets, no network to CRP) ----
from crp.specs import lookup_spec          # ADA over the CRP spec corpus (SPEC-044); cites, refuses to fabricate
from crp.config import validate_config     # schema validation (yaml.safe_load only)
from crp import scaffolding                 # code/config generators (return text, never execute)

MODE = os.getenv("CRP_MCP_MODE", "local")  # "local" | "hosted"
HOSTED = MODE == "hosted"

mcp = FastMCP("crp_mcp")

# =======================================================================
# Shared helpers (DRY) — formatting, errors, auth, entitlement
# =======================================================================
def err(msg: str) -> str:
    return json.dumps({"error": msg})

def require_hosted():
    if not HOSTED:
        raise PermissionError(
            "This action needs the hosted CRP MCP server and sign-in. "
            "Connect to https://mcp.crprotocol.io and run crp_signup_link if you don't have an account."
        )

# --- AUTH: verify the Clerk session token on every hosted call (MCP07) ---
# [DEV-NOTE 7a] Implement with Clerk's backend verification / JWKS. Pseudocode:
def authenticate(ctx: Context) -> "Identity":
    require_hosted()
    token = _extract_session_token(ctx)          # from the request context / header
    if not token:
        raise PermissionError("Not signed in. Run crp_signup_link or crp_link_start first.")
    claims = _verify_clerk_jwt(                   # verify signature, issuer, expiry, authorized_parties
        token,
        issuer=os.environ["CLERK_ISSUER"],                       # https://clerk.crprotocol.io
        jwks_url=f'{os.environ["CLERK_ISSUER"]}/.well-known/jwks.json',
        authorized_parties=os.environ["CLERK_AUTHORIZED_PARTIES"].split(","),
    )
    return Identity(user_id=claims["sub"], org_id=claims.get("org_id"),
                    org_role=claims.get("org_role"))

def get_entitlement(identity, product: str) -> dict:
    # read plan/quota/features from Clerk metadata (per the auth solution doc)
    ...

def require_feature(identity, product: str, feature: str):
    ent = get_entitlement(identity, product)
    if feature not in ent.get("features", []):
        raise PermissionError(f"upgrade_required:{product}:{feature}")
    return ent

def audit(identity, tool: str, outcome: str, **fields):
    # MCP08: immutable audit log; NEVER log secrets/tokens/user data — ids + outcomes only.
    ...

# =======================================================================
# LOCAL tools (no auth) — LEARN / BUILD / DEVELOP / VERIFY(static)
# =======================================================================
class ExplainInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    topic: str = Field(..., description="A CRPv4 concept or spec, e.g. 'CDR', 'STL', 'safety policy'", min_length=1, max_length=200)

@mcp.tool(name="crp_explain",
    annotations={"title":"Explain a CRP concept","readOnlyHint":True,"destructiveHint":False,"idempotentHint":True,"openWorldHint":False})
async def crp_explain(params: ExplainInput) -> str:
    '''Explain a CRPv4 concept, grounded in and cited from the authoritative CRP specs.
    Returns a concise explanation; refuses to invent capabilities CRP does not have.'''
    return lookup_spec(params.topic, mode="explain")     # MCP03/06: data not instructions; cited

class ScaffoldInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    stack: str = Field(..., description="Target stack, e.g. 'python-openai', 'node-openai', 'langchain'", min_length=1, max_length=60)
    goal: str = Field(default="govern all LLM calls", description="What the integration should achieve", max_length=300)

@mcp.tool(name="crp_scaffold_integration",
    annotations={"title":"Scaffold a CRP integration","readOnlyHint":True,"destructiveHint":False,"idempotentHint":True,"openWorldHint":False})
async def crp_scaffold_integration(params: ScaffoldInput) -> str:
    '''Generate integration code (the base_url swap + minimal config) for the given stack.
    Returns code as TEXT; it is never executed (MCP05).'''
    return scaffolding.integration(stack=params.stack, goal=params.goal)

class ValidateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    yaml_text: str = Field(..., description="A crp.config.yaml document to validate", min_length=1, max_length=20000)

@mcp.tool(name="crp_validate_config",
    annotations={"title":"Validate a CRP config","readOnlyHint":True,"destructiveHint":False,"idempotentHint":True,"openWorldHint":False})
async def crp_validate_config(params: ValidateInput) -> str:
    '''Validate a crp.config.yaml against the schema. Returns {valid, errors}. Uses safe YAML
    parsing only (MCP05).'''
    return json.dumps(validate_config(params.yaml_text))

# (crp_spec_lookup, crp_compare, crp_generate_config, crp_generate_safety_policy,
#  crp_sdk_example, crp_migrate_v3_v4, crp_lint_headers, crp_conformance_check
#  follow the same pattern — local, read-only, Pydantic-validated, return text.)

# =======================================================================
# HOSTED tools — REDIRECT-ONLY onboarding (no account creation / no payment)
# =======================================================================
@mcp.tool(name="crp_signup_link",
    annotations={"title":"Get a CRP signup link","readOnlyHint":True,"destructiveHint":False,"idempotentHint":True,"openWorldHint":True})
async def crp_signup_link() -> str:
    '''Return a signup URL for the human to open in their browser. Does NOT create an account.
    The human completes sign-up (and any plan choice/payment) themselves.'''
    require_hosted()
    return json.dumps({"action":"open_in_browser",
                       "url":"https://crprotocol.io/sign-up",
                       "message":"Open this to create your CRP account. I'll continue once you're signed in."})

class UpgradeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    product: str = Field(..., description="'comply' | 'gateway' | 'scan'")
    plan: str = Field(..., description="e.g. 'starter','scale','developer','team','pro','business'")

@mcp.tool(name="crp_upgrade_link",
    annotations={"title":"Get a Stripe checkout link","readOnlyHint":True,"destructiveHint":False,"idempotentHint":True,"openWorldHint":True})
async def crp_upgrade_link(params: UpgradeInput, ctx: Context) -> str:
    '''Return the Stripe Checkout URL for the chosen plan. Does NOT take payment — the human
    pays in their browser. The agent never handles payment (HITL inherent).'''
    identity = authenticate(ctx)
    url = _checkout_link(params.product, params.plan, identity)   # maps to the live price IDs
    audit(identity, "crp_upgrade_link", "issued", product=params.product, plan=params.plan)
    return json.dumps({"action":"open_in_browser","url":url,
                       "message":"Complete payment in your browser to activate the plan."})

# =======================================================================
# HOSTED tools — state-changing (AUTH + ENTITLEMENT + HITL + METERING)
# =======================================================================
class DeployInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    pipeline_id: str = Field(..., description="The id of a built pipeline to deploy", min_length=1, max_length=100)
    confirm_token: Optional[str] = Field(default=None, description="HITL confirmation token from the prior call")

@mcp.tool(name="crp_deploy_endpoint",
    annotations={"title":"Deploy a pipeline as a live endpoint","readOnlyHint":False,"destructiveHint":True,"idempotentHint":False,"openWorldHint":True})
async def crp_deploy_endpoint(params: DeployInput, ctx: Context) -> str:
    '''Deploy a built pipeline as a LIVE production endpoint. Requires auth, the
    'deploy_endpoint' entitlement, and explicit human confirmation (MCP02/06; HITL §5).'''
    identity = authenticate(ctx)                              # MCP07
    require_feature(identity, "gateway", "deploy_endpoint")   # MCP02
    # HITL (MCP06): require an explicit human-approved confirm_token
    if not params.confirm_token:
        token = _issue_confirm_token(identity, "deploy", params.pipeline_id)
        return json.dumps({"requires_confirmation": True, "confirm_token": token,
            "message": f"Deploy pipeline {params.pipeline_id} as a LIVE endpoint? This goes to production. Re-call with the confirm_token to proceed."})
    _verify_confirm_token(identity, params.confirm_token, "deploy", params.pipeline_id)
    result = _deploy(params.pipeline_id, identity)           # consumes plan; per-tenant only (MCP10)
    audit(identity, "crp_deploy_endpoint", "deployed", pipeline=params.pipeline_id)
    return json.dumps(result)                                # returns the live endpoint URL

# crp_test_call, crp_benchmark, crp_create_api_key: same shape —
# authenticate → require_feature/quota → HITL confirm_token → act → audit → meter.

# =======================================================================
# Transport
# =======================================================================
if __name__ == "__main__":
    if HOSTED:
        # Streamable HTTP, TLS-terminated by the platform; validate Origin; rate-limit (MCP07/09)
        mcp.run(transport="streamable_http", port=int(os.getenv("PORT", "8000")))
    else:
        # stdio: log to stderr only, never stdout
        mcp.run()
```

**[DEV-NOTE 6a]** The `crp.specs`, `crp.config`, `crp.scaffolding`, `_verify_clerk_jwt`,
`_checkout_link`, `_deploy`, `_issue/verify_confirm_token`, `get_entitlement`, and `audit`
functions are the real implementation surface. Some exist in the CRP SDK already; the auth
ones map to the CRP-AUTH-USER-MANAGEMENT-SOLUTION doc. Build/wire each; do not leave stubs in
production.

**[DEV-NOTE 6b]** Decide structured output: prefer Pydantic/TypedDict return models so
clients get schemas (the SDK supports this) rather than raw JSON strings, for the tools where
it helps the agent.

---

## 7. DEPLOYMENT

### Local
- `pip install crp-mcp`; runs stdio by default (`CRP_MCP_MODE=local`).
- Connect snippet (Claude Code / Cursor / generic MCP client) in the docs.
- No secrets, no network to CRP. Logs to stderr only.

### Hosted
- Deploy the same package with `CRP_MCP_MODE=hosted` behind TLS at `mcp.crprotocol.io`
  (Streamable HTTP). Reuse the merged Railway project + shared Postgres/Redis if convenient,
  or a dedicated service.
- Env: `CLERK_ISSUER`, `CLERK_AUTHORIZED_PARTIES`, `CLERK_SECRET_KEY`, the device-flow
  secrets, and read access to entitlement; Stripe price-id map for `crp_upgrade_link`.
- Rate-limit per tenant + per IP; validate Origin; bind correctly; structured audit logging.

**[DEV-NOTE 7b]** Decide hosting topology (same Railway project vs separate). The hosted MCP
server is internet-facing and security-sensitive — consider isolating it from the core
runtime so its blast radius is limited (MCP09).

---

## 8. TESTING
- Syntax/import: `python -m py_compile`, run with `--help`.
- MCP Inspector: `npx @modelcontextprotocol/inspector` against both local and hosted.
- Security tests (map to §4): token verification (valid/expired/wrong-issuer/wrong-party),
  entitlement denial, HITL confirm-token flow, per-tenant isolation, rate-limit, no-secret-in-
  logs, safe-YAML, no-exec.
- Evals: 10 read-only questions exercising the LEARN/BUILD/VERIFY tools (per the MCP eval
  guide) to confirm an agent can actually use the server.

**[DEV-NOTE 8b]** Write the security test suite explicitly — the §4 controls are only real if
tested. Prioritise MCP07 (auth) and MCP06 (HITL) tests.

---

## 9. DEV-NOTE REGISTER (everything to implement / decide / research)

| # | What | Why it matters |
|---|------|----------------|
| 2a | Free-tier policy for `crp_test_call` | provider cost economics |
| 3a | Device-flow endpoints; check Clerk device/CLI-flow support | the whole hosted auth depends on it |
| 3b | Session TTL + refusal-to-refresh for destructive tools | limits token misuse (MCP01) |
| 4a | How the local server gets + integrity-checks the spec corpus | MCP03 tool poisoning |
| 4b | Signed releases + SBOM + dependency monitoring (PyPI Trusted Publishing, Sigstore) | MCP04 supply chain |
| 5a | MCP client elicitation support; implement confirm-token fallback | MCP06 HITL on all clients |
| 6a | Implement the real spec/config/scaffold/auth/deploy/audit functions | no stubs in prod |
| 6b | Structured output models where helpful | agent usability |
| 7a | Robust Clerk JWT verification (don't roll your own crypto) | MCP07 — highest risk |
| 7b | Hosting topology + isolation of the internet-facing server | MCP09 blast radius |
| 8a | Audit log destination + anomaly alerting thresholds | MCP08 |
| 8b | Explicit security test suite (auth + HITL first) | controls are real only if tested |
| 9a | Defend the package name; watch typosquats; publish official endpoint identity | MCP09 |

These are the open items I cannot decide for you (they depend on your infrastructure,
provider economics, and current Clerk/MCP-client capabilities). Each is flagged inline above
and collected here so nothing is silently assumed.

---

## 10. THE PRINCIPLE TO HOLD
The MCP server is the agent-facing front door to CRP: it teaches and builds for free and
locally, and it onboards into the paid products via the hosted tier — but it NEVER creates
accounts, takes payment, or acts destructively without the human doing it or explicitly
confirming it, and it is secured against the OWASP MCP Top 10 by design, not as an
afterthought. Signup and billing are redirects. State changes are authenticated,
entitlement-gated, human-confirmed, audited, and per-tenant isolated.

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · mcp.crprotocol.io*
