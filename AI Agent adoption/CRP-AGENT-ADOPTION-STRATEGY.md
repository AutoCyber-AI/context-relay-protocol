# CRP — AI-Agent Adoption Strategy & Resources

**For:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd
**Premise:** developers increasingly build with AI coding agents (Claude Code, Cursor,
Copilot, etc.). The protocol whose ecosystem teaches the agent how to use it wins.
**Goal:** make AI agents (a) AWARE CRP exists, (b) PROFICIENT at using it correctly,
(c) able to DO CRP tasks live.

---

## 1. THE THREE LAYERS (do not conflate them)

| Layer | Question it answers | Resource | Effort | Caveat |
|-------|--------------------|----------|--------|--------|
| **Discovery** | Does the agent know CRP exists? | llms.txt, public GitHub/docs, Scan remediation | medium | the hard problem; no single artifact solves it |
| **Proficiency** | Can the agent use CRP correctly? | CRP-SKILL.md / AGENTS.md + the SDK | low | huge ROI; build first |
| **Assistance** | Can the agent DO CRP things live? | CRP MCP server (local + hosted) | high | only helps users who already connected it |

**The trap:** building only Proficiency (a SKILL file) and expecting adoption. Without
Discovery, no agent ever reaches the SKILL file. Build all three, but understand which
does what.

---

## 2. DISCOVERY — how an agent first hears about CRP

An agent suggests CRP only if it has encountered it. Channels, in order of speed:

1. **Scan remediation (fastest, owned channel).** When CRP Scan flags an ungoverned AI
   call, the remediation IS "route through CRP." Every scan an agent runs becomes a CRP
   awareness event. This is your unique discovery channel — compounding and free.
2. **llms.txt at crprotocol.io (cheap, standards-emerging).** A site-level file telling
   any LLM/agent what CRP is and where the agent-facing docs are. Agents that fetch a
   site increasingly look for it.
3. **Public GitHub + docs presence (slow, compounding).** Public repos, a docs site, the
   PyPI package, the RFC — over time these enter training data, the only path to ambient
   awareness (an agent suggesting CRP unprompted). Slow but durable.
4. **The RFC itself.** An Internet-Draft / RFC is citable authority an agent can find and
   trust — part of why the IETF path matters for adoption, not just credibility.

**Honest:** true ambient awareness (every agent knows CRP) only comes from broad public
presence over time. The MCP server and SKILL.md do NOT create discovery — they serve
agents already pointed at CRP. Invest in the public/Scan channels for discovery.

---

## 3. PROFICIENCY — the agent-facing knowledge file (build FIRST)

The single highest-ROI artifact: a CRP-SKILL.md (a.k.a. AGENTS.md / the body of
llms-full.txt) that any agent can read and immediately write correct CRP code.

- Ship it: in the public repo root (`AGENTS.md` + `CRP-SKILL.md`), at
  `crprotocol.io/llms.txt` (short) and `crprotocol.io/llms-full.txt` (full), and inside
  the `crprotocol` PyPI package so it travels with installs.
- Content principle: show the ONE-LINE path first (base_url swap → governed), then
  progressive disclosure (SPEC-032). Agents copy the first working example they see, so
  the first example must be the simplest correct one.
- Cover CRPv4 accurately: `crp.SDKClient`, `ingest`/`ask`, `client.tool`, sessions,
  `client.safety.*`, checkpoints, the Safety Control Plane, conformance, audit export,
  and the relationship to MCP/A2A.
- See the companion file: **CRP-SKILL.md** (the actual artifact).

---

## 4. ASSISTANCE — the CRP MCP server (build SECOND)

An MCP server giving agents live CRP tools. Powerful for users who connect it; not a
discovery mechanism. It ships as one package with two modes:

| Mode | Transport | What it does | Needs |
|------|-----------|--------------|-------|
| **Local** | stdio on the user's machine | Learn, scaffold, validate, lint, conformance — all static/no secrets | `pip install crprotocol[mcp]` |
| **Hosted** | Streamable HTTP @ `mcp.crprotocol.io` | Account-linked live actions (test call, deploy, benchmark) + onboarding links | CRP sign-in + entitlement |

### Local tools (read-only, no auth)

| Tool | What it does | Backed by |
|------|-------------|-----------|
| `crp_explain` | returns a concise explanation of a CRPv4 concept/spec | the spec corpus |
| `crp_spec_lookup` | retrieves authoritative spec text with citations | the spec corpus |
| `crp_compare` | CRP vs MCP/A2A/AIPREF/RAG/vector-DB | site-docs/topics |
| `crp_scaffold_integration` | generates integration code for a stack | SPEC-032/037 |
| `crp_generate_config` | turns intent into a valid `crp.config.yaml` | `crp.comply.no_code` |
| `crp_generate_safety_policy` | turns plain intent into a valid Safety Policy | SPEC-006/033 |
| `crp_sdk_example` | returns a copy-paste SDK snippet for a task | SPEC-032 |
| `crp_migrate_v3_v4` | migration guidance for existing CRP users | specs |
| `crp_validate_config` | validates a `crp.config.yaml` / SafetyManifest | `crp.config_schema` |
| `crp_lint_headers` | checks CRP-* header usage for correctness | `crp.headers.names` |
| `crp_conformance_check` | runs configs/integrations against conformance vectors | SPEC-014/026 |
| `crp_safety_registry` | lists the Safety Control Plane capabilities | `crp.security.control_plane` |

### Hosted tools (auth-gated, entitlement-checked, HITL for state-changing actions)

| Tool | Purpose | HITL |
|------|---------|------|
| `crp_whoami` | signed-in user's products/plans/quotas | no |
| `crp_get_plan` | current plan + remaining quota | no |
| `crp_signup_link` | returns signup URL (human opens) | inherent |
| `crp_upgrade_link` | returns Stripe checkout URL (human pays) | inherent |
| `crp_connect_repo_link` | returns GitHub App install URL (human installs) | inherent |
| `crp_create_api_key` | mint a scoped Gateway API key | YES |
| `crp_test_call` | run ONE real governed call | YES + cost notice |
| `crp_deploy_endpoint` | deploy a pipeline live | YES |
| `crp_benchmark` | run an SQB-style quality check | YES + cost notice |

Signup, upgrade, and repo-connect are **redirect-only** — the agent never creates accounts,
never handles payment, and never holds credentials. State-changing tools require explicit
human-in-the-loop confirmation.

- See the companion file: **CRP-MCP-SERVER-SPECIFICATION.md** (security, auth, OWASP MCP
  Top 10 mapping, HITL policy).
- Distribution: `pip install crprotocol[mcp]`; publish the server to MCP registries.

---

## 5. THE SEQUENCE (highest ROI first)

1. **CRP-SKILL.md + llms.txt** — proficiency + a discovery entry point. Days, not weeks.
2. **Public GitHub + docs** — discovery groundwork (also where the SKILL lives).
3. **Wire CRP into Scan's remediation text** — turn your existing product into a
   discovery channel. (Mostly copy/positioning work.)
4. **MCP server** — assistance, once the above exist. Start with the local stdio mode;
   the hosted account-linked mode depends on Clerk/Stripe backend wiring.

Do NOT start with the MCP server. It's the most work and the least discovery value;
it amplifies an audience you must first create with 1–3.

---

## 6. HONEST LIMITS
- No artifact makes every agent instantly CRP-aware; discovery is a compounding game won
  through public presence + the Scan channel + the RFC.
- An MCP server helps only after a user connects it — high value, narrow reach early.
- A SKILL.md helps only when an agent is pointed at the repo/site — so getting the file
  into the install (PyPI) and the site (llms.txt) matters as much as writing it.
- Hosted MCP actions that spend quota or create credentials MUST confirm a human first;
  never let an agent silently mint keys, deploy, or pay.
- Keep every resource truthful about what CRP does and doesn't do (the same honesty as the
  specs): an agent that over-trusts an inflated SKILL writes wrong code and burns trust.

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · crprotocol.io*
