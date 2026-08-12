"""Debug gap analysis to understand gap_score=1.000 issue."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from crp.continuation.gap import (
    _extract_l1_structural,
    _extract_l2_semantic,
    _expand_enumerated_items,
    _text_overlap,
    extract_task_requirements,
    gap_analysis,
    clear_requirement_cache,
    FULFILLMENT_THRESHOLD,
)
import re

TASK = """You are writing a comprehensive technical reference document.

Write a document titled "The 30 Pillars of Modern Software Engineering" with EXACTLY 30 numbered sections.

IMPORTANT: Do NOT use <think> tags. Go straight to writing the document.

REQUIRED SECTIONS (all 30 must be present):
1. Input Validation — describe techniques, give 2 code examples in Python
2. Authentication — multi-factor auth, OAuth2 flows, session management
3. Authorization — RBAC, ABAC, principle of least privilege with examples
4. Cryptography — symmetric vs asymmetric, hashing algorithms, key management
5. Error Handling — secure logging, never expose stack traces, structured errors
6. Data Protection — encryption at rest, in transit, data classification levels
7. API Security — rate limiting, input sanitization, CORS configuration
8. Dependency Management — supply chain attacks, SCA tools, SBOM generation
9. Security Testing — SAST, DAST, penetration testing, fuzzing strategies
10. Incident Response — detection, containment, eradication, recovery phases
11. Code Review — static analysis, peer review practices, security checklists
12. Container Security — image scanning, runtime protection, Kubernetes hardening
13. Network Security — zero trust architecture, TLS configuration, firewall rules
14. Database Security — parameterized queries, access controls, backup encryption
15. Logging and Monitoring — SIEM integration, anomaly detection, audit trails
16. DevSecOps Pipeline — CI/CD security gates, automated scanning, policy as code
17. Cloud Security — IAM policies, shared responsibility model, cloud-native tools
18. Mobile Security — certificate pinning, secure storage, biometric authentication
19. Compliance — SOC2, GDPR, HIPAA, PCI-DSS requirements and implementation
20. Threat Modeling — STRIDE methodology, attack trees, risk scoring frameworks
21. Secure SDLC — security requirements, design reviews, security sprints
22. Identity and Access Management — SSO, directory services, lifecycle management
23. Secrets Management — vault integration, rotation policies, zero-trust secrets
24. Resilience Engineering — chaos engineering, fault injection, graceful degradation
25. Data Privacy — anonymization, pseudonymization, consent management, DSAR
26. Supply Chain Security — SLSA framework, provenance, artifact signing
27. Observability — distributed tracing, metrics, SLOs, error budgets
28. Infrastructure as Code — Terraform, policy-as-code, drift detection
29. AI/ML Security — adversarial attacks, model poisoning, prompt injection defense
30. Quantum-Safe Cryptography — post-quantum algorithms, migration planning, NIST PQC

RULES:
- Each section MUST have a heading "## N. Title"
- Each section MUST have at least 2 detailed paragraphs
- Include specific tool names, framework references, and best practices
- End with a "## Conclusion" that references all 30 pillars

Write the complete document now. Do not skip any section."""

# Step 1: Check requirement expansion
print("=" * 60)
print("STEP 1: Requirement Extraction")
print("=" * 60)

clear_requirement_cache()
l1 = _extract_l1_structural(TASK)
print(f"\nL1 requirements: {len(l1)}")
for r in l1[:5]:
    print(f"  [{r.category}] {r.text}")
if len(l1) > 5:
    print(f"  ... and {len(l1) - 5} more")

l2 = _extract_l2_semantic(TASK)
print(f"\nL2 requirements: {len(l2)}")
for r in l2[:5]:
    print(f"  [{r.category}] w={r.weight} {r.text[:80]}")
if len(l2) > 5:
    print(f"  ... and {len(l2) - 5} more")

clear_requirement_cache()
all_reqs = extract_task_requirements(TASK)
print(f"\nTotal combined requirements: {len(all_reqs)}")
section_reqs = [r for r in all_reqs if r.category.startswith("section_")]
print(f"Section requirements: {len(section_reqs)}")
other_reqs = [r for r in all_reqs if not r.category.startswith("section_")]
print(f"Other requirements: {len(other_reqs)}")
for r in other_reqs:
    print(f"  [{r.category}] w={r.weight} {r.text[:80]}")

# Step 2: Check text overlap matching
print("\n" + "=" * 60)
print("STEP 2: Text Overlap Matching")
print("=" * 60)

test_headings = [
    "1. Input Validation",
    "2. Authentication",
    "3. Authorization",
    "4. Cryptography",
    "5. Error Handling",
    "6. Data Protection",
    "7. API Security",
]

test_facts = [
    "Input validation ensures data integrity by rejecting invalid or malicious inputs.",
    "Multi-factor authentication (MFA) adds layers of security.",
    "Role-Based Access Control (RBAC) assigns permissions based on roles.",
]

print("\nSection req vs heading matching:")
for i, heading in enumerate(test_headings[:3], 1):
    req_text = f"Section {i}: {heading.split('. ', 1)[1] if '. ' in heading else heading}"
    score = _text_overlap(req_text, heading)
    print(f"  '{req_text}' vs '{heading}' → score={score:.3f} (threshold={FULFILLMENT_THRESHOLD})")

print("\nSection req vs fact matching:")
for i, fact in enumerate(test_facts, 1):
    req_text = section_reqs[i-1].text if i <= len(section_reqs) else f"Section {i}: test"
    score = _text_overlap(req_text, fact)
    print(f"  '{req_text}' vs '{fact[:60]}...' → score={score:.3f}")

# Step 3: Full gap analysis with fake facts
print("\n" + "=" * 60)
print("STEP 3: Full Gap Analysis (simulated)")
print("=" * 60)

class FakeFact:
    def __init__(self, text):
        self.text = text
        self.confidence = 0.8

fake_facts = [FakeFact(f) for f in test_facts]
fake_headings = test_headings

clear_requirement_cache()
result = gap_analysis(TASK, fake_facts, document_headings=fake_headings)
print(f"\nGap score: {result.gap_score:.3f}")
print(f"Fulfilled: {result.fulfilled_count}/{result.total_count}")
print(f"\nFulfilled requirements:")
for r in result.requirements:
    if r.fulfilled:
        print(f"  ✓ {r.text[:60]} (score={r.fulfillment_score:.3f})")
print(f"\nUnfulfilled requirements (first 10):")
for r in result.unfulfilled[:10]:
    print(f"  ✗ {r.text[:60]} (best_score={r.fulfillment_score:.3f})")
