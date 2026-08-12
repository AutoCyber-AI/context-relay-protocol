# CRP — GitHub Repository Connectivity: Production-Ready Solution

**For:** the developer fixing & completing GitHub connection in CRP Comply (and adding it to Scan)
**From:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd
**Problem being solved:** "I click Connect, install the app, grant repos, get redirected back —
but there's NOTHING there. No saved repo, no connection."
**Status:** this is the complete, working flow with the bug fix called out.

---

## 1. THE BUG (why nothing is there after redirect)

Your flow today does steps 1–4 but is missing step 5 — the backend never **persists the
installation and links it to the logged-in user**. So GitHub installs fine, but your app
forgets it instantly.

```
1. user clicks "Connect to repo"                              ✓ working
2. installs the CRP Comply GitHub App                         ✓ working
3. grants repo permissions                                    ✓ working
4. GitHub redirects back with ?installation_id=...            ✓ happening
5. BACKEND reads installation_id, links it to the Clerk user, ✗ MISSING  <-- the bug
   stores (installation_id, clerk_user/org, repos) in the DB
6. dashboard queries "my connected repos" -> shows them       ✗ returns empty (because 5 never ran)
```

**The fix is to build step 5.** Everything below is how.

---

## 2. THE TWO THINGS GITHUB GIVES YOU (and the confusion to avoid)

A GitHub App install produces an **installation_id** (which repos the app can touch).
GitHub App user-authorization (OAuth) produces a **user identity** (who installed it).
You need BOTH, and you must connect them:

- **installation_id** → "the app can access repos X, Y for account Z"
- **the Clerk user/org** → "this CRP user is connecting"
- **YOU must store the link** between them. GitHub will NOT remember which of your users
  owns which installation — that mapping is your job.

The mechanism that carries "which CRP user is connecting" through the GitHub round-trip is
the **`state` parameter**.

---

## 3. THE CORRECT END-TO-END FLOW

```
[Frontend] user clicks "Connect GitHub"
   │  POST /api/v1/github/connect-start   (Clerk-authed)
   ▼
[Backend] create a signed, short-lived `state` token that encodes the
          clerk_user_id + clerk_org_id; store it (Redis, 10-min TTL);
          return the install URL:
          https://github.com/apps/crp-comply/installations/new?state=<token>
   │
   ▼
[GitHub] user picks repos, clicks Install
   │
   ▼  redirects to the App's Setup URL:
      https://comply.crprotocol.io/api/v1/github/setup?installation_id=NNN&setup_action=install&state=<token>
   ▼
[Backend] GET /api/v1/github/setup:
          1. validate `state` (signature + TTL) -> recover clerk_user/org
          2. read installation_id
          3. mint an installation token, list the repos it can access
          4. STORE: github_installations row (installation_id, clerk_org_id, account_login)
                    + github_repos rows (one per granted repo)
          5. redirect -> https://comply.crprotocol.io/app/repos?connected=1
   │
   ▼
[Frontend] /app/repos calls GET /api/v1/github/repos (Clerk-authed)
          -> backend returns the stored repos for THIS tenant -> RENDERED. ✓
```

---

## 4. THE DATABASE SCHEMA (the missing persistence)

```sql
CREATE TABLE github_installations (
    id                BIGSERIAL PRIMARY KEY,
    installation_id   BIGINT NOT NULL UNIQUE,        -- from GitHub
    clerk_org_id      TEXT,                           -- the linked tenant (org)
    clerk_user_id     TEXT,                           -- or the linked user (personal acct)
    account_login     TEXT NOT NULL,                  -- the GitHub account/org
    account_type      TEXT NOT NULL,                  -- 'User' | 'Organization'
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    suspended         BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX ix_install_org  ON github_installations(clerk_org_id);
CREATE INDEX ix_install_user ON github_installations(clerk_user_id);

CREATE TABLE github_repos (
    id                BIGSERIAL PRIMARY KEY,
    installation_id   BIGINT NOT NULL REFERENCES github_installations(installation_id) ON DELETE CASCADE,
    repo_id           BIGINT NOT NULL,               -- GitHub repo id
    full_name         TEXT NOT NULL,                 -- "owner/repo"
    private           BOOLEAN NOT NULL,
    last_scanned_at   TIMESTAMPTZ,
    UNIQUE(installation_id, repo_id)
);
CREATE INDEX ix_repos_install ON github_repos(installation_id);
```

**Never store an access token here.** Tokens are minted on demand (§6) and discarded.

---

## 5. THE BACKEND HANDLERS (Python / FastAPI — production-ready)

```python
# crp/github/routes.py
import os, time, json, hmac, hashlib, base64, secrets
import jwt, requests
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from .auth import current_clerk_identity   # your Clerk JWT dependency
from .db import db
from .redis import redis

router = APIRouter(prefix="/api/v1/github")

APP_ID        = os.environ["GITHUB_APP_ID"]
APP_SLUG      = "crp-comply"                            # the app's URL slug
PRIVATE_KEY   = os.environ["GITHUB_APP_PRIVATE_KEY"].replace("\\n", "\n")
WEBHOOK_SECRET= os.environ["GITHUB_APP_WEBHOOK_SECRET"].encode()
STATE_SECRET  = os.environ["GITHUB_STATE_SECRET"].encode()   # any 32-byte random
APP_BASE_URL  = os.environ["APP_BASE_URL"]               # https://comply.crprotocol.io

# ---------- helpers ----------
def _sign_state(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(STATE_SECRET, raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"

def _verify_state(state: str) -> dict:
    try:
        raw, sig = state.split(".")
        expect = hmac.new(STATE_SECRET, raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            raise ValueError("bad sig")
        payload = json.loads(base64.urlsafe_b64decode(raw))
        if payload["exp"] < time.time():
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(400, "invalid state")

def _app_jwt() -> str:
    now = int(time.time())
    return jwt.encode({"iat": now-60, "exp": now+600, "iss": APP_ID},
                      PRIVATE_KEY, algorithm="RS256")

def _installation_token(installation_id: int) -> str:
    r = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={"Authorization": f"Bearer {_app_jwt()}",
                 "Accept": "application/vnd.github+json"}, timeout=10)
    r.raise_for_status()
    return r.json()["token"]

# ---------- 1. start: build the install URL carrying WHO is connecting ----------
@router.post("/connect-start")
def connect_start(identity = Depends(current_clerk_identity)):
    state = _sign_state({
        "clerk_user_id": identity.user_id,
        "clerk_org_id":  identity.org_id,     # may be None for personal accounts
        "exp": time.time() + 600,             # 10 min
        "nonce": secrets.token_hex(8),
    })
    url = f"https://github.com/apps/{APP_SLUG}/installations/new?state={state}"
    return {"url": url}

# ---------- 2. setup callback: THE FIX — persist + link ----------
@router.get("/setup")
def github_setup(installation_id: int, setup_action: str = "", state: str = ""):
    payload = _verify_state(state)                       # recover who is connecting
    clerk_org_id  = payload.get("clerk_org_id")
    clerk_user_id = payload.get("clerk_user_id")

    # who/what is this installation on?
    meta = requests.get(
        f"https://api.github.com/app/installations/{installation_id}",
        headers={"Authorization": f"Bearer {_app_jwt()}",
                 "Accept": "application/vnd.github+json"}, timeout=10).json()
    account = meta.get("account", {})

    # upsert the installation, LINKED to the tenant
    db.execute("""
        INSERT INTO github_installations
            (installation_id, clerk_org_id, clerk_user_id, account_login, account_type)
        VALUES (:iid, :org, :usr, :login, :atype)
        ON CONFLICT (installation_id) DO UPDATE
          SET clerk_org_id=:org, clerk_user_id=:usr, suspended=false
    """, dict(iid=installation_id, org=clerk_org_id, usr=clerk_user_id,
              login=account.get("login"), atype=account.get("type")))

    # list and store the granted repos
    tok = _installation_token(installation_id)
    repos = requests.get("https://api.github.com/installation/repositories",
        headers={"Authorization": f"Bearer {tok}",
                 "Accept": "application/vnd.github+json"}, timeout=10).json().get("repositories", [])
    for r in repos:
        db.execute("""
            INSERT INTO github_repos (installation_id, repo_id, full_name, private)
            VALUES (:iid, :rid, :fn, :priv)
            ON CONFLICT (installation_id, repo_id) DO UPDATE SET full_name=:fn, private=:priv
        """, dict(iid=installation_id, rid=r["id"], fn=r["full_name"], priv=r["private"]))

    # redirect back to the app — now there will be repos to show
    return RedirectResponse(f"{APP_BASE_URL}/app/repos?connected=1")

# ---------- 3. list repos for the logged-in tenant (what the dashboard calls) ----------
@router.get("/repos")
def list_repos(identity = Depends(current_clerk_identity)):
    rows = db.fetch_all("""
        SELECT r.full_name, r.private, r.last_scanned_at, r.installation_id
        FROM github_repos r
        JOIN github_installations i ON i.installation_id = r.installation_id
        WHERE (i.clerk_org_id = :org AND :org IS NOT NULL)
           OR (i.clerk_user_id = :usr)
    """, dict(org=identity.org_id, usr=identity.user_id))
    return {"repos": [dict(x) for x in rows]}

# ---------- 4. disconnect ----------
@router.delete("/installations/{installation_id}")
def disconnect(installation_id: int, identity = Depends(current_clerk_identity)):
    # verify ownership first
    owns = db.fetch_one("""SELECT 1 FROM github_installations
        WHERE installation_id=:iid AND (clerk_org_id=:org OR clerk_user_id=:usr)""",
        dict(iid=installation_id, org=identity.org_id, usr=identity.user_id))
    if not owns: raise HTTPException(403, "not your installation")
    db.execute("DELETE FROM github_installations WHERE installation_id=:iid",
               dict(iid=installation_id))   # cascade drops repos
    return {"disconnected": True}

# ---------- 5. webhook: keep repo list fresh + handle uninstall ----------
@router.post("/webhook")
async def github_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    expect = "sha256=" + hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        raise HTTPException(400, "bad signature")
    event = request.headers.get("X-GitHub-Event")
    data = json.loads(body)

    if event == "installation" and data["action"] in ("deleted", "suspend"):
        db.execute("DELETE FROM github_installations WHERE installation_id=:iid",
                   dict(iid=data["installation"]["id"]))
    elif event == "installation_repositories":
        iid = data["installation"]["id"]
        for r in data.get("repositories_added", []):
            db.execute("""INSERT INTO github_repos (installation_id, repo_id, full_name, private)
                VALUES (:iid,:rid,:fn,:priv) ON CONFLICT DO NOTHING""",
                dict(iid=iid, rid=r["id"], fn=r["full_name"], priv=r.get("private", True)))
        for r in data.get("repositories_removed", []):
            db.execute("DELETE FROM github_repos WHERE installation_id=:iid AND repo_id=:rid",
                       dict(iid=iid, rid=r["id"]))
    return {"ok": True}
```

---

## 6. THE GITHUB APP CONFIG THAT MAKES THIS WORK

In the GitHub App settings (App ID 3971977):
- **Setup URL:** `https://comply.crprotocol.io/api/v1/github/setup`  ← MUST be set, this is where step 2 lands
- ✅ **Redirect on update** (so adding/removing repos re-hits setup)
- **Webhook URL:** `https://comply.crprotocol.io/api/v1/github/webhook`
- **Webhook secret:** = `GITHUB_APP_WEBHOOK_SECRET`
- **Permissions:** Contents read-only, Metadata read-only (+ Pull requests read/write only if auto-PR)
- **Events:** Push, Pull request (installation events arrive automatically)
- **Where installable:** Any account

> If your Setup URL was blank or pointed at a frontend page that didn't call the backend,
> that alone explains "nothing there." Set it to the backend `/setup` route above.

---

## 7. NEW RAILWAY VARS NEEDED
```
GITHUB_STATE_SECRET = <openssl rand -hex 32>   # signs the state token
APP_BASE_URL        = https://comply.crprotocol.io   (already added)
```
(You already have GITHUB_APP_ID, _PRIVATE_KEY, _WEBHOOK_SECRET, _CLIENT_ID, _CLIENT_SECRET.)

---

## 8. MINTING TOKENS FOR SCANNING (later use)
When scanning, call `_installation_token(installation_id)` for the tenant's installation,
use it to clone (`https://x-access-token:<tok>@github.com/owner/repo.git`), scan, delete.
Never persist the token. (Full scan flow in CRP-GITHUB-APP-GUIDE.md.)

---

## 9. TEST CHECKLIST
```
[ ] Setup URL in the GitHub App = the backend /api/v1/github/setup route
[ ] GITHUB_STATE_SECRET set in Railway
[ ] /connect-start returns an install URL containing ?state=
[ ] After install, /setup is hit with installation_id + state (check logs)
[ ] A row appears in github_installations linked to your clerk_user/org
[ ] Rows appear in github_repos
[ ] /app/repos shows the repos
[ ] Disconnect removes them; uninstalling from GitHub fires the webhook and clears them
```

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io*
