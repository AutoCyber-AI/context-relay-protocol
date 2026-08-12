# CRP Scan

**Find ungoverned AI calls before they reach production.**

CRP Scan analyses your codebase for AI-system patterns that bypass governance - unaudited LLM calls, missing safety policies, ungoverned context construction, regulatory-mapping gaps, and version drift. It then opens remediation PRs so your team fixes issues without leaving GitHub.

!!! note "Scan product status"
    The CRP Scan GitHub Action is published. Managed cloud features and the VS Code extension are on the roadmap.

---

## The value in one minute

| Without CRP Scan | With CRP Scan |
|------------------|---------------|
| Ungoverned LLM calls ship to production | Every PR is scanned before merge |
| Compliance gaps discovered during audit | EU AI Act high-risk patterns caught in CI |
| Security issues live for weeks | Hard-coded keys and injection risks flagged immediately |
| Remediation is a ticket backlog | Auto-remediation PRs fix routing + policy stubs |
| No visibility into AI footprint | SARIF findings live in the GitHub Security tab |

---

## Why teams choose CRP Scan

- **Governance in CI, not after an audit.** HIGH/CRITICAL findings are caught in the pull request that introduces them, so fixes cost minutes instead of months.
- **Zero-friction remediation.** Auto-remediation opens a PR with Gateway routing and policy stubs - it never pushes directly to `main`.
- **Free for public repos.** Add one workflow step and every open-source contribution gets the same governance check as enterprise code.

### Who it's for

| Role | Problem | How Scan helps |
|------|---------|----------------|
| **Engineering Manager** | AI calls spread across repos with no visibility | SARIF findings in the GitHub Security tab per repo |
| **Security Engineer** | Hard-coded keys and injection risks slip through PR | CRITICAL findings block merge until fixed |
| **Compliance Lead** | No evidence that code-level controls exist | Scan logs show governance gaps were caught pre-merge |
| **Open Source Maintainer** | Need free governance for public contributions | Public repos scan at no cost |

---

## What it catches

| Finding | Severity | Remediation |
|---------|----------|-------------|
| LLM call without CRP Gateway routing | HIGH | Change `base_url` to Gateway |
| Missing `CRP-Safety-Policy` on production path | MEDIUM | Add policy via no-code builder or YAML |
| EU AI Act high-risk pattern without classifier | CRITICAL | Run risk classifier in CRP Comply |
| Hard-coded provider API keys | CRITICAL | Move to CRP Key Vault |
| Context truncation risk (no windowing) | MEDIUM | Enable CDR/CDGR envelope |
| Multi-agent chain without budget header | HIGH | Add `CRP-Chain-Budget` |
| Missing audit log destination | MEDIUM | Connect CRP Comply webhook |

---

## GitHub Action

Add one workflow step and every pull request is automatically scanned.

```yaml
# .github/workflows/crp-scan.yml
name: CRP Governance Scan
on: [pull_request]

permissions:
  contents: read
  security-events: write

jobs:
  crp-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: AutoCyber-AI/crp-scan@v1
        with:
          paths: 'src,lib'
          fail-on: HIGH
          upload-sarif: true
          summary: true
          auto-remediate: false   # set true to open remediation PRs
```

### Outputs

- `findings-count` - number of findings detected
- `highest-severity` - NONE | LOW | MEDIUM | HIGH | CRITICAL
- `sarif-file` - path to SARIF artefact for the Security tab
- `pr-url` - opened remediation PR (when `auto-remediate: true`)

### Auto-remediate

Set `auto-remediate: true` and CRP Scan will:

1. Generate a fix branch with Gateway routing + policy stubs
2. Open a PR against the target branch
3. **Never** push directly to `main` (CRP invariant)

---

## CLI scanning

You can also scan locally before pushing:

```bash
.venv/Scripts/python -m crp scan --paths src,lib --fail-on HIGH
```

[:octicons-arrow-right-24: CLI Guide](../getting-started/cli.md)

---

## VS Code Extension

!!! warning "Not yet implemented"
    The CRP Scan VS Code extension is on the roadmap and is not currently available.

---

## Pricing

| Repository Type | Cost |
|-----------------|------|
| **Public repos** | Free |
| **Private repos** | Included in CRP Comply Starter ($49/mo or $490/yr) or Scale ($499/mo or $4,990/yr) |
| **Enterprise** | Unlimited private repos + custom rules + SSO |

Annual plans save ~17% vs monthly.

[:octicons-arrow-right-24: GitHub Marketplace](https://github.com/marketplace/actions/crp-scan)
[:octicons-arrow-right-24: View on GitHub](https://github.com/AutoCyber-AI/crp-scan)

---

## Get started

Add CRP Scan to your repository in one workflow step, or view pricing for private-repo and Enterprise tiers.

[GitHub Marketplace →](https://github.com/marketplace/actions/crp-scan){ .md-button .md-button--primary }
[View Pricing →](../pricing.md){ .md-button }
[CLI Guide →](../getting-started/cli.md){ .md-button }
