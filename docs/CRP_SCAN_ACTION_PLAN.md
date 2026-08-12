# `crp-scan` — GitHub Action Design Plan

*Round 5 deliverable. This document is a design/specification only — no implementation
is shipped in this round.*

## Goal

A GitHub Action that brings CRP governance into CI: it **scans a repository's
LLM/agent code and policy configuration**, scores it against CRP conformance, and
**reports governance gaps on pull requests** — the "lint for AI safety" step.

The headline value: the same way `eslint`/`bandit`/`codeql` catch code defects,
`crp-scan` catches *governance* defects — ungoverned model calls, missing grounding
checks, unenforced halt conditions, and absent audit trails.

## What it scans for

| Check | Detects | Severity |
|-------|---------|----------|
| **Ungoverned LLM calls** | Direct calls to `openai`, `anthropic`, `ollama`, LM Studio, `requests`/`httpx` to model endpoints with no CRP adapter/policy in the path. | HIGH |
| **Missing safety policy** | Project uses CRP adapters but defines no `SafetyPolicy` / policy string. | HIGH |
| **No halt path** | Generation results are consumed without an `enforce_policy` / HTTP 451 halt branch. | MEDIUM |
| **No provenance / audit** | No `ComplianceAuditTrail`, DPE, or provenance chain wired to model outputs. | MEDIUM |
| **Policy lint** | Malformed policy grammar, `report-only` left on, grounding thresholds below a floor, untrusted sources allowed (`default-src parametric`). | LOW–HIGH |
| **Header conformance** | Endpoints that emit some but not all required `CRP-*` headers. | LOW |
| **Version drift** | Pinned `crprotocol` version below a configurable minimum. | LOW |

Scanning is **static** (AST + regex over Python/JS, plus parsing of `*.crp-policy`,
YAML/TOML config). No code execution, no network calls to model providers.

## Architecture

```
crp-scan/
  action.yml                 # composite action metadata
  entrypoint (python -m crp.scan)
        │
        ├── collectors/       # find LLM call sites, policy files, header emitters
        ├── rules/            # one module per check above
        ├── conformance/      # reuse tests/conformance vectors for policy/grammar
        └── reporters/
              ├── sarif.py     # → GitHub code-scanning (Security tab)
              ├── pr_comment.py# → annotations / review comment
              └── junit.py     # → CI summary
```

Implemented as a thin CLI subcommand (`crp scan`) inside the existing package, so the
Action is a small wrapper that `pip install crprotocol` then runs the CLI. This keeps
the logic versioned with the protocol and unit-testable outside CI.

## Action interface (`action.yml`)

```yaml
name: "CRP Scan"
description: "Scan a repository for CRP / AI-governance conformance."
inputs:
  paths:            { default: ".",            description: "Globs to scan." }
  fail-on:          { default: "HIGH",          description: "Min severity that fails the build (LOW|MEDIUM|HIGH|CRITICAL)." }
  min-grounding:    { default: "0.70",          description: "Required grounding floor for policy lint." }
  min-version:      { default: "3.0.0",         description: "Minimum crprotocol version." }
  report-only:      { default: "false",         description: "Annotate but never fail." }
  sarif-file:       { default: "crp-scan.sarif", description: "SARIF output path." }
outputs:
  findings-count:   { description: "Total findings." }
  highest-severity: { description: "Highest severity found." }
runs:
  using: "composite"
  steps:
    - uses: actions/setup-python@v5
      with: { python-version: "3.12" }
    - run: pip install "crprotocol[full]==${{ inputs.min-version }}"
      shell: bash
    - run: crp scan --paths "${{ inputs.paths }}" --fail-on "${{ inputs.fail-on }}" --sarif "${{ inputs.sarif-file }}"
      shell: bash
    - uses: github/codeql-action/upload-sarif@v3
      with: { sarif_file: "${{ inputs.sarif-file }}" }
```

## Consumer usage

```yaml
# .github/workflows/governance.yml
name: AI Governance
on: [pull_request]
jobs:
  crp-scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write   # for SARIF upload
      pull-requests: write      # for PR annotations
    steps:
      - uses: actions/checkout@v4
      - uses: crprotocol/crp-scan@v1
        with:
          fail-on: HIGH
          min-grounding: "0.75"
```

## Output

1. **PR annotations** — inline at each ungoverned call site / policy line.
2. **Security tab** — SARIF upload → code-scanning alerts with rule IDs
   (`CRP001`–`CRPnnn`), descriptions, and remediation snippets.
3. **Job summary** — a markdown table (findings by severity, conformance score).
4. **Exit code** — non-zero when any finding ≥ `fail-on` (unless `report-only`).

## Conformance score

A single 0–100 number = weighted pass rate across all enabled rules, surfaced as a
badge-able output so projects can display `CRP conformance: 92%`.

## Implementation phases (R5)

1. `crp scan` CLI skeleton + collectors (find call sites & policy files).
2. Rules: ungoverned-call, missing-policy, policy-lint (reuse conformance vectors).
3. SARIF reporter + PR annotations.
4. `action.yml` composite action + marketplace publish.
5. Self-test: run `crp-scan` against this repo's own `examples/` and demos.

## Open questions

- Marketplace listing name / org (`crp-scan` vs `crprotocol/scan`).
- JS/TS coverage depth in v1 (Python-first, JS best-effort).
- Whether to bundle a Docker action for hermetic runs vs. composite (composite chosen
  for speed; revisit if dependency install dominates runtime).
