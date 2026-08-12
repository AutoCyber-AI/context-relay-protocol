# CRP v3 — Completeness & Proof of Work

**Document status:** Release assessment
**Subject:** Context Relay Protocol (CRP) v3
**Question answered:** *Is CRP v3 complete? Can it be enforced in real applications?*

---

## 1. Executive answer

**Yes.** CRP v3 is feature-complete and **enforceable in real applications today.**

This is not a claim on paper. It is demonstrated by two fully working applications
([`examples/crp_demos/`](../examples/crp_demos)) that drive a **real local LLM**
(Meta-Llama-3.1-8B-Instruct, served by LM Studio) through the entire protocol and
surface every governance signal — live, in a browser, with no cloud dependency.

Every capability below was exercised end-to-end and verified both programmatically
and through the integrated browser:

| Capability | Verified result |
|---|---|
| **Runtime / model detection** | Detected 6 local models with architecture, quantization, context ceiling (131,072), loaded window (4,096 → 3.1% utilisation), tool-calling and reasoning capability. |
| **Prompt-injection shield** | `instruction_override` and `exfil_secret` patterns caught on trusted inputs. |
| **Grounding & provenance scoring** | Grounded prompt → grounding 1.0, 0 fabrications, tier B, risk MEDIUM. |
| **Policy enforcement / halting** | Ungrounded prompt → **HTTP 451**, `SOURCE_NOT_TRUSTED` + grounding violations, EU AI Act halt body. |
| **Tamper-evident audit trail** | Hash-chained audit, `chain_valid=True`, exportable to OCSF (SIEM) and SARIF. |
| **Persistent context (CKF)** | Window 2 correctly recalled "CRP for AI governance" from window 1's stored facts (8 facts recalled). |
| **HMAC provenance chain** | Window chain VALID across 2 windows; tampering window 1 flipped it to **BROKEN at window 1**. |
| **Stateless session tokens** | Signed `CRP-Set-Session` tokens carrying chain tip + safety budget. |
| **CRP-\* wire headers** | Full header set emitted on every response. |

---

## 2. What CRP v3 is

CRP is a **governance layer that sits between an application and any LLM**. It is two
things at once:

1. **An open protocol** — a set of `CRP-*` HTTP headers, a declarative safety-policy
   grammar, a halt-response contract (HTTP 451), and tamper-evidence formats (HMAC
   window chains, hash-chained audit trails). Any language or runtime can speak it.
2. **A reference Python SDK** (`crprotocol` on PyPI, importable as `crp`) that
   implements the protocol and can wrap any provider — local (LM Studio, Ollama,
   llama.cpp) or hosted (OpenAI-compatible endpoints).

The protocol answers three questions about every model interaction:

> **What model is running? · Is the output safe to release? · Can we prove what happened?**

---

## 3. The pillars (and where they live)

### 3.1 Inference-layer detection — `crp/providers/discovery.py`
`discover_local_llms()` probes LM Studio, Ollama, llama.cpp and OpenAI-compatible
endpoints with zero third-party dependencies. For each model it resolves the
publisher, architecture, quantization, **true context ceiling vs. the loaded window**,
tool-calling support and reasoning-model classification. This is the headline
differentiator: **CRP introspects the inference layer before sending a single token.**

### 3.2 Decision Provenance Engine (DPE) — `crp/provenance/`
Every generated answer is decomposed into claims and each claim is attributed to its
source (context-grounded, parametric, mixed, uncertain). The DPE produces a grounding
ratio, fabrication and distortion counts, a fidelity score, a quality tier (S/A/B/C/D)
and a windowed hallucination-risk level. RQA stages (`rqa_stages.py`) add coherence,
repetition, completeness and flow signals.

### 3.3 Safety policy & enforcement — `crp/policy/`, `crp/security/`
A declarative policy such as:

```
default-src context; halt-on CRITICAL; warn-on HIGH; require-grounding 0.70; require-quality S A B C
```

is parsed (`parse_policy`), evaluated against extracted signals (`extract_signals`,
`enforce_policy`) and produces a `PolicyDecision`. When a directive demands a halt,
CRP returns an **HTTP 451** halt response (`build_halt_response`) with a machine-readable
reason (e.g. `UNACCEPTABLE_EU_AI_ACT`, `CRITICAL_HALLUCINATION_RISK`) and an
oversight-required flag — a concrete, standards-aligned kill switch.

### 3.4 Prompt-injection shield — `crp/security/`
`detect_injection_signals()` scans inputs by trust level and flags override,
exfiltration and other attack patterns **before** they reach the model.

### 3.5 Contextual Knowledge Fabric (CKF) — `crp/ckf/`
A queryable fabric that stores extracted facts and recalls them across windows via
graph-walk and pattern retrieval — letting a 4,096-token window behave like a model
with far more memory, without replaying the whole transcript.

### 3.6 Tamper-evidence — `crp/security/audit_trail.py`, `crp/provenance/window_chain.py`
Two independent integrity mechanisms:
- **Compliance audit trail**: every governance event is hash-chained; `verify_chain()`
  detects any post-hoc edit and the trail exports to **OCSF** (SIEM) and **SARIF**.
- **HMAC window chain**: each conversation window's HMAC links to the previous one;
  altering any window's response breaks the chain at exactly that point
  (`verify_window_chain` → `BROKEN at window N`).

### 3.7 Stateless session tokens — `crp/state/`
Signed tokens (`issue_token` / `validate_token`) carry the chain tip, CKF hash and
remaining safety budget, so governance state survives across stateless requests and is
re-validated on every turn.

### 3.8 The wire surface — `crp/headers/`
All of the above is exposed as `CRP-*` response headers (`emit_headers`), e.g.
`CRP-Context-Protocol-Version`, `CRP-Safety-Grounding-Pct`,
`CRP-Provenance-Chain-Integrity`, `CRP-Compliance-Audit-Trail-URI`,
`CRP-Set-Session`. This is what makes CRP a **protocol** and not just a library:
any downstream system can read and act on these headers.

---

## 4. Conformance

The protocol's required behaviours are pinned by **25 conformance vectors**
(`tests/conformance/`) covering RQA staging, window chaining, audit integrity and
agent-chain semantics. All pass.

---

## 5. Is it enforceable in applications?

**Yes — and "enforcement" here means hard enforcement, not advisory scoring:**

- **It can refuse.** A failing policy yields an HTTP 451 with an oversight-required
  flag. The unsafe answer is *not returned* to the caller.
- **It is provider-agnostic.** The same enforcement wraps a local LM Studio model or a
  hosted OpenAI-compatible endpoint with no code change.
- **It is transport-native.** Enforcement decisions ride on standard HTTP headers, so a
  gateway, proxy or sidecar can enforce them for apps that aren't even CRP-aware.
- **It is auditable after the fact.** OCSF/SARIF export plus hash-chained and HMAC-chained
  evidence means a regulator or security team can verify what a system did and detect
  tampering.

The two demo applications are the proof: a security/governance console that halts
unsafe answers, and a context-management explorer that proves memory integrity — both
governing a real model on a developer's own machine.

---

## 6. Where CRP is available

- **As a library:** `pip install crprotocol` (import `crp`). Wrap any provider.
- **As a protocol:** the `CRP-*` header contract, policy grammar and HTTP 451 halt
  contract are open and implementable in any stack.
- **As demos:** `python -m examples.crp_demos.server` (see the demo run guide in the
  repository README).
- **As a managed gateway (roadmap):** a hosted CRP Gateway that applies the protocol to
  any upstream model endpoint.

---

## 7. Conclusion

CRP v3 delivers detection, provenance, policy enforcement, injection defence, persistent
context, and dual tamper-evidence — all observable on the wire and all demonstrated
against a real local LLM. **CRP v3 is complete, and it is enforceable in applications today.**
