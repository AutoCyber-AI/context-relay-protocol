<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in the CRP specification or reference implementations, please report it responsibly.

### What Constitutes a Security Vulnerability

- **Specification-level**: A design flaw that would allow an attacker to bypass CRP's security architecture (§22 in the core spec, §07_SECURITY.md) — e.g., session key leakage, RBAC bypass, injection through extraction pipeline
- **Schema-level**: A JSON Schema definition that permits malicious input to bypass validation
- **Implementation-level**: Vulnerabilities in reference SDK implementations (reported to the respective SDK repository)

### How to Report

1. **Do NOT open a public issue** for security vulnerabilities
2. Email: **security@crprotocol.io** (or use GitHub Security Advisories on this repository)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Affected specification sections or schema files
   - Suggested fix (if you have one)

### Response Timeline

| Action | Timeline |
|--------|----------|
| Acknowledgment of report | Within 48 hours |
| Initial assessment | Within 7 days |
| Fix or mitigation plan | Within 30 days |
| Public disclosure | After fix is released, coordinated with reporter |

### Scope

| In Scope | Out of Scope |
|----------|-------------|
| CRP specification design flaws | Vulnerabilities in LLM providers |
| JSON Schema validation gaps | Issues with specific LLM model outputs |
| Reference SDK vulnerabilities | Social engineering attacks |
| CKF knowledge fabric security | Denial of service via legitimate API usage |
| Session management weaknesses | Third-party integration vulnerabilities |

### CVE Assignment

Security vulnerabilities in reference implementations will be assigned CVE identifiers when appropriate.

### Recognition

Security researchers who responsibly disclose vulnerabilities will be acknowledged in the CHANGELOG (with permission) and in the project's security hall of fame.

## Security Architecture

The CRP security architecture is fully documented in:

- [07_SECURITY.md](specification/07_SECURITY.md) — Dedicated security document (14 sections)
- [02_CORE_PROTOCOL.md §22](specification/02_CORE_PROTOCOL.md) — Security architecture in the core spec

Key security features:
- HMAC-SHA256 request binding
- Three-tier fact validation (structural, confidence, anomaly)
- RBAC with three roles (OBSERVER, OPERATOR, ADMIN)
- AES-256-GCM encryption at rest
- Input structural validation (injection detection, Unicode normalization, control character stripping)
- Cross-window isolation guarantees
- OWASP Top 10 coverage mapping
- Quantum resistance roadmap (CRYSTALS-Kyber, CRYSTALS-Dilithium)
