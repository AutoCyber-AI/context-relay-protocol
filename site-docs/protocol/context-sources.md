# Context Sources - input-side provenance

<div class="cr-hero" markdown>

## Know where every input fact came from

CRP has always tracked where the model's *output* came from. Context-source
provenance answers the mirror question: *where did the input come from?* It
turns RAG chunks, tool responses, database rows, and user uploads into
first-class, auditable protocol primitives - not downstream annotations.

</div>

<span class="cr-badge cr-badge-live">Self-hosted today</span>
<span class="cr-badge cr-roadmap">Managed-cloud waitlist for Gateway and Comply; more endpoints on the roadmap</span>

**Available since CRP 2.1. Enforcement pipeline + ledger in CRP 2.2. Provider hooks, derived manifests, turn-level enforcement, and ledger hash-chain in CRP 2.3. SDK integration in CRP 4.0.**

That's half the picture. Regulators ask the mirror question:

> *"Where did the **input** come from? Which of these facts was pulled
> from a vector DB? Which was a tool response? Which was typed by the
> user? Which did the model already know?"*

Context-source provenance answers that - as a first-class protocol
primitive, not a downstream annotation.

!!! info "Why this matters"
    - **ISO/IEC 42001 §4.1–4.2** - Context of the organisation. An auditor
      will ask for your source inventory on Day One.
    - **EU AI Act Art. 10** - Data and data governance. You must document
      the data used to operate each high-risk system.
    - **GDPR Art. 30** - Records of processing activities. Every personal-data
      source must be recorded.
    - **NIST AI RMF MAP 4** - Impacts are mapped when the organisation maps
      its context.

---

## The primitive

Four types in `crp.core.context_source`:

```python
from crp import SourceKind, SourceOrigin, TrustLevel, ContextSource
```

### `SourceKind`

A closed enumeration of upstream categories:

| Kind | Meaning |
|---|---|
| `USER_TURN` | End-user's direct chat input |
| `SYSTEM_PROMPT` | Developer-authored system prompt |
| `DEVELOPER_PROMPT` | OpenAI-style `role=developer` message |
| `RAG_RETRIEVAL` | Generic RAG chunk |
| `VECTOR_DB` | Pinecone / Weaviate / pgvector / etc. |
| `DATABASE` | Relational / NoSQL read |
| `KNOWLEDGE_GRAPH` | Neo4j / RDF / structured graph |
| `MCP_TOOL` | Model Context Protocol server call |
| `FUNCTION_CALL` | Function-calling result |
| `WEB_SEARCH` | Live web search |
| `FILE_UPLOAD` | User-uploaded document |
| `AGENT_MEMORY` | Agent-framework memory store |
| `CKF_RETRIEVAL` | CRP Contextual Knowledge Fabric (internal) |
| `WARM_STORE` | CRP warm-store fact (internal) |
| `PARAMETRIC` | Model-internal knowledge |
| `UNATTESTED` | Detected but not declared - audit signal |

Closed intentionally. New kinds land via RFC so auditors don't receive
novel strings unannounced.

### `ContextSource`

Frozen dataclass. Attach to any `Fact` or message.

```python
src = ContextSource(
    kind=SourceKind.VECTOR_DB,
    source_id="acme-hr-policies-vdb",
    origin=SourceOrigin.OBSERVED,
    trust_level=TrustLevel.TRUSTED,
    contains_pii=True,
    region="eu-west-1",
    retrieval_query="redundancy policy 2024",
    retrieved_at=time.time(),
)
```

`origin` has three values: `DECLARED` (from a signed manifest),
`OBSERVED` (plumbed in by the caller who knows the true origin), or
`HEURISTIC` (inferred by the detective-mode parser).

### `ContextManifest`

Customer-authored declaration of *intended* sources, HMAC-SHA256 signed.

```python
from crp import ContextManifest

manifest = ContextManifest(system_id="resume-rank-v1", customer_id="acme")
manifest.add(ContextSource(
    kind=SourceKind.VECTOR_DB,
    source_id="acme-hr-policies-vdb",
    contains_pii=True,
    region="eu-west-1",
))
manifest.add(ContextSource(
    kind=SourceKind.DATABASE,
    source_id="acme-postgres-applicants",
    contains_pii=True,
    region="eu-west-1",
))
manifest.sign(secret=os.environ["YOUR_MANIFEST_SECRET"].encode())

blob = manifest.to_json()            # persist / ship to proxy
restored = ContextManifest.from_json(blob)
assert restored.verify(os.environ["YOUR_MANIFEST_SECRET"].encode())
```

Signature verification uses `hmac.compare_digest` (constant-time).

### `check_attestation`

Compares observed sources against the manifest and returns a list of
`AttestationMismatch` rows.

```python
from crp import check_attestation

mismatches = check_attestation(observed_sources, manifest)
for m in mismatches:
    audit_log.emit(m.to_audit_event())   # CONTEXT_ATTESTATION_MISMATCH
```

Reasons reported:

- `no_manifest` - observed source seen but no manifest registered
- `manifest_expired` - manifest past `expires_at`
- `unattested_kind` - observed `kind` not in declared kinds
- `unattested_source_id` - kind declared but `source_id` mismatch

Benign kinds (`USER_TURN`, `SYSTEM_PROMPT`, `DEVELOPER_PROMPT`,
`PARAMETRIC`) are exempt from "no manifest" mismatches.

---

## From the SDK

The SDK captures source provenance automatically when you ingest documents or
use tool-mediated `ask()` calls:

```python
import crp

client = crp.SDKClient()
client.ingest("./docs/")

answer = client.ask("What is the redundancy policy?", depth="standard")

print(answer.text)
print(answer.quality)
for src in answer.sources:
    print(src.title, src.doc_id, src.used_facts)
```

---

## Detective mode - heuristic parsing

When upstream code doesn't attach a `ContextSource`,
`detect_source_kind(content, role=…)` classifies the message using a
conservative pattern library plus the OpenAI-style role hint.

```python
from crp import detect_source_kind

detect_source_kind("You are helpful.", role="system").kind
# → SourceKind.SYSTEM_PROMPT

detect_source_kind("<RAG>chunk 1</RAG>", role="user").kind
# → SourceKind.RAG_RETRIEVAL

detect_source_kind("SELECT name FROM users").kind
# → SourceKind.DATABASE
```

Detective-mode results always have `origin=HEURISTIC` and
`trust_level=UNKNOWN`. They surface in audit reports for review - they
are never treated as authoritative.

---

## `Fact.source`

The extraction pipeline's `Fact` gains an optional `source` field.

```python
from crp import Fact, ContextSource, SourceKind

fact = Fact(
    text="The redundancy policy requires 60 days' notice.",
    source=ContextSource(
        kind=SourceKind.VECTOR_DB,
        source_id="acme-hr-policies-vdb",
        contains_pii=False,
    ),
)
```

The field defaults to `None`, so every v2.0 caller continues to work
without modification.

---

## Envelope integration

`[CONTEXT_SOURCES]` is now a recognised Tier-3 section in the envelope
formatter. When the envelope builder packs facts that carry `source`
records, the source manifest can be rendered as a dedicated section for
the model to reason about - or stripped for production prompts and
retained only in the audit log.

See [Context Envelope](envelope.md) for the 11-section layout.

---

## Error codes

| Code | Name | Meaning |
|---|---|---|
| 1040 | `CONTEXT_ATTESTATION_MISMATCH` | Observed source not declared in manifest |
| 1041 | `CONTEXT_MANIFEST_INVALID` | Manifest failed to parse or verify |

---

## Complete example

```python
import os
import time
from crp import (
    SDKClient, Fact, ContextSource, ContextManifest,
    SourceKind, SourceOrigin, TrustLevel,
    detect_source_kind, check_attestation,
)

# 1.  Declare your sources up front.
manifest = ContextManifest(system_id="triage-bot", customer_id="acme")
manifest.add(ContextSource(
    kind=SourceKind.VECTOR_DB, source_id="policy-vdb",
    contains_pii=False, region="eu-west-1",
    trust_level=TrustLevel.TRUSTED,
))
manifest.sign(os.environ["YOUR_MANIFEST_SECRET"].encode())

# 2.  Use the SDK to ingest and ask.
client = crp.SDKClient()
client.ingest("./docs/")

answer = client.ask("What is the redundancy policy?", depth="standard")
print(answer.text)
print(answer.sources)

# 3.  Heuristically detect anything that slipped through unattested.
detected = detect_source_kind(some_tool_response, role="tool")

# 4.  Audit the session.
observed = [detected]
for mismatch in check_attestation(observed, manifest):
    print(mismatch.to_audit_event())
```

---

## Enforcement pipeline *(CRP 2.2)*

2.1 defined the **vocabulary**. 2.2 defines the **wire-side choke-point**
every envelope assembly must flow through when a manifest is attached.

```python
from crp import (
    ContextEnforcer,
    EnforcementPolicy,
    InMemoryAuditSink,
    RotatingKeyProvider,
    ManifestLedger,
    set_default_enforcer,
)

enforcer = ContextEnforcer(
    policy=EnforcementPolicy.REJECT,                    # OBSERVE | WARN | REJECT
    sink=InMemoryAuditSink(),                           # or LoggingAuditSink, or your own
    key_provider=RotatingKeyProvider(initial=SECRET),   # HMAC keys w/ grace window
    ledger=ManifestLedger(),                            # append-only JSONL per session
    session_id="sess-abc",
    require_signed_manifest=True,
)

set_default_enforcer(enforcer)   # process-wide default; opt-in
```

Every call to `assemble_messages(manifest=…, observed_sources=…)`
now runs the pipeline before any message is constructed:

1. Manifest signature verify (via `KeyProvider.candidates()` - rotation aware)
2. Manifest expiry check
3. Attestation mismatch scan (observed sources vs. declared)
4. Injection-signal scan on content from `TRUSTED` sources
5. Auto-record to the ledger on success

Under `REJECT`, violations raise `CRPError(CONTEXT_ATTESTATION_MISMATCH)`
or `CRPError(CONTEXT_MANIFEST_INVALID)` with the offending `source_id`s
named in the message. Under `OBSERVE` / `WARN`, audit events are emitted
to the sink and assembly continues.

---

## Injection-signal detection *(CRP 2.2)*

Trust labels are declarative. Marking a `SYSTEM_PROMPT` as `TRUSTED`
doesn't make its content safe if the prompt was templated from user
input. CRP 2.2 scans `TRUSTED` sources for common injection signals
(instruction overrides, role jailbreaks, secret-exfiltration attempts,
delimiter forgery, suspicious payload URLs, and embedded tool calls).

Hits are surfaced as `CONTEXT_TRUST_VIOLATION` audit events. Untrusted
sources are not scanned by default (untrusted content is expected to
contain arbitrary text - scanning it produces noise).

---

## Manifest ledger *(CRP 2.2)*

Cross-turn continuity. Every verified manifest is appended to the
configured session ledger (e.g. `sessions/<session_id>.manifest.jsonl`):

```python
from crp import ManifestLedger

ledger = ManifestLedger()

# Find every turn where a source was declared:
entries = ledger.find_by_source_id("acme-hr-policies-vdb", session_id="sess-abc")

# Find every session that touched a particular kind of source:
entries = ledger.find_by_kind(SourceKind.WEB_SEARCH, session_id="sess-abc")

# Periodic integrity audit:
bad = ledger.verify_signatures("sess-abc", secret=current_key)

# Discover every session on disk (for cold-start audits):
for sid in ledger.scan_sessions():
    ...
```

Session IDs are sanitized to `[A-Za-z0-9_-]` - identifiers that sanitize
to empty are rejected (prevents directory traversal).

---

## Key management *(CRP 2.2)*

Two `KeyProvider` implementations; integrators plug in their own for
KMS / Vault / HSM:

```python
from crp import EnvVarKeyProvider, RotatingKeyProvider

# Minimum viable: env var (hex auto-detect, ≥32 byte minimum)
kp = EnvVarKeyProvider("YOUR_MANIFEST_SECRET")

# Rotation with grace window
kp = RotatingKeyProvider(initial=current_key)
kp.rotate(new_key)                  # old key still verifies in-flight manifests
kp.retire_all()                     # drop every retired key
```

The enforcer calls `kp.verify(manifest)` which tries `candidates()` in
order (current first, retired next). `hmac.compare_digest` is used for
each comparison - no timing side channel between candidates.

---

## Retrieval auto-stamping *(CRP 2.2)*

Two retrieval surfaces automatically stamp provenance on facts that
arrive without an explicit `source`:

- **Warm store** (`WarmStateStore.get_active_facts_as_extraction`) -
  `kind=WARM_STORE`, `trust_level=UNKNOWN`.
- **CKF** (`ContextualKnowledgeFabric.retrieve`) - `kind=CKF_RETRIEVAL`,
  `trust_level=UNKNOWN`, with retrieval `modes` and `score` in `metadata`.

Trust is deliberately `UNKNOWN` - CRP cannot infer upstream trust at
retrieval time. Integrators who have vetted their warm-store contents
should set `fact.source` explicitly before the fact enters the store.

---

## Provider/framework auto-hooks *(CRP 2.3)*

Callers who hand-build OpenAI / Anthropic requests, or use
LangChain/LlamaIndex/Semantic Kernel directly, previously bypassed the
`ContextEnforcer` entirely. CRP 2.3 fixes that with transparent hooks:

```python
from crp.integrations import install_openai_hook, install_anthropic_hook
from crp.integrations.langchain_hook import CRPCallbackHandler

# Monkey-patches openai.OpenAI.chat.completions.create (sync + async).
install_openai_hook(enforcer=my_enforcer)

# Same for anthropic.Anthropic.messages.create.
install_anthropic_hook(enforcer=my_enforcer)

# LangChain: add as a callback to any LLM/Chain/AgentExecutor.
chain.invoke(..., callbacks=[CRPCallbackHandler(enforcer=my_enforcer)])
```

Every bypass path now flows through the same ledger and the same policy.

## Derived manifests *(CRP 2.3)*

Not every integrator will stamp sources. CRP 2.3 can *derive* a manifest
from observed bytes, distinguishing lazy-integrator from genuinely
ephemeral content:

```python
from crp.core.manifest_derive import derive_manifest_from_content

manifest = derive_manifest_from_content(
    content=retrieved_text,
    retrieval_query="What is policy X?",
    upstream_uri="vector://kb/doc-42",
)
```

Derived manifests carry `origin=DERIVED` and default `TrustLevel.UNKNOWN`
- they *never* silently upgrade trust. They do flow through the ledger so
OBSERVE-mode deployments get audit coverage even without explicit stamps.

## Turn-level enforcement *(CRP 2.3)*

The enforcer now re-validates every turn, including `tool_result`
injections mid-conversation:

```python
# Full message list (typical chat-completions shape)
enforcer.check_messages(messages, observed=sources)

# Single tool_result about to re-enter the prompt
enforcer.check_tool_result(tool_call_id, content, source=...)
```

No more one-shot-at-assembly-time gap.

## Ledger hash chain + SIEM forwarding *(CRP 2.3)*

`ManifestLedger` entries now include `prev_hash` + `entry_hash`. Tampering
with any entry breaks the chain, detectable via:

```python
ok, bad_entries = ledger.verify_chain(session_id)
```

SIEM / syslog / JSONL replicators plug in via the `forward_to=` kwarg:

```python
from crp.core.ledger_backends import JsonlFileSink, SyslogSink

ledger = ManifestLedger(
    session_dir="sessions",
    forward_to=[
        JsonlFileSink("/var/log/crp/ledger.jsonl"),
        SyslogSink(host="your-siem.host", port=514),
    ],
)
```

Forwarding never blocks a ledger write; failing sinks are logged and
skipped.

## Default observe enforcer *(CRP 2.3)*

`assemble_messages` now auto-installs an `OBSERVE`-mode enforcer if the
caller forgot to configure one. Previously, forgetting `set_default_enforcer`
meant silent no-op. Now you always get at least the ledger trail.

## Custom / local endpoints *(CRP 2.3)*

`OpenAIAdapter` accepts empty or `None` `api_key` when `base_url` is set.
Works out-of-the-box with LM Studio, vLLM, llama.cpp server, Ollama
OpenAI-compat, TGI, and any unauthenticated local endpoint:

```python
from crp.providers import OpenAIAdapter

adapter = OpenAIAdapter(
    model="gemma-3-270m-it-qat",
    api_key="",  # or None
    base_url="http://192.168.0.6:1234/v1",
)
```

---

## Roadmap

- ~~Protocol-level `[CONTEXT_SOURCES]` envelope section renderer and budget accounting (2.1.x)~~ - **shipped in 2.1**
- ~~Dispatch router auto-attaches `ContextSource` to tool-role messages (2.2.0)~~ - **shipped in 2.2**
- ~~Provider/framework auto-hooks, derived manifests, turn-level enforcement, ledger hash-chain (2.3.0)~~ - **shipped in 2.3**
- ~~SDK-level source attribution via `client.ask(...).sources` (4.0.0)~~ - **shipped in 4.0; enhanced in 5.1.0**
- `crp-comply` consumes `ContextSource` + the manifest ledger to emit
  the **Context Analysis** deliverable (ISO 42001 §4.1–4.2) and GDPR
  Art. 30 RoPA. Coming in Comply 1.x.

See the [CHANGELOG on GitHub](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/CHANGELOG.md) for the complete 5.1.0 note.
