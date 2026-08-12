# CRP — GitHub App Connection: Implementation Guide

**For:** the engineer implementing CRP Comply's secure GitHub repository connection
**Companion to:** SPEC-048 (the spec) — this is the build guide
**Goal:** let CRP Comply securely connect to public AND private GitHub repos,
scan them, and open remediation PRs — with least-privilege, short-lived
tokens, and instant revocation.

---

## 0. Why a GitHub App (not OAuth, not a PAT)

| Option | Verdict |
|--------|---------|
| **GitHub App** ✅ | per-repo, least-privilege, short-lived tokens, org-installable, revocable, acts as itself. THE choice. |
| OAuth app | acts as the user, broader scopes, user-tied. Avoid for repo access. |
| Personal Access Token | long-lived broad secret pasted by user. Never. |

A GitHub App is installed onto selected repos, mints short-lived (~1h)
installation tokens on demand, and is revocable by the user at any time.

---

## 1. Register the GitHub App (one-time, on github.com)

GitHub → Settings → Developer settings → GitHub Apps → **New GitHub App**.

**Identity**
- Name: `CRP Comply`
- Homepage URL: `https://comply.crprotocol.io`
- Description: "Finds and helps fix ungoverned AI calls; gathers code evidence for AI compliance."

**Callback / setup**
- Callback URL: `https://comply.crprotocol.io/api/github/callback`
- Setup URL (after install): `https://comply.crprotocol.io/api/github/installed`
- ✅ Redirect on update
- ✅ Request user authorization (OAuth) during installation — so you learn which CRP user installed it

**Webhook**
- ✅ Active
- Webhook URL: `https://comply.crprotocol.io/api/github/webhook`
- Webhook secret: generate a strong secret → store as `GITHUB_APP_WEBHOOK_SECRET`

**Permissions (LEAST PRIVILEGE — this is the security core)**
- Repository → **Contents: Read-only** (read code to scan)
- Repository → **Metadata: Read-only** (mandatory, automatic)
- Repository → **Pull requests: Read & write** — ONLY if you offer auto-PR remediation; otherwise omit
- Repository → **Commit statuses: Read & write** — optional, to post scan status on commits
- Do NOT request: Administration, Secrets, Actions write, Webhooks, org-wide write. None are needed.

**Subscribe to events** (so re-scans trigger on change)
- `push`
- `pull_request`
- `installation` / `installation_repositories` (so you learn add/remove of repos)

**Installation**
- Where can it be installed: **Any account** (so customers can install on their org/personal).

**On create, GitHub gives you:**
- **App ID** → `GITHUB_APP_ID`
- **Client ID** + **Client secret** → `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET`
- **Generate a private key** (.pem) → store in a secrets manager (NOT in code) → `GITHUB_APP_PRIVATE_KEY`
- The webhook secret you set → `GITHUB_APP_WEBHOOK_SECRET`

---

## 2. The Connection Flow (what the user experiences)

```
1. User on Connect Repo page clicks "Connect GitHub"
2. Redirect to: https://github.com/apps/crp-comply/installations/new
3. GitHub shows the install screen: user picks ALL or SELECT repos
   (public or private — their choice, per-repo)
4. GitHub redirects back to your Setup URL with ?installation_id=...&setup_action=install
5. Your backend records: installation_id ↔ this CRP tenant (Clerk org)
6. Done. You can now mint tokens for the selected repos on demand.
```

Private repos work identically — they appear in the install picker; whatever
the user selects is what you can access, nothing more.

---

## 3. Secrets & Storage (the security requirements)

Store in a secrets manager (cloud KMS / Vault), NOT in code or env files in the repo:
```
GITHUB_APP_ID                 # public-ish id
GITHUB_APP_CLIENT_ID
GITHUB_APP_CLIENT_SECRET      # secret
GITHUB_APP_PRIVATE_KEY        # the .pem — THE most sensitive; signs token requests
GITHUB_APP_WEBHOOK_SECRET     # verifies inbound webhooks
```

In your database, per tenant, store ONLY:
```
tenant_id (Clerk org)  ↔  installation_id   # a reference, NOT a token
connected_repos[]                            # which repos, last_scanned_at
```
NEVER store a long-lived access token. Tokens are minted per-use and discarded.

---

## 4. Minting a Short-Lived Token (Python)

```python
# crp/github/app.py
import os, time, jwt, requests   # pyjwt
from functools import lru_cache

APP_ID = os.environ["GITHUB_APP_ID"]
PRIVATE_KEY = get_secret("GITHUB_APP_PRIVATE_KEY")  # from your secrets manager

def _app_jwt() -> str:
    """A short (10-min) JWT signed with the app private key — authenticates AS the app."""
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 600, "iss": APP_ID}
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")

def installation_token(installation_id: str) -> str:
    """Mint a ~1h installation token scoped to that installation's repos."""
    r = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={"Authorization": f"Bearer {_app_jwt()}",
                 "Accept": "application/vnd.github+json"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]   # use immediately, do NOT persist

def list_repos(installation_id: str) -> list:
    tok = installation_token(installation_id)
    r = requests.get("https://api.github.com/installation/repositories",
                     headers={"Authorization": f"Bearer {tok}",
                              "Accept": "application/vnd.github+json"}, timeout=10)
    r.raise_for_status()
    return r.json()["repositories"]
```

You can optionally scope the token to specific repos / permissions in the
POST body (`repository_ids`, `permissions`) for even tighter least-privilege.

---

## 5. Cloning / Reading a Repo for Scanning (Python)

```python
# Read-only fetch for semantic scanning (SPEC-039). Transient — don't keep the code.
import tempfile, subprocess

def fetch_repo(installation_id: str, repo_full_name: str) -> str:
    tok = installation_token(installation_id)
    tmp = tempfile.mkdtemp(prefix="crp-scan-")
    url = f"https://x-access-token:{tok}@github.com/{repo_full_name}.git"
    subprocess.run(["git", "clone", "--depth", "1", url, tmp], check=True, timeout=120)
    return tmp   # scan it (SPEC-039), ingest derived graph into the per-tenant code-CKF,
                 # then DELETE tmp. Do not retain raw source unless the user opted in.
```

After scanning: ingest the *derived knowledge graph* (call sites, findings)
into the tenant-isolated code-CKF (SPEC-039), then delete the clone. The raw
code is not retained by default.

---

## 6. Opening a Remediation PR (Python, only if write granted)

```python
def open_remediation_pr(installation_id, repo_full_name, branch, base, title, body, changes):
    tok = installation_token(installation_id)
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    # 1. create a branch from base, 2. commit the changes (Contents API),
    # 3. open the PR (Pulls API). NEVER push to a protected/base branch directly.
    r = requests.post(f"https://api.github.com/repos/{repo_full_name}/pulls",
        headers=h, json={"title": title, "body": body, "head": branch, "base": base}, timeout=15)
    r.raise_for_status()
    return r.json()["html_url"]   # show this to the user: "PR #N opened"
```

Remediations are ALWAYS PRs to a dedicated branch, never direct commits,
never to protected branches (SPEC-036 §9).

---

## 7. Verifying Inbound Webhooks (Python)

```python
import hmac, hashlib, os
SECRET = get_secret("GITHUB_APP_WEBHOOK_SECRET").encode()

def verify_github_webhook(body: bytes, signature_header: str) -> bool:
    # header: "sha256=...."
    expected = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")
```

Handle events: `push`/`pull_request` → trigger a re-scan of that repo;
`installation_repositories` → update the tenant's connected_repos list;
`installation` deleted → mark the tenant disconnected, stop scanning.

---

## 8. Revocation & Transparency

- The user can uninstall the app from GitHub (Settings → Applications) OR
  disconnect from within Comply. On the `installation.deleted` webhook, mark
  the tenant disconnected and purge connected_repos + the code-CKF for those repos.
- Show the user, in Comply, a "Connected Repositories" view: which repos,
  what access, last scanned. (SPEC-048 §5.)
- Log every scan and PR to the audit chain (SPEC-011).

---

## 9. The No-Grant Alternative (always offer it)

For users who won't grant repo access: they run the `crp-scan` GitHub Action
in their own CI and upload the SARIF output to Comply (SPEC-042 §5.2). No
GitHub App, no repo access — Comply ingests findings from the uploaded file.
Anonymous/pre-signup scans are limited to this + public repos (SPEC-048 §7.2).

---

## 10. Checklist

```
[ ] Register CRP Comply GitHub App (read-only contents + metadata; PRs write only if auto-PR)
[ ] Store App ID, client id/secret, private key (.pem), webhook secret in secrets manager
[ ] Build: install flow → record installation_id ↔ tenant
[ ] Build: short-lived token minting (never persist tokens)
[ ] Build: transient clone → scan (SPEC-039) → ingest graph → delete clone
[ ] Build: remediation PR (dedicated branch only) — if offering auto-PR
[ ] Build: webhook verification + push/pull_request re-scan + installation events
[ ] Build: Connected Repositories view + disconnect + audit logging
[ ] Offer the SARIF-upload no-grant path
[ ] Enforce: private repos require auth; anonymous scans = public/SARIF only
```

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · crprotocol.io*
