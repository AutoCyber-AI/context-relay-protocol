Here's the breakdown — future-proof, convenient, and open-source-aligned MFA for AutoCyber AI:

---

## THE WINNER: Passkeys (FIDO2/WebAuthn)

**Why this is your move:**
- **Phishing-resistant by design** — private key never leaves the device, no shared secrets to steal 
- **User convenience** — Face ID, fingerprint, or device PIN. No codes to type, no apps to open 
- **Mainstream NOW** — 90% consumer awareness, 75% have enabled on at least one account, 5 billion passkeys in use globally as of 2026 
- **Compliance-ready** — NIST SP 800-63-4 (July 2025) recognizes synced passkeys as AAL2-compliant; phishing-resistant MFA is now *required* not recommended 

**The Clerk Problem:** Clerk free tier is limited. You need MFA *now* and you need it *scalable*.

---

## OPEN-SOURCE / SELF-HOSTABLE ALTERNATIVES TO CLERK

Since you want control and innovation potential:

| Platform | Why It Fits | Free Tier / Cost |
|----------|-------------|------------------|
| **Keycloak** | Full open-source IAM, SSO, MFA, RBAC. No vendor lock-in. Self-hosted = zero per-user cost. | Free (Apache 2.0) |
| **Ory** | API-first, modular, maximum flexibility. Built for microservices and custom auth flows. | Free self-hosted |
| **Hanko** | Open-source auth APIs + embeddable UI components. Passkey-first. | 10k MAU free on cloud, free self-hosted |
| **Kinde** | 7,500 MAU free, includes SSO + MFA + unlimited social connections | Free up to 7.5k MAU |
| **WSO2 Identity Server** | Enterprise-grade, self-hosted, context-aware conditional MFA. Steep learning curve but total control. | Free (open-source) |



---

## YOUR IMPLEMENTATION PATH

**Phase 1: Immediate (This Week)**
- Add **WebAuthn/passkeys** as a primary auth method alongside whatever Clerk gives you
- Use `@passwordless-id/webauthn` — open-source, dependency-free, minimalistic library 
- Supports: Chrome 108+, Safari 16+, Firefox 122+, iOS 16+, Android 9+, Windows 11/10

**Phase 2: Migration (Next 1-2 Months)**
- Evaluate **Hanko** or **Kinde** as Clerk replacement — both have generous free tiers and passkey-native design
- If you want total control: **Keycloak** self-hosted on your infrastructure

**Phase 3: Innovation Layer**
- Add **adaptive/context-aware MFA** — risk-based step-up when anomalies detected (new device, unusual location, odd timing) 
- Consider **behavioral biometrics** for continuous auth (typing cadence, mouse patterns) — passive, frictionless 

---

## WHY NOT THESE METHODS?

| Method | Problem |
|--------|---------|
| SMS OTP | Not phishing-resistant, SIM-swappable, NIST no longer recognizes for AAL2  |
| TOTP (Google Authenticator) | Phishable via real-time proxy attacks, MFA fatigue vulnerable |
| Email magic links | Phishable, dependent on email security |
| Push notifications | MFA fatigue / prompt bombing attacks |

---

## BOTTOM LINE

**For AutoCyber AI specifically:**
1. **Passkeys are your default** — they align with your cybersecurity brand, they're what you should be *selling* as best practice
2. **Drop Clerk's free tier limitation** — migrate to Hanko (passkey-native, open-source) or Kinde (7.5k MAU free with MFA)
3. **Position this as a feature** — "We eat our own dog food. AutoCyber AI uses phishing-resistant FIDO2 authentication." That's a LinkedIn post and a trust signal.

Want me to walk through the exact WebAuthn implementation code, or compare the self-hosting setup for Keycloak vs Hanko?





