<!--
  Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
  Licensed under Elastic License 2.0 — see LICENSE.md for details.
-->

# CRP-Scan GitHub Action — Complete Setup, Testing & Verification Guide

> **What this guide does.** Takes you from zero to a live, verified GitHub Action that scans
> your repository for AI-governance issues on every pull request, uploads results to the
> GitHub Security tab, and optionally fails the build when ungoverned LLM calls are found.

---

## Table of Contents

1. [What crp-scan detects](#1-what-crp-scan-detects)
2. [Prerequisites](#2-prerequisites)
3. [Add crp-scan to your repository (5 minutes)](#3-add-crp-scan-to-your-repository-5-minutes)
4. [Understanding the output](#4-understanding-the-output)
5. [Viewing results in the GitHub Security tab](#5-viewing-results-in-the-github-security-tab)
6. [Testing that it actually works](#6-testing-that-it-actually-works)
7. [Advanced configuration](#7-advanced-configuration)
8. [Connecting to CRP Comply (remediation)](#8-connecting-to-crp-comply-remediation)
9. [Troubleshooting](#9-troubleshooting)
10. [All inputs and outputs reference](#10-all-inputs-and-outputs-reference)

---

## 1. What crp-scan detects

crp-scan runs six static-analysis rules against your codebase:

| Rule | Name | What it catches | Default severity |
|------|------|-----------------|-----------------|
| CRP001 | Ungoverned LLM call | Direct `openai.`, `anthropic.`, `transformers.pipeline(`, raw HTTP to `/v1/chat` — no CRP adapter in the call path | HIGH |
| CRP002 | CRP used, no safety policy | CRP is imported but no safety-policy YAML/JSON file is defined | HIGH |
| CRP003 | No halt / enforcement path | No `halt`, `refuse`, or HTTP-451 pattern anywhere in the repo | MEDIUM |
| CRP004 | No provenance / audit trail | No audit log, no `provenance`, no HMAC or signing pattern | MEDIUM |
| CRP005 | Policy lint | Safety-policy file has weak grounding score or missing required fields | LOW |
| CRP006 | Version drift | crprotocol version < minimum configured threshold | LOW |

**Conformance score** = 0–100. A repo with zero findings scores 100.
Zero-dependency core: no ML models are loaded during the scan — it's pure static analysis.

---

## 2. Prerequisites

| Requirement | Notes |
|-------------|-------|
| GitHub repository | Public or private, any language |
| GitHub Actions enabled | Settings → Actions → Allow all |
| `security-events: write` permission | Required for SARIF upload (Security tab) |
| crprotocol ≥ 3.1.0 | Installed automatically by the action |

---

## 3. Add crp-scan to your repository (5 minutes)

### Step 1 — Create the workflow file

Create `.github/workflows/crp-scan.yml` in your repository:

```yaml
name: CRP-Scan

on:
  push:
    branches: [main, master, develop]
  pull_request:
    branches: [main, master, develop]
  schedule:
    - cron: '0 8 * * 1'    # Every Monday 08:00 UTC
  workflow_dispatch:        # Manual trigger

permissions:
  contents: read
  security-events: write   # Required for SARIF upload to Security tab
  actions: read

jobs:
  crp-scan:
    name: AI Governance Scan
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Run CRP-Scan
        uses: AutoCyber-AI/crp-scan@v1
        with:
          paths: '.'              # Scan entire repo
          fail-on: HIGH           # Fail build on HIGH or CRITICAL findings
          format: text            # Console output format (text|json|markdown)
          upload-sarif: true      # Upload to GitHub Security tab
          summary: true           # Append to Actions step summary
```

### Step 2 — Commit and push

```bash
git add .github/workflows/crp-scan.yml
git commit -m "ci: add CRP AI-governance scan"
git push
```

The workflow will trigger automatically on the push.

### Step 3 — Verify it ran

1. Go to your repository on GitHub
2. Click **Actions** tab
3. Click the **CRP-Scan** workflow run
4. Expand the **Run CRP-Scan** step to see findings

That's it. The action installs `crprotocol[cli]>=3.1.0` automatically — no Python setup required on your end.

---

## 4. Understanding the output

### Console output (text format)

```
CRP AI-Governance Scan
======================
Scanned: 42 files in 0.8s
Conformance score: 67/100

Findings (3):

HIGH  CRP001  src/llm/client.py:14
      Ungoverned LLM call — direct openai.ChatCompletion call without CRP adapter.
      Remediation: Wrap with CRP DispatchRouter or register a CRP policy.
      → https://comply.crprotocol.com/?ref=crp-scan&rule=CRP001

MEDIUM  CRP003  (repo-level)
      No halt / enforcement path detected.
      → https://comply.crprotocol.com/?ref=crp-scan&rule=CRP003

MEDIUM  CRP004  (repo-level)
      No provenance or audit trail found.
      → https://comply.crprotocol.com/?ref=crp-scan&rule=CRP004
```

### Exit codes

| Exit code | Meaning |
|-----------|---------|
| 0 | Scan complete, no findings at or above `fail-on` severity |
| 1 | One or more findings at or above `fail-on` severity (build fails) |
| 2 | Scan error (crprotocol not installed, malformed paths, etc.) |

### Step summary (markdown)

When `summary: true`, the action appends a formatted table to the GitHub Actions step
summary, visible at the bottom of the workflow run page.

---

## 5. Viewing results in the GitHub Security tab

### Where to find them

After a successful workflow run with `upload-sarif: true`:

1. Go to your repository → **Security** tab
2. Click **Code scanning alerts**
3. All findings appear here with line-number links, severity labels, and suggested fixes

### Requirements for SARIF upload

- Repository must have **GitHub Advanced Security** enabled (free for all public repos;
  requires GitHub Enterprise for private repos without GHAS)
- Workflow must have `security-events: write` permission (see workflow above)

### What the Security tab shows

- **Rule ID** (CRP001–CRP006) with description
- **File + line number** — click to jump to the exact location
- **Severity** (critical, high, medium, low, note)
- **Suggested fix** — links to CRP Comply for guided remediation
- **Dismiss/resolve** — integrated with your PR review flow

---

## 6. Testing that it actually works

### Test A — Trigger a real finding (recommended)

Add a test file with a known-bad pattern:

```bash
# In your repo root
cat > _crp_test.py << 'EOF'
# Intentional test — delete after verifying crp-scan works
import openai
client = openai.OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
EOF
git add _crp_test.py
git commit -m "test: add crp-scan trigger file"
git push
```

**Expected result:**
- `crp-scan` step reports `CRP001 HIGH` on `_crp_test.py:3` and `_crp_test.py:5`
- Build exits with code 1 (because `fail-on: HIGH`)
- Findings appear in Security tab under Code scanning

**Clean up:**
```bash
git rm _crp_test.py
git commit -m "test: remove crp-scan trigger file"
git push
```

### Test B — Verify report-only mode

Change `fail-on: HIGH` to `report-only: true` — findings should still appear in the
Security tab and step summary, but the build should exit 0 (not fail).

### Test C — Run locally before pushing

```bash
# Install crprotocol with CLI extra
pip install "crprotocol[cli]>=3.1.0"

# Scan your repo
python -m crp scan --paths . --format text --sarif /tmp/out.sarif

# View the SARIF output
cat /tmp/out.sarif
```

### Test D — Verify Security tab output

After the action runs with `upload-sarif: true`:

```bash
# List code scanning alerts via GitHub CLI
gh api repos/{owner}/{repo}/code-scanning/alerts \
  --jq '.[] | {rule_id: .rule.id, severity: .rule.severity, location: .most_recent_instance.location.path}'
```

You should see entries for each `crp-scan` finding.

---

## 7. Advanced configuration

### Scan only specific directories

```yaml
- uses: AutoCyber-AI/crp-scan@v1
  with:
    paths: 'src,lib,api'    # comma-separated
```

### Enforce minimum crprotocol version

```yaml
- uses: AutoCyber-AI/crp-scan@v1
  with:
    min-version: '3.1.0'    # fails if repo uses older crprotocol
```

### Use in monorepos

```yaml
strategy:
  matrix:
    service: [auth-service, inference-api, gateway]
steps:
  - uses: actions/checkout@v4
  - uses: AutoCyber-AI/crp-scan@v1
    with:
      paths: '${{ matrix.service }}/src'
      fail-on: CRITICAL    # Only fail on critical in monorepo services
```

### Require high grounding score on policies

```yaml
- uses: AutoCyber-AI/crp-scan@v1
  with:
    min-grounding: '0.80'   # Fail if policy grounding < 80%
```

### Full enterprise configuration

```yaml
- uses: AutoCyber-AI/crp-scan@v1
  with:
    paths: '.'
    fail-on: MEDIUM         # Strict: fail on MEDIUM and above
    format: markdown        # Richer console output
    upload-sarif: true
    summary: true
    min-version: '3.1.0'
    min-grounding: '0.75'
    report-only: false      # Hard-fail the build
    python-version: '3.12'
```

---

## 8. Connecting to CRP Comply (remediation)

Every finding in the crp-scan output includes a link:
```
→ https://comply.crprotocol.com/?ref=crp-scan&rule=CRP001
```

This link opens the CRP Comply onboarding flow pre-populated with:
- The specific rule that was violated
- The detected language/framework
- An AI-generated fix plan for your codebase

### What CRP Comply provides (vs. crp-scan)

| Feature | crp-scan (free) | CRP Comply (paid) |
|---------|-----------------|-------------------|
| Detect ungoverned LLM calls | ✓ | ✓ |
| SARIF / Security tab upload | ✓ | ✓ |
| Build gate (fail on severity) | ✓ | ✓ |
| Step-by-step remediation guide | ✗ | ✓ |
| Auto-generated policy files | ✗ | ✓ |
| One-click PR with fixes applied | ✗ | ✓ |
| SSO, audit trail, attestations | ✗ | ✓ |
| Multi-repo dashboard | ✗ | ✓ |

### Analytics attribution

The `?ref=crp-scan` query parameter is tracked in the Comply backend so you can measure
how many signups flow from the scanner. Use `?ref=crp-scan&campaign=<name>` for
campaign-specific attribution.

---

## 9. Troubleshooting

### "No such command 'scan'"

**Cause:** crprotocol < 3.1.0 installed (3.1.0 is the first version with `crp scan`).

**Fix:** The action now pins `>=3.1.0` automatically. If you see this error, add:
```yaml
with:
  crprotocol-version: '3.1.0'
```

### "Path does not exist: crp-scan.sarif"

**Cause:** The scan step exited with an error before writing the SARIF file, so the
upload-sarif step couldn't find it.

**Fix:** Check the "Run CRP-Scan" step logs for the actual error. Common causes:
- `paths` contains a path that doesn't exist
- Python version incompatibility (try `python-version: '3.11'`)

### "Resource not accessible by integration" on upload-sarif

**Cause:** Missing `security-events: write` permission.

**Fix:** Add to your workflow:
```yaml
permissions:
  security-events: write
```

### Findings not appearing in Security tab

**Cause:** Private repository without GitHub Advanced Security (GHAS).

**Fix:** Either make the repository public, or enable GHAS (requires GitHub Enterprise).
Alternatively, disable SARIF upload and rely on the step summary + console output:
```yaml
with:
  upload-sarif: false
  summary: true
  format: markdown
```

### "pip install ... >= 3.1.0 failed"

**Cause:** PyPI index lag (rare; new version takes ~2 min to propagate).

**Fix:** Explicitly pin the version:
```yaml
with:
  crprotocol-version: '3.1.0'
```

---

## 10. All inputs and outputs reference

### Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `paths` | No | `.` | Comma-separated paths to scan |
| `fail-on` | No | `HIGH` | Minimum severity that exits non-zero |
| `format` | No | `text` | Console format: `text\|json\|markdown\|sarif\|junit` |
| `upload-sarif` | No | `true` | Upload to GitHub Security tab |
| `summary` | No | `true` | Append to Actions step summary |
| `min-version` | No | `''` | Enforce minimum crprotocol version |
| `min-grounding` | No | `0.0` | Minimum policy grounding score (0–1) |
| `report-only` | No | `false` | Report findings but always exit 0 |
| `python-version` | No | `3.11` | Python version for crprotocol install |
| `crprotocol-version` | No | `''` | Pin crprotocol version (blank = latest ≥3.1.0) |

### Outputs

| Output | Description | Example |
|--------|-------------|---------|
| `sarif-file` | Absolute path to generated SARIF | `/home/runner/work/_temp/crp-scan.sarif` |
| `findings-count` | Total findings count | `3` |
| `highest-severity` | Worst severity found | `HIGH` |

### Using outputs in downstream steps

```yaml
- name: Run CRP-Scan
  id: crp
  uses: AutoCyber-AI/crp-scan@v1

- name: Post scan summary
  run: |
    echo "Found ${{ steps.crp.outputs.findings-count }} findings"
    echo "Highest: ${{ steps.crp.outputs.highest-severity }}"
    echo "SARIF at: ${{ steps.crp.outputs.sarif-file }}"
```

---

## Quick-start copy-paste

```yaml
# .github/workflows/crp-scan.yml
name: CRP-Scan
on: [push, pull_request, workflow_dispatch]
permissions:
  contents: read
  security-events: write
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: AutoCyber-AI/crp-scan@v1
        with:
          fail-on: HIGH
          upload-sarif: true
          summary: true
```

**To see findings:** Go to your repo → Security → Code scanning alerts.

---

*Licensed under the Elastic License 2.0 — see [LICENSE.md](../LICENSE.md).*
