# Publishing the CRP Scan GitHub Action to Marketplace

## Prerequisites

1. **Public repository** — GitHub Actions in the Marketplace must be from public repos
2. **Action metadata** — `action.yml` must be present in the repo root
3. **Branding** — `branding.icon` and `branding.color` in `action.yml`
4. **README** — Must document inputs, outputs, and usage examples

## Current State

The `crp-scan` repo already has:
- ✅ `action.yml` with branding, inputs, outputs
- ✅ `README.md` with usage examples
- ✅ Public repo at `AutoCyber-AI/crp-scan`

## Step-by-Step Publication

### 1. Verify action.yml

Ensure `crp-scan/action.yml` contains:

```yaml
name: 'CRP Scan'
author: 'AutoCyber AI'
description: 'AI governance scanner — finds ungoverned LLM calls and opens remediation PRs'
branding:
  icon: 'shield'
  color: 'purple'
inputs:
  paths:
    description: 'Comma-separated paths to scan'
    required: false
    default: '.'
  fail-on:
    description: 'Minimum severity to fail (LOW, MEDIUM, HIGH, CRITICAL)'
    required: false
    default: 'HIGH'
  min-version:
    description: 'Minimum crprotocol version to enforce'
    required: false
    default: ''
outputs:
  findings:
    description: 'JSON array of scan findings'
runs:
  using: 'composite'
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: '3.13'
    - run: pip install crprotocol[cli]
      shell: bash
    - run: python -m crp scan --format json --paths "${{ inputs.paths }}" --fail-on "${{ inputs.fail-on }}"
      shell: bash
      id: scan
```

### 2. Create a Release

1. Go to https://github.com/AutoCyber-AI/crp-scan/releases
2. Click **"Draft a new release"**
3. Choose **"Publish to Marketplace"** (not just a regular release)
4. Tag: `v1.0.0` (or `v0.1.0` for first release)
5. Title: `CRP Scan v1.0.0`
6. Description: Copy from README.md usage section
7. Check **"Publish this Action to the GitHub Marketplace"**
8. Click **"Publish release"**

### 3. Verify on Marketplace

- Visit https://github.com/marketplace?type=actions
- Search for "CRP Scan"
- Should appear with shield icon and purple branding

### 4. Versioning Strategy

| Tag | Purpose |
|-----|---------|
| `v1` | Major version — users pin to this for auto-updates |
| `v1.0.0` | Exact release |
| `v1.0.1` | Patch fix |

After each release, update the major tag:

```bash
git tag -fa v1 -m "Update v1 tag"
git push origin v1 --force
```

### 5. Usage in Workflows

Users will reference the action as:

```yaml
- uses: AutoCyber-AI/crp-scan@v1
  with:
    paths: 'src/'
    fail-on: 'HIGH'
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Action not found in Marketplace" | Ensure repo is public and release checkbox is ticked |
| "Invalid branding" | Use approved icon names from GitHub docs |
| "README too short" | Add inputs, outputs, and at least one full workflow example |
| "Composite action fails" | Ensure all steps have `shell: bash` |

## Post-Publication Checklist

- [ ] Action appears in GitHub Marketplace search
- [ ] Test workflow in a public repo works
- [ ] Badge added to crp-scan README
- [ ] Documented in crprotocol.io site
