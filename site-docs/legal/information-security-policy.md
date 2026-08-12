---
title: Information Security Policy
description: >-
  AutoCyber AI Pty Ltd information security policy - covering crprotocol.io,
  CRP products, and the Context Relay Protocol™ open-source project.
---

# Information Security Policy

**Company:** AutoCyber AI Pty Ltd (ABN 22 697 087 166)
**Policy owner:** Constantinos Vidiniotis, Founder & Security Lead
**Effective date:** 27 May 2026
**Review cycle:** Annual (or after a significant incident)
**Version:** 1.0

---

## 1. Purpose and scope

This policy establishes the minimum information security requirements for all systems,
personnel, contractors, and third parties associated with:

- The **CRP™ open-source project** and its supply chain
- **crprotocol.io** and any subdomain
- **CRP product family** (CRP Comply, CRP Gateway, CRP Visualise, CRP Scan, CRP Scribe)
- **Standards body submissions** and supporting artefacts

It is aligned with **ISO/IEC 27001:2022** controls and the **OWASP Top 10 (2021)**.

---

## 2. Information security principles

AutoCyber AI operates under the following principles:

1. **Least privilege** - access is granted only to the minimum necessary level.
2. **Defence in depth** - multiple independent controls at each layer.
3. **Security by default** - production configuration must be secure out of the box.
4. **Privacy by design** - data minimisation and purpose limitation at design time.
5. **Transparency** - security posture is publicly disclosed; incidents are reported promptly.
6. **Continuous improvement** - the posture is reviewed after incidents and annually.

---

## 3. Technical controls

### 3.1 Authentication and access control

| Control | Implementation |
|---|---|
| API authentication | API keys (`crc_*`, `crs_*`) hashed before storage; never logged in plaintext |
| JWT | HS256, minimum 32-byte secret, 1-hour default expiry |
| SSO / OIDC | Clerk JWKS cache with TTL; short-lived tokens |
| Role-based access | Per-tier feature matrix enforced at every endpoint |
| Admin routes | `X-Admin-Secret` validated against a securely stored admin secret; admin routes disabled in production unless explicitly enabled |

### 3.2 Cryptography

| Data | Algorithm |
|---|---|
| Passwords | bcrypt (passlib) |
| API keys at rest | Argon2 or bcrypt hash |
| BYOK LLM keys at rest | libsodium secretbox (XSalsa20-Poly1305)|
| Evidence pack integrity | SHA-256 content hash + HMAC-SHA256 signature |
| Transport | TLS 1.2+ (Railway / Cloudflare edge) |

### 3.3 Input validation and injection prevention

- All user-supplied input is treated as untrusted.
- SQL: parameterised queries only; no raw string interpolation.
- LLM prompts: user content framed as untrusted narrative; classification tools are deterministic Python, not LLM output.
- File uploads: validated type, size-capped, stored outside the web root.
- External URLs: scrapers operate against an allow-list of trusted regulator hosts; no user-controlled URL fetching in production.

### 3.4 OWASP Top 10 (2021) mapping

| Risk | Primary mitigation |
|---|---|
| A01 Broken Access Control | Per-tier feature gate on every endpoint; `user_id` from authenticated principal, never from request body |
| A02 Cryptographic Failures | bcrypt / Argon2 for passwords; libsodium for keys; TLS at edge |
| A03 Injection | Parameterised queries; prompt-injection guardrails; allow-list URL fetching |
| A04 Insecure Design | Agent tools are deterministic Python; clarification budget prevents loops |
| A05 Security Misconfiguration | Production mode disables debug routes; explicit CORS allow-list; non-root Docker user |
| A06 Vulnerable Components | Dependabot weekly; pinned `pyproject.toml` |
| A07 Authentication Failures | Hashed key storage; JWT expiry; Clerk JWKS rotation |
| A08 Software & Data Integrity | HMAC-signed evidence packs; append-only audit JSONL; corpus content-hash |
| A09 Security Logging | Every agent step + tool call logged; per-session trace JSONL |
| A10 SSRF | Only allow-listed regulator hosts reachable from scrapers; no user-controlled URLs |

### 3.5 Container and infrastructure

- Docker images run as **non-root user** with a dedicated `crp` system account.
- Application data stored in volume-mounted paths with minimal filesystem permissions.
- Secrets injected as environment variables; never baked into images.
- Railway platform provides network isolation, HSTS, and TLS termination.

---

## 4. Operational security

### 4.1 Incident response

| Step | Target time |
|---|---|
| Detection and triage | Within 4 hours |
| Containment | Within 8 hours |
| GDPR Art. 33 supervisory-authority notification (if personal data involved) | Within 72 hours |
| GDPR Art. 34 individual notification (high-risk breach) | Without undue delay |
| Root-cause analysis | Within 14 days |
| Public disclosure (if warranted) | Within 30 days |

Security incidents should be reported to [security@crprotocol.io](mailto:security@crprotocol.io)
or via the [Security Advisory process](https://github.com/AutoCyber-AI/context-relay-protocol/security/advisories/new)
on GitHub.

See [SECURITY.md](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/SECURITY.md)
for the full responsible-disclosure policy and severity matrix.

### 4.2 Patch management

- **Critical / High CVEs** - patched within 7 days of disclosure.
- **Medium CVEs** - patched within 30 days.
- **Low CVEs** - addressed in next scheduled release.
- Dependabot is configured for weekly dependency scans on all repositories.

### 4.3 Secrets and key management

- Production secrets injected by the hosting platform's secret manager.
- No secrets committed to source control. `.gitignore` and pre-commit hooks enforce this.
- BYOK LLM keys are encrypted at rest; decrypted only in memory during a request.
- Key rotation is possible without downtime; documented in product runbooks.

### 4.4 Backup and recovery

- Application data backed up daily to an isolated storage volume.
- Retention: 30-day rolling backup.
- Recovery Time Objective (RTO): 4 hours.
- Recovery Point Objective (RPO): 24 hours.

---

## 5. Third-party and supply-chain security

| Supplier | Category | Security basis |
|---|---|---|
| Railway | Hosting | SOC 2 Type II; SCCs for EU data |
| GitHub / Microsoft | Source code, CI | SOC 2 Type II; Microsoft EU Data Boundary |
| Stripe | Payments | PCI-DSS Level 1 |
| Clerk | Identity / OIDC | SOC 2 Type II |

All suppliers are reviewed annually. Any new supplier processing personal data must sign a
Data Processing Agreement (DPA) per GDPR Art. 28 before data transfer begins.

Open-source dependencies are assessed via Dependabot and manual review for any package with
direct access to user data or cryptographic material.

---

## 6. Personnel security

- All personnel and contractors with access to production systems are required to:
  - Use a password manager and unique passwords for all accounts.
  - Enable multi-factor authentication (MFA) on all admin accounts.
  - Complete a security awareness briefing on joining.
  - Report suspected incidents immediately to [security@crprotocol.io](mailto:security@crprotocol.io).
- Access is revoked within 24 hours of departure.

---

## 7. Physical security

AutoCyber AI operates as a remote-first company. Physical security controls:

- Development machines are full-disk encrypted (BitLocker / FileVault).
- Development machines use screen-lock on idle (5 minutes maximum).
- No production data is stored on personal devices.

---

## 8. Compliance alignment

This policy is aligned with:

| Framework | Relevance |
|---|---|
| ISO/IEC 27001:2022 | Information security management system (ISMS) controls |
| ISO/IEC 42001:2023 | AI management system - security of AI systems (A.9, A.10) |
| GDPR (Regulation 2016/679) | Art. 32 security of processing; Art. 33/34 incident notification |
| EU AI Act (Regulation 2024/1689) | Art. 15 accuracy, robustness, and cybersecurity |
| Australian Privacy Act 1988 (Cth) | APP 11 security of personal information |
| NIST AI RMF (2023) | GOVERN, MAP, MEASURE, MANAGE functions |
| OWASP Top 10 (2021) | Application security controls |

---

## 9. Review and exceptions

- This policy is reviewed **annually** and after any significant incident.
- Exceptions to this policy require written approval from the Policy Owner.
- Exceptions are time-limited and logged.

---

## 10. Contact

| Purpose | Contact |
|---|---|
| Security incidents and vulnerabilities | [security@crprotocol.io](mailto:security@crprotocol.io) |
| Privacy questions | [privacy@crprotocol.io](mailto:privacy@crprotocol.io) |
| Policy questions | [info@crprotocol.io](mailto:info@crprotocol.io) |

---

*AutoCyber AI Pty Ltd · ABN 22 697 087 166 · Victoria, Australia*
*Version 1.0 · 27 May 2026*
