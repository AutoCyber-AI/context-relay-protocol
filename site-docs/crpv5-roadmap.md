---
seo_title: "CRPv5 Improvements — AIUC-1, Safety, Storage & SDK Roadmap"
description: "The CRPv5 improvement roadmap: agentic positioning, SLM-first execution, closing AIUC-1 gaps, hardening the Safety Control Plane, expanding storage backends, and shipping developer-experience upgrades."
tags:
  - crpv5
  - agentic-positioning
  - slm-first
  - roadmap
  - ai-safety
  - aiuc-1
  - crp
---

# CRPv5 Improvement Roadmap

<div class="hero-splash" markdown>

<h1 class="hero-headline" markdown>
CRPv5 Is Shipped.<br/>Here Is What Is Next.
</h1>

<p class="hero-sub">
<strong>CRP v5.1.0 is live</strong>: agentic positioning, the core quality layer (CDR/CDGR/CSO), the Safety Control
Plane, the progressive SDK, pluggable storage backends, Gateway runtime, and Comply automation are
all shipping today. This page tracks the <strong>improvements</strong> that make CRP the default
trust infrastructure for AI agents: <strong>AIUC-1 certification alignment</strong>,
<strong>offensive-security hardening</strong>, <strong>storage flexibility</strong>, and
<strong>developer-experience polish</strong>.
</p>

<div class="hero-buttons">
<a href="/control-evidence/" class="md-button md-button--primary">Control-Evidence Mapping</a>
<a href="/aiuc-1/" class="md-button">AIUC-1 Proof Point</a>
<a href="/spec/" class="md-button">Browse Specs</a>
</div>

</div>

---

## 1. Close AIUC-1 certification gaps

CRP already produces **80%+ of the control evidence** AIUC-1 auditors verify. The remaining gaps
are not technical limitations — they are accreditation, partnership, and scope decisions.

| Gap | Status | Target |
|-----|--------|--------|
| Accredited third-party adversarial testing | Internal red-teaming is continuous; accredited attestation needed | v5.2 — partner with AIUC-1 accredited lab |
| Third-party harmful-output validation | Internal DPE testing runs on every call | v5.2 — independent validation integration |
| AI cyber-misuse prevention | No dedicated module | v5.2 — add cyber-misuse detection stage to DPE |
| Catastrophic-misuse prevention | No dedicated classifier | v5.3 — evaluate with explicit weight-boundary controls |
| Insurance integration | Not started | v5.3 — explore AIUC-insured bundles |

!!! tip "Certification is the floor"
    AIUC-1 certification is a point-in-time validation. CRP's architecture makes adversarial
defense, audit, and compliance evidence continuous by design.

---

## 2. Harden the Safety Control Plane

The Safety Control Plane is the central registry for all active safety rules. v5.x improvements
make it more observable, tunable, and enforceable.

- **Rule versioning & rollback** — every rule change is HMAC-signed and reversible.
- **Per-tenant rule isolation** — SaaS deployments can run different rule sets per organisation.
- **Live rule simulation** — test new rules against historical audit events before enabling them.
- **Safety-coverage heat map** — visualise which risks are covered and which are explicitly out of scope.
- **Automated rule recommendations** — suggest new rules based on audit patterns and benchmark failures.

See [SPEC-033](spec/CRP-SPEC-033-safety-control-plane.md) and [SPEC-034](spec/CRP-SPEC-034-safety-coverage.md).

---

## 3. Expand pluggable storage backends

CRPv5.1 ships InMemory, SQLite, Redis, and S3 backends. v5.x improvements add:

- **PostgreSQL backend** — for teams that want relational audit and CKF storage.
- **Azure Blob / GCS backends** — cloud-native object storage beyond S3.
- **Encrypted local backend** — AES-256-GCM encrypted files for air-gapped deployments.
- **Tiered backend router** — automatically route hot, warm, and cold data to the right store.
- **Backend observability** — latency, hit-rate, and cost dashboards per storage tier.

See [SPEC-038](spec/CRP-SPEC-038-storage-backends.md) and [SPEC-035](spec/CRP-SPEC-035-context-lifecycle.md).

---

## 4. Improve the progressive SDK

The SDK currently supports Level 0 (drop-in governance), Level 1 (ingest/ask), and Level 2
(depth/tools/fine-grained safety). v5.x improvements add:

- **Level 3 — Infrastructure control** — manage Gateway, Comply, and Scan from the SDK.
- **Streaming safety events** — subscribe to `CRP-Safety-*` headers in real time.
- **Multi-provider failover** — automatic fallback across OpenAI, Anthropic, and local models.
- **Offline-first mode** — queue calls and audit events when connectivity is intermittent.
- **Language clients** — JavaScript/TypeScript and Go SDKs for non-Python stacks.

See [SPEC-032](spec/CRP-SPEC-032-developer-experience.md).

---

## 5. Strengthen the Gateway runtime

CRP Gateway is the runtime product that turns every LLM call into a governed, audited event.
v5.x improvements in flight:

- **22-step OpenAI-compatible lifecycle** — full request/response transformation parity.
- **Provider router with key vault** — route by cost, latency, capability, and safety profile.
- **Visual console GA** — real-time session tracing, risk dashboards, and audit exploration.
- **Edge deployment** — lightweight Gateway worker for CDN-integrated inference.
- **Webhook destinations** — stream audit events to SIEM, Slack, or custom endpoints.

See [SPEC-016](spec/CRP-SPEC-016-gateway-service.md) and [SPEC-043](spec/CRP-SPEC-043-gateway-runtime-product.md).

---

## 6. Advance the Semantic Task Layer (STL)

STL turns user requests into operation frames: RETRIEVE, COMPARE, ANALYSE, SYNTHESISE,
GENERATE, VERIFY, CLARIFY, REVISE. v5.x improvements:

- **Add operation-specific safety budgets** — VERIFY can be stricter than GENERATE.
- **Improve depth negotiation** — auto-select D1–D5 depth based on task risk and context size.
- **Multi-operation plans** — decompose complex tasks into bounded STL operations.
- **Goal-compass anchoring** — prevent drift by re-checking task intent at each continuation.
- **Token-efficiency telemetry** — prove <30% token cost vs. injection-equivalent prompts.

See [SPEC-031](spec/CRP-SPEC-031-semantic-task-layer.md).

---

## 7. Enhance CRP Scan remediation

CRP Scan finds ungoverned AI calls in codebases. v5.x improvements make it actionable:

- **Auto-remediation PRs** — open pull requests with Gateway routing and policy stubs.
- **SARIF-native uploads** — integrate with GitHub Advanced Security and other SARIF consumers.
- **Language expansion** — TypeScript, Java, Go, Rust, and C# scanners.
- **IDE extensions** — VS Code and JetBrains plugins for live governance hints.
- **Policy-as-code rules** — let teams define custom governance rules in YAML.

See [SPEC-013](spec/CRP-SPEC-013-github-action.md), [SPEC-036](spec/CRP-SPEC-036-scan-remediation.md), and [SPEC-039](spec/CRP-SPEC-039-semantic-code-ingestion.md).

---

## 8. Benchmark-driven quality gating

The **Semantic Quality Benchmark (SQB)** is the single gate that separates specification from
proven system. v5.x improvements:

- **Publish SQB results** — factual F1 and LLM-as-judge usefulness scores vs. v3 baseline.
- **Add adversarial SQB splits** — measure robustness under prompt-injection and contradiction attacks.
- **Per-model scorecards** — show which models perform best with CRP governance.
- **Continuous regression detection** — run SQB on every release candidate.

See [SPEC-026](spec/CRP-SPEC-026-semantic-quality-benchmark.md).

---

## 9. Standards-track acceleration

CRP is submitted to IETF, IANA, IEEE SA, and ISO/IEC JTC 1/SC 42. v5.x improvements:

- **Publish internet-draft updates** — incorporate header-field registry feedback.
- **IANA registration** — formalise `CRP-*` header fields.
- **Conformance suite v2** — automate Level 1/2/3 conformance testing.
- **Public test vectors** — let anyone verify CRP compatibility independently.

See [SPEC-014](spec/CRP-SPEC-014-conformance.md) and [Standards Track](standards.md).

---

## Release timeline

| Release | Focus | Expected |
|---------|-------|----------|
| **v5.1.0** | Core quality layer, safety surface, SDK, storage backends | Current |
| **v5.2.0** | AIUC-1 accredited testing integration, cyber-misuse DPE stage, PostgreSQL backend | Q3 2026 |
| **v5.3.0** | Catastrophic-misuse classifiers, insurance partnerships, language SDKs | Q4 2026 |
| **v5.4.0** | Gateway visual console GA, edge deployment, IDE extensions | Q1 2027 |

---

## Contribute

CRP is open source under the Elastic License 2.0. If you want to help close a gap, start with
the [conformance suite](testing/index.md) or open an issue on
[GitHub](https://github.com/AutoCyber-AI/context-relay-protocol).

<div class="cta-bar" markdown>
<div class="cta-bar__text">
<div class="cta-bar__title">Want to influence the roadmap?</div>
<div class="cta-bar__subtitle">Join the standards discussion or request an enterprise feature.</div>
</div>
<div class="cta-bar__actions">
<a href="https://github.com/AutoCyber-AI/context-relay-protocol/issues/new" target="_blank" rel="noopener" class="md-button md-button--primary">Open an Issue</a>
<a href="mailto:standards@crprotocol.io" class="md-button">Contact Standards</a>
</div>
</div>
