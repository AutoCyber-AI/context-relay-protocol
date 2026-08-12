# CRP-SPEC-037: The Unified Configuration - One File Governs Everything

**Document:** CRP-SPEC-037  
**Title:** Context Relay Protocol (CRP) - The Unified Configuration: A Single Source of Truth for Context, Safety, Knowledge, and Behaviour  
**Version:** 1.0.0  
**Status:** Foundational - Experience-Completing  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Unifies:** the configuration surface of every prior spec  
**Prerequisites:** CRP-SPEC-032, CRP-SPEC-033

---

## Abstract

CRP has many configurable surfaces - model selection, safety settings, the Safety Manifest (SPEC-033), context tiers, retrieval parameters, knowledge packs, amplification toggles, depth defaults, storage tuning. Spread across method calls and separate objects, they create exactly the burden CRP promised to remove: managing configuration. This document defines the **Unified Configuration** - a single, optional, declarative config (a `crp.config.yaml` file or one `CRPConfig` object) that governs everything, with sane defaults for every field so that the entire config is optional and the common case is zero configuration. It is the single source of truth that the SDK, the Gateway, and the CRP Comply dashboard all read and write - change it in code and the dashboard reflects it; change it in the dashboard and the file updates. This is the "all-in-one config" that makes CRP's full power adjustable from one place without scattering settings across a codebase, while preserving the principle that a developer who configures nothing still gets a safe, high-quality default.

---

## 1. Why One Config

CRP's configurability, unmanaged, violates its own promise ("never worry about context management") by creating configuration sprawl. The Unified Configuration consolidates every setting into one declarative artifact with three properties:

1. **Optional everywhere** - every field has a default; the entire file can be omitted and CRP runs well.
2. **One source of truth** - code, Gateway, and dashboard read/write the same config.
3. **Layered override** - a clear precedence so per-call needs don't require editing the file.

---

## 2. The Unified Config File

A single `crp.config.yaml` (or equivalent `CRPConfig` object) governs everything. Every section is optional.

```yaml
# crp.config.yaml - the single source of truth for CRP. All optional.

version: "4.0"

# ── MODEL & PROVIDER ──────────────────────────────────────────
model:
  default: "gpt-4o-mini"            # or "local:llama-3.1-8b"
  fallback: "claude-3-5-haiku"      # on provider failure
  providers:                         # vaulted keys referenced by env
    openai:    { key_env: "OPENAI_API_KEY" }
    anthropic: { key_env: "ANTHROPIC_API_KEY" }
  # default: first available provider, no fallback

# ── SAFETY (the Safety Manifest, SPEC-033) ───────────────────
safety:
  profile: "balanced"                # balanced|strict|medical|financial|public
  settings:
    require_grounding: 0.75
    hallucination_halt: "CRITICAL"
    pii_handling: "flag"             # flag|redact|block
    injection_shield: on
  coverage:                          # SPEC-034 §11 addable rules
    jailbreak: on
    toxicity: on
    secret_leakage: block
    copyright: warn
  checkpoints:                       # inline HITL (SPEC-033/034)
    - when: "value.amount > 1000000"
      reason: "Large transactions need sign-off"
      route_to: "risk@company.com"
      on_reject: "fallback"
  custom_rules: ["./safety/competitor_check.py"]
  # default: profile balanced, core rules on, no checkpoints

# ── CONTEXT & RETRIEVAL ───────────────────────────────────────
context:
  mode: "auto"                       # auto|document|conversation|hybrid (SPEC-028)
  depth: "auto"                      # auto|quick|standard|thorough|exhaustive (SPEC-031)
  retrieval:
    min_relevance: 0.55              # CDR (SPEC-024)
    graph_retrieval: on              # CDGR (SPEC-025)
    max_hops: 2
    recency_weighting: on            # SPEC-027
  storage:                           # SPEC-035 tuning
    rolling_log_size: 50             # turns kept in the rolling context log
    hot_cache: on
    scratch_ttl: "5m"                # ephemeral tool-data freshness
  # default: everything auto, sensible thresholds

# ── KNOWLEDGE (CKF) ───────────────────────────────────────────
knowledge:
  sources: ["./docs/", "./policies/"]   # auto-ingested on init
  packs: ["eu-ai-act", "iso-42001"]     # prebuilt knowledge packs
  embedding_model: "text-embedding-3-large"  # consistency (SPEC-027 §2.5)
  # default: zero-CKF until ingest (SPEC-017)

# ── AMPLIFICATION (opt-in, SPEC-023) ──────────────────────────
amplification:
  enabled: false                     # OFF by default - never imposed
  mode: "full"                       # only if enabled: air|cqr|cld|ros|full
  async_only: true
  # default: disabled

# ── COMPLIANCE & AUDIT ────────────────────────────────────────
compliance:
  frameworks: ["eu-ai-act", "gdpr"]
  comply_connect: "${YOUR_COMPLY_ORG_KEY}"  # stream to CRP Comply
  audit_export: "ocsf"
  # default: classify + local audit, no Comply streaming

# ── DEPLOYMENT ────────────────────────────────────────────────
deployment:
  mode: "gateway"                    # gateway|local
  gateway_url: "https://gateway.crprotocol.io/v1"
  region: "eu"                       # data residency
  # default: local (in-process) if no gateway key
```

### 2.1 Loading

```python
import crp
client = crp.Client(config="crp.config.yaml")   # explicit
client = crp.Client()                            # auto-discovers ./crp.config.yaml
client = crp.Client(config=CRPConfig(...))       # programmatic
# no config anywhere → all defaults, CRP runs safely
```

---

## 3. Sane Defaults - The Whole File Is Optional

The defining property: **every field defaults**, so the entire config is optional. A developer with no config file gets:

| Domain | Default behaviour |
|--------|------------------|
| Model | first available provider |
| Safety | balanced profile (halt-on CRITICAL, core rules on) |
| Context | auto mode, auto depth, CDR+CDGR on |
| Knowledge | zero-CKF until first ingest (SPEC-017) |
| Amplification | OFF (never imposed) |
| Compliance | classify + local audit |
| Deployment | local in-process, or gateway if a key is present |
| Storage | rolling log 50, hot cache on, scratch 5m TTL |

This preserves the Level 0/1 promise (SPEC-032): configure nothing, get safe high-quality behaviour. The config exists to *adjust*, never as a prerequisite.

---

## 4. Layered Override Precedence

Configuration resolves in a defined order, so per-call needs never require editing the file:

```
per-call argument        (highest - client.ask(..., depth="thorough"))
   ▼ overrides
session config           (chat = client.session(depth="quick"))
   ▼ overrides
unified config file      (crp.config.yaml)
   ▼ overrides
profile defaults         (safety.profile: "medical" sets a baseline)
   ▼ overrides
CRP system defaults      (lowest - the built-in sane defaults)
```

A developer sets durable choices in the file, applies a profile for a baseline, and overrides per-call when a specific call needs something different. No setting is locked to one layer.

---

## 5. One Source of Truth - Code, Gateway, Dashboard

The Unified Config is the single artifact all three surfaces share:

```
crp.config.yaml  ◄──────────────────────────────────────┐
   │                                                      │
   ├─ SDK reads it          → governs client behaviour    │
   ├─ Gateway reads it      → governs hosted execution    │
   └─ CRP Comply reads it   → renders as editable UI ──────┘
                               (dashboard edits write back to the file/store)
```

- **Code → dashboard:** commit a config change; CRP Comply reflects it.
- **Dashboard → code:** a compliance officer edits safety settings in Comply; the change is written to the config store (and can be exported back to the file / opened as a PR).
- **Provenance:** the active config is hashed (`CRP-Config-Hash` header) so any call can be tied to the exact configuration in force - auditable config provenance.

This is how a non-developer (compliance, safety lead) manages CRP without touching code, while developers keep config-as-code in version control - both editing one source of truth.

---

## 6. Validation and Safety of the Config Itself

```python
crp.config.validate("crp.config.yaml")
```
- Every value checked against its allowed range/type (an invalid `require_grounding: 2.0` is rejected).
- Embedding-model consistency enforced (SPEC-027 §2.5): if `knowledge.embedding_model` changes, CRP warns that the CKF must be re-indexed.
- Dangerous combinations flagged (e.g. `on_timeout: approve` on a financial checkpoint emits a warning).
- Config changes are themselves audited events (changing safety config is governed).

---

## 7. Headers

| Header | Meaning |
|--------|---------|
| `CRP-Config-Hash` | Hash of the active unified config (config provenance) |
| `CRP-Config-Source` | `file` / `object` / `dashboard` / `defaults` |
| `CRP-Config-Profile` | The active profile, if any |

`CRP-Config-Hash` lets an auditor prove which configuration governed any given call - config becomes part of the tamper-evident record.

---

## 8. The Experience This Completes

**Before:** settings scattered across constructor arguments, separate safety objects, per-call flags, and dashboard toggles - configuration sprawl, the very burden CRP promised to remove.

**After:** one optional `crp.config.yaml`. Omit it entirely and CRP runs safely. Use it to adjust anything - model, safety, context, knowledge, amplification, compliance, deployment - from one place. Edit it in code or in the CRP Comply dashboard; both read and write the same source of truth. Every call carries a hash proving which config governed it.

This is the final piece of the all-in-one promise: not just that CRP *handles* context, safety, and compliance, but that *controlling* all of it lives in one place a developer or a compliance officer can understand at a glance - with the freedom to configure nothing and still be safe.

---

## 9. Honest Status & Limits

The Unified Config consolidates existing settings; it introduces no new capability, only a single coherent surface for what the prior specs already expose. Its value is consolidation and the shared source-of-truth, honestly - a DX and governance contribution.

The code↔dashboard bidirectional sync requires the config to live in a store the Gateway/Comply own (for hosted) or a file the SDK reads (for local). In local mode without Comply, the dashboard half does not apply - the file is the sole source. The bidirectional experience is a hosted (Gateway + Comply) feature.

Config-as-code and dashboard-editing can conflict (two people change the same setting). Last-write-wins with an audit record is the default; teams needing stricter control should manage the config via their normal code-review process (PRs) rather than live dashboard edits.

---

## 10. References

- CRP-SPEC-032 - Developer Experience (the config honours progressive disclosure)
- CRP-SPEC-033 - Safety Control Plane (the safety section IS the Safety Manifest)
- CRP-SPEC-034 - Safety Coverage (the coverage rules toggled here)
- CRP-SPEC-035 - Context Lifecycle (the storage section tunes the primitives)
- CRP-SPEC-016 - Gateway (reads the config for hosted execution)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*
