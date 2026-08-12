# AI Safety SDK Reference

<div class="hero-kicker hero-kicker--light">🎯 Agentic Positioning · Safety Built In</div>

CRP makes AI safety **operational**: every LLM call is risk-scored, grounded,
audited, and policy-enforced before the response reaches your application.
This page maps every safety capability to the SDK call that surfaces it and
the deterministic action that enforces it.

Every safety signal is emitted as HMAC-signed, tamper-evident evidence for the
EU AI Act, AIUC-1, ISO 42001, NIST AI RMF, and SOC 2-for-AI. See the
[full control-evidence mapping](../control-evidence.md) or the focused
[AIUC-1 proof point](../aiuc-1.md).

!!! danger "Scores are signals, not decisions"
    A hallucination risk score of `0.85` is meaningless unless it triggers a deterministic action. CRP couples every score to a policy decision: allow, warn, redispatch, halt, or escalate to human review.

## What you get

| Without CRP | With CRP |
|-------------|----------|
| Raw text, no risk signal | `r.crp.risk` on every response |
| No provenance | `r.crp.grounded` + source attribution |
| Scattered safety code | One `safety_profile` config |
| Manual compliance evidence | `client.audit.export()` generates evidence packs |
| Unknown PII/injection exposure | `r.crp.pii_detected`, `r.crp.injection_detected` |
| No audit trail | HMAC-signed chain, `client.audit.verify()` |

## One-line strict safety

```python
import crp

client = crp.SDKClient(safety_profile="strict")
r = client.complete("Summarise the quarterly report.")

print(r.crp.risk)              # LOW | MEDIUM | HIGH | CRITICAL
print(r.crp.grounded)          # True | False
print(r.crp.fabrications)      # unsupported claims count
print(r.crp.pii_detected)      # bool
print(r.crp.injection_detected)# bool
print(r.crp.compliant)         # bool
```

---

## 1. Safety Control Plane

The `SafetyControlPlane` is the central registry for all active safety rules. It lets you inspect, enable, disable, and tune rules at runtime.

```python
from crp.security.control_plane import SafetyControlPlane, get_default_control_plane

scp = get_default_control_plane()
# or
scp = SafetyControlPlane()

print(scp.show())                 # human-readable printout
print(scp.list_capabilities())    # all registered capabilities
print(scp.get_capability("require_grounding"))
print(scp.get_surface_map())      # dict for dashboard rendering
```

### Active capabilities include

| Capability | What it does |
|------------|--------------|
| Hallucination risk scoring | Fabrication, distortion, omission detection |
| Grounding verification | Claim-to-source attribution |
| Contradiction detection | Internal inconsistency in context |
| Repetition detection | Loop prevention |
| PII detection | Personal data in input/output |
| Prompt injection shield | Override/exfiltration patterns in inputs |
| Safety budget | Per-session risk allowance |
| Compliance classification | EU AI Act risk class |
| Tamper-evident audit | Signed event chain |
| Human oversight | Checkpoint and review routing |

```python
from crp.security.control_plane import CustomSafetyRule

scp.register_rule(
    CustomSafetyRule(
        name="no-secrets",
        check_fn=lambda text: "sk-" not in text,
        description="Detect API keys in output",
    ),
)
```

---

## 2. Safety profiles and policy

CRP ships with predefined profiles that map to the orchestrator's human-oversight configuration.

```python
client = crp.SDKClient(safety="strict")
# or
client = crp.SDKClient(safety={
    "profile": "strict",
    "alert_on_quality_below": "B",
})
```

### Built-in profiles

| Profile | Effect |
|---------|--------|
| `permissive` | Fully autonomous, no halts |
| `balanced` *(default)* | Informative logging, no automatic halts |
| `strict` | Require approval for dispatch, halt on injection/PII |
| `research` | Informative logging, keeps autonomous dispatch |

### Per-call override

Safety is configured per client. For per-call tuning, create a scoped client or call `client.configure()`:

```python
client.configure(safety.profile="strict")
r = client.ask("Summarise the contract")
```

---

## 3. Input validation

Layer 1 safety: validate incoming prompts before they reach the model. The SDK invokes the orchestrator validator on every call.

```python
from crp.security.validation import InputValidator

validator = InputValidator()
result = validator.validate("User prompt here...")
print(result.valid)
print(result.warnings)   # e.g. too long, encoded payload, suspicious pattern
```

Malformed input causes `client.complete()` / `client.ask()` to return a response with `finish_reason="error"`.

---

## 4. Prompt injection detection

Detect direct, indirect, and goal-hijacking injection attempts.

```python
from crp.security.injection import InjectionDetector

detector = InjectionDetector()
report = detector.scan("User prompt...")
print(report.has_flags)
for flag in report.flags:
    print(flag.injection_type)   # DIRECT | INDIRECT | GOAL_HIJACK | ...
    print(flag.confidence)
    print(flag.pattern_name)
```

### Enforced via client

```python
r = client.complete("...")
print(r.crp.injection_detected)   # bool
if r.crp.injection_detected:
    # Policy already recorded a halt/oversight event depending on profile
    pass
```

---

## 5. PII and privacy

Detect and classify personal data in inputs and outputs.

```python
from crp.security.privacy import PIIScanner

scanner = PIIScanner()
report = scanner.scan("My email is alice@example.com")
print(report.has_pii)
for det in report.detections:
    print(det.pii_type)   # EMAIL | PHONE | NAME | ...
    print(det.confidence)
```

### Enforced via client

```python
r = client.complete("...")
print(r.crp.pii_detected)          # bool
```

### Consent and retention

```python
from crp.security.consent import ConsentManager
from crp.security.privacy import RetentionManager

consent = ConsentManager()
consent.record_consent(user_id="alice", purpose="support_chat")

retention = RetentionManager()
retention.set_policy(user_id="alice", days=90)
```

---

## 6. Decision Provenance Engine (DPE)

DPE breaks the model output into claims and checks each one against sources.

```python
r = client.ask("What are the EU AI Act penalties?")

print(r.crp.fabrications)       # unsupported claims count
print(r.crp.grounded)           # whether response is grounded
```

!!! note "DPE runs inside the orchestrator"
    The full DPE report (distortions, omissions, contradictions, grounding ratio) is recorded in the tamper-evident audit trail. Use `client.audit.events()` to inspect it.

### Enforceable thresholds

```python
client = crp.SDKClient(safety={
    "profile": "strict",
})

r = client.ask("What are the EU AI Act penalties?")
assert r.crp.compliant
assert r.crp.grounded
```

---

## 7. Safety budget and circuit breaker

Every session has a safety budget. Risky outputs decrement it; if it is depleted, the circuit opens.

```python
r = client.complete("...")
print(r.crp.safety_budget_remaining)   # 0.0–1.0

# When the budget reaches 0, further calls may raise SecurityInvariantError
```

---

## 8. Checkpoints and human oversight

For HIGH/CRITICAL risk outputs, CRP can pause and wait for human review.

```python
from crp.security.control_plane import get_default_control_plane
from crp.security.checkpoint import CheckpointResolution

scp = get_default_control_plane()
checkpoint = scp.create_checkpoint(
    trigger="high_risk",
    timeout=300,
    on_timeout="escalate",
    on_reject="fallback",
)

# UI or webhook resolves the checkpoint
checkpoint.resolve(CheckpointResolution(action="approve", reviewer="alice@example.com"))
```

!!! warning "No Checkpoint.create()"
    Checkpoints are created through the Safety Control Plane (`scp.create_checkpoint()`). `Checkpoint.create()` does not exist.

### SDK shortcut: `client.safety`

You can also create and inspect checkpoints through the SDK namespace:

```python
checkpoint = client.safety.checkpoint(
    trigger="high_risk",
    timeout=300,
    on_timeout="escalate",
    on_reject="fallback",
)
print(client.safety.list_capabilities())
print(client.safety.get_surface_map())
```

`client.safety` mirrors the `SafetyControlPlane` surface and is the recommended way to tune safety rules from application code.

### Automatic escalation

```python
client = crp.SDKClient(safety={
    "profile": "strict",
    "alert_on_quality_below": "B",
})
```

---

## 9. Axiom 4: no CRP headers to providers

CRP strips all `CRP-*` / `X-CRP-*` headers before forwarding a request to an upstream LLM provider.

!!! warning "Not exposed as SDK field"
    `r.crp.axiom4_compliant` is not available on `SDKClient` responses. Axiom 4 is enforced in Gateway and native dispatch.

You can also assert it manually:

```python
from crp.headers import assert_no_crp_headers

provider_headers = {...}
assert_no_crp_headers(provider_headers)   # raises Axiom4Violation if any CRP header present
```

---

## 10. Audit and compliance classification

Every safety event is logged to a tamper-evident audit trail.

```python
r = client.complete("...")
print(r.crp.compliant)          # bool
print(r.crp.audit_url)          # deep link to audit trail
print(r.crp.chain_valid)        # HMAC chain integrity
```

Run an EU AI Act risk classification for your use case:

```python
assessment = client.compliance.classify(
    intended_purpose="Customer support chatbot",
    processes_personal_data=True,
)
print(assessment["risk_level"])
print(assessment["mitigations"])
```

Export the audit trail:

```python
print(client.audit.summary())
print(client.audit.verify())       # (valid, broken_at_sequence)
export = client.audit.export()
```

---

## 11. What is enforced and displayed

| Safety layer | Visible to user | Enforced |
|--------------|-----------------|----------|
| Safety Control Plane | `scp.show()`, `scp.list_capabilities()`, `scp.get_surface_map()` | Active rule registry |
| Policy engine | `r.crp.risk` | Oversight level / halt per profile |
| Input validation | `finish_reason="error"` | Blocks malformed input |
| Injection shield | `r.crp.injection_detected` | Halt or warn per policy |
| PII scanner | `r.crp.pii_detected` | Quarantine or mask per policy |
| DPE | `r.crp.fabrications`, `r.crp.grounded` | Halt/redispatch on threshold breach |
| Safety budget | `r.crp.safety_budget_remaining` | Circuit breaker at depletion |
| Checkpoints | `scp.create_checkpoint()` | Blocks response until resolved |
| Axiom 4 | *(enforced in dispatch)* | Asserts upstream header hygiene |
| Compliance class | `client.compliance.classify()` | Maps to regulatory controls |
| Audit trail | `client.audit.export()` | Tamper-evident chain |

---

## 12. Example: strict medical deployment

```python
from crp.providers.openai import OpenAIAdapter
import crp

client = crp.SDKClient(
    provider=OpenAIAdapter(model="gpt-4o"),
    safety="strict",
    depth="thorough",
)

try:
    r = client.ask("Summarise this patient record")
except crp.SecurityInvariantError as e:
    # e.message, e.code, e.details available
    raise_for_human_review(e)

assert r.crp.compliant
assert r.crp.grounded
assert r.crp.fabrications == 0
assert r.crp.chain_valid
```
