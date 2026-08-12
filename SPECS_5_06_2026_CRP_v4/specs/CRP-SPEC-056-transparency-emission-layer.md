# CRP-SPEC-056: Transparency Emission Layer

**Document:** CRP-SPEC-056  
**Title:** The Transparency Emission Layer — Streaming CRP's Governance  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Evidence as Standard, Faithful, Verifiable Events  
**Version:** 6.0.0  
**Status:** Implemented (D1-D3 streaming events and governance vocabulary);  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;D4-D6 resumable transparency is roadmap  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**License:** CC BY 4.0 (specification text) / Elastic License 2.0 (reference implementation)  
**Prerequisites:** CRP-SPEC-005 (DPE), CRP-SPEC-011 (Audit), CRP-SPEC-016 (Gateway),  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;CRP-SPEC-030 (CSO), CRP-SPEC-049 (VR)

---

## Abstract

CRP generates more governance evidence per turn than any comparable agent protocol: safety scans, policy verdicts, provenance links, verification ratios, quality tiers, and audit-chain hashes. The Transparency Emission Layer (TEL) defines a standard wire format for *emitting* that evidence so it can be displayed, replayed, and independently verified by clients.

TEL maps CRP runtime events onto the AG-UI cross-framework event vocabulary, extends that vocabulary with a CRP-specific governance namespace (`crp.safety_scan`, `crp.quality`, `crp.provenance`, and others), and binds the emitted stream to the session's HMAC audit chain. It also introduces a faithful-narration contract: every sentence shown to a user as part of a `TEXT_MESSAGE_CONTENT` event must first be checked against the event trace that produced it, and unsupported claims must be withheld.

This specification realises the D1–D6 transparency roadmap from *The Architecture of Transparency in Agentic AI Systems*. D1–D3 (AG-UI mapping, governance vocabulary, faithful narration) are implemented in CRP v6.0.0. D4–D6 (live client-verifiable provenance, quality/confidence badges, and full CSO-backed resumable transparency) are implemented at the event-layer boundary but remain roadmap features for completion across continuation-relayed long engagements.

---

## 1. Terminology

**AG-UI:** The Agent-User Interaction Protocol, a cross-framework event vocabulary for streaming agent execution state to frontends.

**Audit-chain link:** One HMAC-signed record in the session audit trail (CRP-SPEC-011). Each link binds the previous hash, the current operation, and a timestamp.

**CRP governance event:** A namespaced `CUSTOM` event whose `name` begins with `crp.`, carrying safety, quality, provenance, or policy evidence.

**Event trace:** The ordered sequence of TEL events produced during one run or window, used as evidence when checking narration claims.

**Faithful narration:** The property that every narrative sentence delivered to a user is entailed by the event trace; unsupported sentences are not streamed.

**Governance disclosure tier:** The audience classification (end user, operator, auditor) that determines which governance events a client is authorised to receive (CRP-SPEC-006).

**Last-Event-ID:** The SSE resume cursor. A client reconnects with the last `id` it received and the server replays buffered events with greater sequence numbers.

**Semantic entropy:** A calibrated uncertainty estimate derived from sample divergence among meaning-equivalent outputs (CRP-SPEC-055).

**Verification ratio:** The fraction of claims in a window whose reasoning was validated by the Verification Relay (CRP-SPEC-049).

---

## 2. Introduction

### 2.1 Motivation

Most agent runtimes stream *what the model is doing*: tokens, tool calls, intermediate reasoning. Few stream *whether what the model says is true, whether the action was permitted, or whether any of it can be proven*. CRP already produces all three kinds of evidence inside the Decision Provenance Engine, the Safety Control Plane, the Verification Relay, and the HMAC audit chain. TEL is the missing emission layer that converts that internal evidence into externally consumable events.

By adopting AG-UI as the base vocabulary, CRP inherits an existing frontend ecosystem. By adding the CRP governance namespace, CRP extends that ecosystem with events no competitor can emit because no competitor generates the underlying evidence.

### 2.2 Goals

1. Emit every CRP run as a stream of standard, vendor-neutral events.
2. Surface safety scans, policy verdicts, verification results, quality tiers, and provenance links as first-class events.
3. Guarantee that user-facing narration is faithful to the underlying trace.
4. Make the audit chain client-verifiable in real time.
5. Allow a long, continuation-relayed engagement to be resumed with its transparency stream intact.

### 2.3 Non-Goals

- TEL does not define a new general-purpose agent display protocol; it extends AG-UI.
- It does not replace CRP-SPEC-011 audit storage; it streams references into that storage.
- It does not grant end users access to auditor-tier provenance unless the active disclosure tier explicitly allows it.

---

## 3. Event Model

### 3.1 Base Event Structure

Every TEL event is a JSON-serialisable object with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | AG-UI event type or `CUSTOM` |
| `seq` | integer | Monotonic sequence number within the session bus |
| `id` | string | Stable event identifier |
| `ts` | float | Unix timestamp (seconds) |
| `payload` | object | Type-specific data |

When transported over Server-Sent Events, an event is rendered as:

```text
id: {seq}
event: {type}
data: {json-encoded event body}

```

The `id` field enables `Last-Event-ID` replay and the `event` field lets `EventSource` consumers route by type.

### 3.2 Standard AG-UI Events (D1)

A conformant TEL runtime MUST emit the following AG-UI event families:

**Lifecycle:**
- `RUN_STARTED` — a new governed run began.
- `RUN_FINISHED` — the run completed normally.
- `RUN_ERROR` — the run halted or failed.
- `STEP_STARTED` / `STEP_FINISHED` — operation state-machine transitions.

**Narrative substrate:**
- `TEXT_MESSAGE_START` / `TEXT_MESSAGE_END` — boundaries of a user-facing message.
- `TEXT_MESSAGE_CONTENT` — a delta or full sentence of user-facing text.

**Reasoning substrate:**
- `REASONING_START` / `REASONING_END` — boundaries of a reasoning block.
- `REASONING_CONTENT` — a reasoning delta.

**Tool-call substrate:**
- `TOOL_CALL_START` — a tool call is about to be issued.
- `TOOL_CALL_ARGS` — incremental arguments for the call.
- `TOOL_CALL_END` — the call arguments are complete.
- `TOOL_CALL_RESULT` — the result returned by the tool.

**State synchronisation:**
- `STATE_SNAPSHOT` — a full serialised state object.
- `STATE_DELTA` — a JSON Patch (RFC 6902) list describing a state change.
- `MESSAGES_SNAPSHOT` — the current message list.

**Special:**
- `INTERRUPT` — the runtime paused for human input, clarification, or checkpoint.
- `CUSTOM` — extension events, including the CRP governance vocabulary.

### 3.3 CRP Governance Vocabulary (D2)

Governance events are `CUSTOM` events whose payload contains a `name` and a `value`. The `name` MUST begin with `crp.` and use lowercase snake-case with dot namespacing.

Defined governance event names:

| Name | Value fields | Source spec |
|------|--------------|-------------|
| `crp.safety_scan` | `stage`, `risk`, `ms`, `verdict` | CRP-SPEC-005, CRP-SPEC-033 |
| `crp.policy` | `envelope`, `verdict` | CRP-SPEC-006 |
| `crp.verification` | `ratio`, `invalid`, `repairs` | CRP-SPEC-049 |
| `crp.quality` | `tier`, `confidence`, `semantic_entropy` | CRP-SPEC-026, CRP-SPEC-055 |
| `crp.provenance` | `op`, `prev`, `hash` | CRP-SPEC-011 |
| `crp.prediction` | `action`, `predicted`, `confidence` | CRP-SPEC-051 |
| `crp.retrieval` | `sources` | CRP-SPEC-009, CRP-SPEC-027 |
| `crp.progress` | `percent`, `eta_seconds`, `confidence`, `current` | Runtime |
| `crp.intent` | `operation`, `detail`, `plan` | CRP-SPEC-031, CRP-SPEC-052 |

Example:

```json
{
  "type": "CUSTOM",
  "seq": 42,
  "id": "a1b2c3d4e5f6",
  "ts": 1757142892.0,
  "name": "crp.quality",
  "value": {
    "tier": "A",
    "confidence": 0.91,
    "semantic_entropy": 0.04
  }
}
```

The reference adapter exposes ergonomic methods that emit these events:

```python
# Conceptual API (CRP-SPEC-056 §3.3)
class CRPEmitter:
    def dpe_stage(self, stage: str, risk: str, ms: int, verdict: str) -> Event: ...
    def verification(self, ratio: float, invalid: int, repairs: int) -> Event: ...
    def quality(self, tier: str, confidence: float, entropy: float | None) -> Event: ...
    def provenance(self, prev_hash: str, this_hash: str, op: str) -> Event: ...
    def prediction(self, action: str, predicted: dict, confidence: float) -> Event: ...
```

### 3.4 Event Sequencing Guarantees

The session event bus MUST:

1. Assign monotonically increasing `seq` values.
2. Retain the most recent events in a bounded replay buffer (default 2000 events).
3. Support `replay_after(seq)` to return all buffered events with `seq >` the supplied cursor.
4. Fan out events to both synchronous and asynchronous subscribers.

No subscriber MAY observe an event with a lower `seq` after it has already observed a higher `seq` from the same bus, unless a deliberate replay is requested via `Last-Event-ID`.

---

## 4. Faithful Narration (D3)

### 4.1 Contract

Every `TEXT_MESSAGE_CONTENT` event that carries a summary or narrative claim MUST be checked against the event trace before it is emitted. Claims that are not supported by the trace MUST be withheld or rewritten to a lower-certainty form.

A claim is supported when the flattened event trace entails it. The reference implementation uses a natural-language inference (NLI) cross-encoder when available, with a deterministic word-subset fallback. The fallback requires every content word of the claim to appear in the flattened trace.

### 4.2 Entailment Procedure

Given a candidate claim `c` and the current event trace `E`:

1. Flatten `E` into a single premise string by concatenating operation names, tool results, detail fields, and governance payloads.
2. If an NLI model is available, classify `(premise, c)`. Emit `c` only when the top label is `entailment`.
3. If the NLI model is unavailable or inference fails, apply the deterministic heuristic: emit `c` only when every content word in `c` appears in the premise.
4. If `c` fails the check, either:
   - withhold it;
   - replace it with a weaker claim that the trace supports; or
   - append a qualification ("not yet verified by tool output") and downgrade the quality tier.

### 4.3 Narration Boundaries

The runtime MUST mark the start and end of user-facing narration with `TEXT_MESSAGE_START` and `TEXT_MESSAGE_END`. Faithfulness checking applies to the concatenated content deltas between those boundaries. Reasoning content (`REASONING_CONTENT`) is not user-facing and is exempt from the faithful-narration contract, though it MAY still be filtered for privacy or disclosure-tier reasons.

---

## 5. Live Verifiable Provenance (D4)

### 5.1 Provenance Events

For every operation that extends the session audit chain, the runtime MUST emit a `crp.provenance` event containing:

| Field | Meaning |
|-------|---------|
| `op` | Operation identifier that produced this link |
| `prev` | Hash of the previous audit-chain record |
| `hash` | Hash of the current audit-chain record |

Example:

```json
{
  "type": "CUSTOM",
  "name": "crp.provenance",
  "value": {
    "op": "scan.port_scan",
    "prev": "sha256:abcd...",
    "hash": "sha256:ef01..."
  }
}
```

### 5.2 Client Verification

An auditor-tier client MAY recompute the audit-chain hash from the event payload and compare it with the `hash` field. A mismatch indicates tampering or desynchronisation and MUST surface as a `CRP-Provenance-Chain-Integrity: BROKEN` condition (CRP-SPEC-011).

In CRP v6.0.0 the `crp.provenance` event is emitted and the chain is server-verified on every window. Full *client-side* recomputation and display in a browser is a roadmap target for D4.

---

## 6. Quality and Confidence Streaming (D5)

### 6.1 Quality Event

After each operation or window, the runtime SHOULD emit a `crp.quality` event carrying:

| Field | Meaning |
|-------|---------|
| `tier` | Quality tier: `S`, `A`, `B`, `C`, `D`, or `E` (CRP-SPEC-026) |
| `confidence` | Calibrated confidence estimate in `[0.0, 1.0]` |
| `semantic_entropy` | Optional uncertainty estimate from CRP-SPEC-055 |

### 6.2 Presentation

A frontend SHOULD render the quality tier and confidence as an always-visible epistemic badge. When confidence is low or semantic entropy is high, the UI SHOULD visually distinguish the output (for example, with a warning state) and SHOULD NOT present the result with unwarranted certainty.

In CRP v6.0.0 the `crp.quality` event is emitted; the standardised always-visible badge and its precise visual treatment are roadmap targets for D5.

---

## 7. Resumable Transparency (D6)

### 7.1 Replay Buffer

The session event bus MUST retain events so that a client that reconnects with `Last-Event-ID` can receive all missed events. The default buffer size is 2000 events; deployments MAY tune this value based on expected session length and memory constraints.

### 7.2 CSO-Backed Resumability

For long engagements that span multiple continuation windows, the event stream SHOULD be anchored to the Cognitive State Object (CRP-SPEC-030). On resume:

1. The client supplies the last `seq` it observed.
2. The server replays buffered events from the active session bus.
3. If the buffer does not cover the gap, the server reconstructs a compact transparency summary from the CSO and emits it as a `STATE_SNAPSHOT` before resuming live events.

In CRP v6.0.0 the replay buffer is implemented; full CSO-backed resumability across continuation-relayed windows is a roadmap target for D6.

---

## 8. Transport

### 8.1 Default Transport

The default TEL transport is **Server-Sent Events (SSE)** over HTTPS. The SSE stream is identified by the CRP session id. A client connects to the Gateway endpoint and receives events in real time.

### 8.2 Authentication and Isolation

TEL stream endpoints MUST:

1. Require authentication (for example, via Clerk session tokens or API keys).
2. Enforce tenant isolation so a client can only subscribe to events for sessions it is authorised to access.
3. Validate `Last-Event-ID` values against the session bus so cross-session replay is impossible.

### 8.3 Heartbeats

The server SHOULD emit SSE comment heartbeats (for example, `: ping`) when no event has been sent within a configured interval (default 15 seconds). This keeps proxies and browser `EventSource` connections alive during long tool executions.

---

## 9. Integration Points

### 9.1 Gateway (CRP-SPEC-016)

The Gateway hosts the public TEL SSE endpoint, authenticates subscribers, and strips or downgrades events according to the active disclosure tier before streaming them.

### 9.2 Decision Provenance Engine (CRP-SPEC-005)

DPE stage results (`dpe_stage`) are emitted as `crp.safety_scan` events. Claim-level verdicts feed the faithful-narration check.

### 9.3 Audit Chain (CRP-SPEC-011)

Every window commit produces a new audit-chain hash. TEL emits that hash as a `crp.provenance` event so clients can verify the chain.

### 9.4 Cognitive State Object (CRP-SPEC-030)

The CSO carries the session state used for D6 resumability. TEL `STATE_SNAPSHOT` and `STATE_DELTA` events reflect CSO snapshots and changes.

### 9.5 Verification Relay (CRP-SPEC-049)

VR verdicts are emitted as `crp.verification` events. The verification ratio is one of the inputs to the quality tier.

### 9.6 Quality and Uncertainty (CRP-SPEC-026, CRP-SPEC-055)

SQB quality tiers and EP semantic-entropy estimates are surfaced through `crp.quality` events.

### 9.7 Predictive Oversight (CRP-SPEC-051)

Predicted action outcomes are emitted as `crp.prediction` events before the action is executed, giving a frontend the opportunity to display a pre-action checkpoint.

---

## 10. Conformance Requirements

A CRP v6.0.0 implementation claiming conformance with this specification MUST satisfy the following requirements:

### 10.1 D1 — AG-UI Mapping

1. MUST emit standard AG-UI lifecycle, text, reasoning, tool, and state events for every run.
2. MUST assign monotonic `seq` values and stable `id` values to every event.
3. MUST render events to SSE with `id`, `event`, and `data` fields.

### 10.2 D2 — Governance Vocabulary

1. MUST emit safety scans, policy verdicts, verification results, and quality assessments as `CUSTOM` events using the `crp.*` namespace.
2. MUST preserve unknown `crp.*` event names so future extensions degrade gracefully.
3. MUST NOT emit governance events that are not backed by evidence from the corresponding CRP subsystem.

### 10.3 D3 — Faithful Narration

1. MUST entailment-check every `TEXT_MESSAGE_CONTENT` claim against the event trace before streaming it.
2. MUST withhold claims that the trace does not support.
3. MUST fall back to a deterministic heuristic when the NLI model is unavailable.
4. MUST NOT mark reasoning content as user-facing text without a preceding `REASONING_*` event boundary.

### 10.4 D4 — Verifiable Provenance

1. MUST emit a `crp.provenance` event for every operation that extends the audit chain.
2. The event MUST include the previous and current audit-chain hashes.
3. A conformant server MUST verify the chain on every window commit.

### 10.5 D5 — Quality Streaming

1. SHOULD emit a `crp.quality` event after each operation or window.
2. When emitted, the event MUST include at least `tier` and `confidence`.

### 10.6 D6 — Resumability

1. MUST support `Last-Event-ID` replay for buffered events.
2. MUST authenticate the session before honouring a replay request.
3. SHOULD integrate with the CSO for full cross-window resumability (roadmap).

### 10.7 Transport and Security

1. TEL endpoints MUST be authenticated.
2. TEL endpoints MUST enforce tenant isolation.
3. `STATE_DELTA` payloads MUST be validated against JSON Patch schema before application.
4. Tool-result values streamed as `TOOL_CALL_RESULT` MUST be rendered as inert/declarative content; they MUST NOT be executable by the frontend.

---

## 11. Security Considerations

### 11.1 Adversarial Stream Content

Tool results may originate from untrusted targets. TEL MUST treat such values as adversarial: they MUST be rendered as inert/declarative content and MUST carry a provenance taint indicating their source.

### 11.2 Disclosure Tiers

Not all governance events are appropriate for all audiences. The disclosure tier from CRP-SPEC-006 policy governs which events a subscriber receives:

- **End-user tier:** lifecycle, text, tool summaries, and high-level `crp.quality` events.
- **Operator tier:** end-user events plus `crp.safety_scan`, `crp.policy`, and `crp.verification`.
- **Auditor tier:** operator events plus `crp.provenance` with full audit-chain hashes.

An external end user MUST NOT receive auditor-tier provenance unless explicitly authorised.

### 11.3 Prototype Pollution

`STATE_DELTA` events use JSON Patch. The server and any client applying patches MUST validate patch operations, reject prototype-key paths such as `__proto__` and `constructor`, and constrain paths to the documented state schema.

### 11.4 Replay Boundaries

Replay buffers are bounded. A client that reconnects after a gap larger than the buffer size MUST receive a `STATE_SNAPSHOT` or a graceful error, not stale or partial events that misrepresent the session state.

### 11.5 Chain Integrity

If a client-side recomputation of the audit chain does not match the server-emitted `crp.provenance` hash, the client MUST surface the mismatch and MUST NOT present the affected operations as verified.

---

## 12. References

- CRP-SPEC-001: Core Protocol
- CRP-SPEC-002: HTTP Headers
- CRP-SPEC-003: Context Envelope
- CRP-SPEC-004: Continuation and State Relay
- CRP-SPEC-005: Decision Provenance Engine
- CRP-SPEC-006: Safety Policy
- CRP-SPEC-011: Audit Trail
- CRP-SPEC-016: Gateway Service
- CRP-SPEC-026: Semantic Quality Benchmark
- CRP-SPEC-030: Cognitive State Object
- CRP-SPEC-031: Semantic Task Layer
- CRP-SPEC-049: Verification Relay
- CRP-SPEC-051: Predictive Oversight
- CRP-SPEC-055: Epistemic Positioning

**Companion volume:** Vidiniotis, C. (2026). *The Architecture of Transparency in Agentic AI Systems*. AutoCyber AI Pty Ltd.

**External standards:**
- CopilotKit. (2025). *AG-UI: The Agent-User Interaction Protocol* [Specification]. https://docs.ag-ui.com
- Bryan, P. C., & Nottingham, M. (2013). *JavaScript Object Notation (JSON) Patch* (RFC 6902). IETF. https://doi.org/10.17487/RFC6902

---

*End of CRP-SPEC-056.*
