# CRP Availability & Distribution

*Where can you actually use the Context Relay Protocol today, and what's coming next?*

CRP is **both an open protocol and a shipping product**. You can adopt it at four
distinct levels, from "drop a header in" to "run the full governance layer".

---

## 1. The Python SDK — available now

The reference implementation ships as the **`crprotocol`** package on PyPI.

```bash
pip install crprotocol            # core
pip install "crprotocol[nlp]"     # + Decision Provenance Engine (embeddings)
pip install "crprotocol[full]"    # everything (NLP, security, providers, CLI, metrics)
```

```python
import crp
```

- **PyPI:** https://pypi.org/project/crprotocol/
- **Import name:** `crp`
- **Current version:** 3.0.0
- **License:** Elastic License 2.0
- **Python:** 3.10+

What you get: provider adapters (LM Studio / Ollama / llama.cpp / OpenAI / Anthropic),
local-LLM discovery, the Contextual Knowledge Fabric, the Decision Provenance Engine,
safety-policy parsing/enforcement, the HTTP 451 halt contract, the tamper-evident
audit trail (OCSF/SARIF export), per-window HMAC provenance chains, and signed
session tokens. There is also a `crp` CLI.

## 2. The open protocol — vendor-neutral, implement in any language

CRP is fundamentally a **wire contract**, not just a library. The protocol surface is:

- **`CRP-*` HTTP headers** — `CRP-Context-ETag`, `CRP-Session-Id`, `CRP-Window`,
  `CRP-Protocol-Version`, `CRP-Strategy`, `CRP-Provenance-Chain-Integrity`,
  `CRP-Provenance-Window-HMAC`, `CRP-Compliance-Audit-Trail-Id` / `-Uri`,
  `CRP-Set-Session`, and the conditional-request family.
- **The safety-policy grammar** — a declarative, CSP-style policy string
  (`default-src context; halt-on CRITICAL; require-grounding 0.70`).
- **The HTTP 451 halt contract** — a machine-readable refusal body with
  `crp_halt_reason`, `audit_trail_uri`, `oversight_required`, and `retry_condition`.
- **The provenance-chain & HMAC verification rules.**

Anyone can implement a conformant CRP endpoint in any stack. Conformance is checked
by the vector suite in `tests/conformance/` (DPE, headers, HMAC, safety policy,
session, agent levels).

> Specs live in `specification/`, `rfcs/`, and `SPECS_27-05-2027/`. An IETF
> Internet-Draft track is in progress.

## 3. Runnable demos — see it govern a real local LLM now

The repository ships two browser apps (`examples/crp_demos/`) that run CRP against a
real local model with zero cloud calls:

```bash
pip install "crprotocol[nlp]"
python -m examples.crp_demos.server        # http://127.0.0.1:8770
```

- **AI Safety & Governance Console** — injection shield, grounding/risk scoring,
  policy enforcement, HTTP 451 halt, OCSF audit trail.
- **Context Management & Provenance Explorer** — CKF recall, HMAC chain, tamper
  detection, signed session tokens, full `CRP-*` headers.

See the [README demo guide](../README.md#interactive-demo-apps-local-llm).

## 4. Coming next — automated adoption & managed hosting

- **`crp-scan` GitHub Action** *(in design — see `docs/CRP_SCAN_ACTION_PLAN.md`)* —
  a CI check that scans a repo's LLM/agent code and policy files for CRP conformance
  and governance gaps, posting findings on pull requests.
- **CRP Gateway** *(roadmap)* — a managed/self-hostable reverse proxy that enforces
  CRP in front of any LLM endpoint, so applications get governance without changing
  their model-calling code.

---

### Summary

| Level | Status | How to use |
|-------|--------|-----------|
| Python SDK (`crprotocol`) | **Available** | `pip install crprotocol` |
| Open protocol (headers, policy, 451, HMAC) | **Available / spec stable** | Implement against `specification/` + conformance vectors |
| Local demo apps | **Available** | `python -m examples.crp_demos.server` |
| `crp-scan` GitHub Action | **In design** | CI conformance scanning |
| CRP Gateway | **Roadmap** | Managed/self-hosted enforcing proxy |
