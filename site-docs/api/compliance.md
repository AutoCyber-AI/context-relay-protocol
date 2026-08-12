# Compliance API

CRP exposes compliance and audit capabilities through two high-level proxies on
the `SDKClient` instance: `client.compliance.*` and `client.audit.*`. These
proxies wrap the underlying security and provenance subsystems into a concise,
auditable surface.

## Compliance Proxy

### classify()

Classify content against configured compliance frameworks.

```python
result = client.compliance.classify(
    text="We use this system to screen resumes.",
    frameworks=["eu_ai_act", "gdpr"],
)
```

### report()

Generate a multi-framework compliance report for the current session or task.

```python
report = client.compliance.report()
print(report.summary.compliance_score)
print(report.summary.implemented_controls)
print(report.summary.total_controls)
```

### controls()

List the active compliance controls and their status.

```python
controls = client.compliance.controls()
```

---

## Audit Proxy

`client.audit.*` provides a tamper-evident view of the session's audit trail.

### events()

Return the audit events.

```python
for event in client.audit.events():
    print(event)
```

### export()

Export the audit trail to a portable format.

```python
client.audit.export(path="./audit.jsonl")
```

### verify()

Verify the HMAC chain integrity.

```python
is_valid, broken_at = client.audit.verify()
print(f"Valid: {is_valid}, broken at: {broken_at}")
```

### summary()

Return a concise summary of the audit trail.

```python
summary = client.audit.summary()
print(summary.entry_count)
```

---

## Response metadata

Every `complete()` and `ask()` response also carries compliance signals in
`response.crp`:

| Attribute | Meaning |
|-----------|---------|
| `compliant` | Compliance classification result |
| `risk` | LOW, MEDIUM, HIGH, CRITICAL |
| `fabrications` | Detected fabrications |
| `injection_detected` | Prompt-injection flag |
| `pii_detected` | PII detection flag |
| `chain_valid` | Audit-chain integrity status |
