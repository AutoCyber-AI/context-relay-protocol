# CRP Agent Console — CDN Deployment Guide

> **Why this is separate from the Python package:**  
> The agent console is a **frontend asset** (HTML/CSS/JS/TS). The `crprotocol` wheel is a **Python library**.  
> Bundling a Node/Vite build inside the wheel would force every `pip install crprotocol` user to download megabytes of JS they may never use, and it would break the zero-dependency core promise.  
> Therefore the console ships as **two independent artifacts**:
> 1. An embedded, self-contained HTML fallback in `crp/frontend/console.py` — works with zero Node.
> 2. A buildable TypeScript/Vite package in `frontend/agent-console/` — used when you want the richer, CDN-hostable console.

---

## 1. What the console does

The CRP Agent Console consumes the AG-UI + CRP governance event stream from `agent.run_tel()` and renders:

- **Chat panel** — user/agent messages with streaming tokens.
- **Narrative tab** — a readable chain-of-thought (intent → operations → tool calls → safety scans → verification).
- **Governance tab** — cards and logs for risk, grounding, quality tier, confidence, sources.
- **Provenance tab** — visual HMAC chain link-by-link.
- **Events tab** — raw AG-UI/CRP event stream.

It is model-agnostic and provider-agnostic — any agent that emits the standard TEL stream can render in it.

---

## 2. Local build (Node / npm)

### Prerequisites

- Node.js 18+ and npm 9+ (verified on Node v24 / npm 11).
- The CRP Python package installed (for the SSE backend).

### Build the console

```bash
cd frontend/agent-console
npm install
npm run build
```

Output lands in:

```text
frontend/agent-console/dist/
├── index.html
└── assets/
    ├── index-<hash>.js
    ├── index-<hash>.css
    └── ...
```

The `crp/frontend/console.py` `mount_fastapi()` helper will automatically serve this built bundle if it exists at either:

- `crp/frontend/static/` (development copy), or
- `frontend/agent-console/dist/` (canonical Vite output).

If neither exists, it falls back to the inline HTML console.

### Development server

```bash
cd frontend/agent-console
npm run dev
```

Vite serves the console at `http://localhost:5173`.  You will still need a CRP FastAPI backend running elsewhere that exposes `/v1/tel/stream`.

---

## 3. Self-hosted / CDN deployment

### Option A — Serve from the Python process (simplest)

After `npm run build`, copy the built files to `crp/frontend/static/`:

```bash
cp -r frontend/agent-console/dist/. crp/frontend/static/
```

Then in your FastAPI app:

```python
from fastapi import FastAPI
from crp.frontend.console import mount_fastapi

app = FastAPI()
mount_fastapi(app, path="/crp/console", stream_path="/v1/tel/stream")
```

Visit `http://localhost:8000/crp/console`.

### Option B — Static CDN (S3 / R2 / CloudFront)

1. Build once:

   ```bash
   cd frontend/agent-console
   npm run build
   ```

2. Upload `dist/` to your CDN bucket, preserving the directory structure:

   ```bash
   aws s3 sync dist/ s3://your-crp-cdn/agent-console/v6.1.1/ \
     --cache-control "public, max-age=31536000, immutable"
   ```

3. Serve a tiny shim from your Gateway that injects the stream URL:

   ```python
   from fastapi import FastAPI
   from fastapi.responses import HTMLResponse

   app = FastAPI()
   CDN_BASE = "https://cdn.example.com/agent-console/v6.1.1"
   STREAM_URL = "https://gateway.example.com/v1/tel/stream"

   @app.get("/crp/console")
   def console():
       return HTMLResponse(f"""<!doctype html>
   <html>
     <head>
       <script>
         window.CRP_STREAM_URL = "{STREAM_URL}";
       </script>
     </head>
     <body>
       <script type="module" src="{CDN_BASE}/assets/index-XXXX.js"></script>
       <link rel="stylesheet" href="{CDN_BASE}/assets/index-XXXX.css">
       <div id="app"></div>
     </body>
   </html>""")
   ```

   > In production, read the hashed asset names from `dist/assets/` or use a build that outputs predictable names.

### Option C — Railway / Gateway-hosted

For Railway or similar PaaS:

1. Add a GitHub Actions job to build and upload `dist/` to your CDN on every tag.
2. Or add a pre-deploy step in your Railway service:

   ```bash
   cd frontend/agent-console && npm ci && npm run build && cp -r dist/* ../crp/frontend/static/
   ```

3. Expose `/crp/console` via `mount_fastapi()` in your Gateway service.

### Option D — GitHub-connected auto-deploy (Cloudflare Pages) ✨ RECOMMENDED

Instead of manual uploads, connect the Pages project to the GitHub repo: every push to
`main` rebuilds and redeploys the console automatically. The repo can stay **private** —
Cloudflare Pages builds private repos (the Cloudflare Pages GitHub app gets read access).

**One-time setup (≈10 minutes, dashboard clicks):**

1. Push the repo so `frontend/agent-console/` (source, `package-lock.json`, `.nvmrc`) is on
   GitHub. No build output needs to be committed — Pages builds from source.
2. Cloudflare dashboard → **Workers & Pages** → your `crp-console` project →
   **Settings → Builds & deployments** → **Connect to Git**.
   (If you prefer a clean start: **Create → Pages → Connect to Git** instead.)
3. GitHub authorization: when prompted, grant the **Cloudflare Pages** app access to the
   org/user that owns the repo, then select `context-relay-protocol`.
4. Build settings:
   | Setting | Value |
   |---|---|
   | Production branch | `main` |
   | Root directory | `frontend/agent-console` |
   | Framework preset | Vite (auto-detected) |
   | Build command | `npm run build` |
   | Output directory | `dist` |
5. Save. Cloudflare runs `npm ci` automatically (lockfile present) and uses Node 20 via
   `.nvmrc`. The existing custom domain (`console.crprotocol.io`) carries over.
6. Optional: under the same settings, disable **Preview deployments** if you don't want PR
   builds for a private repo.

From then on: merge to `main` → console live in ~1 minute, hashed assets and all. The
`dist/cdn/` manual packaging remains useful only for hosting the bundle outside Cloudflare.

---

## 4. Security checklist

- Serve the console over HTTPS.
- Bind the SSE stream to the authenticated Clerk session; reject cross-session `session_id` values.
- Use a strict Content-Security-Policy:

  ```text
  default-src 'self';
  script-src 'self' https://cdn.example.com;
  style-src 'self' 'unsafe-inline';
  connect-src 'self' https://gateway.example.com;
  ```

- Escape all tool-output text before rendering; never `eval()` agent-produced code.
- Do not log or expose the PyPI token, API keys, or provider credentials in the frontend.

---

## 5. Why Node / npm is the right tool here

- **Type safety** — TypeScript catches event-schema mismatches between the AG-UI stream and the UI.
- **Bundle optimisation** — Vite tree-shakes and hashes assets for long-term CDN caching.
- **CSS scoping** — Vite scopes CSS modules and supports light/dark mode without global conflicts.
- **Ecosystem** — npm gives us linting, audit, and a path to add React/Vue later if needed, while staying lightweight today.
- **Separation of concerns** — the Python wheel stays focused on the protocol; the frontend is a buildable, versioned asset.

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Console shows inline fallback instead of built bundle | `index.html` not found in `crp/frontend/static/` or `frontend/agent-console/dist/` | Run `npm run build` in `frontend/agent-console/` |
| Assets 404 | Hashed asset paths mismatch the served URL | Make sure assets are mounted under the same path prefix as `index.html`, or use a CDN shim |
| Stream never connects | Wrong `CRP_STREAM_URL` or CORS | Check the `stream_url` passed to `mount_fastapi()` and browser dev-tools Network tab |
| Blank page after CDN deploy | Browser cached old `index.html` | Set `Cache-Control: no-cache` on `index.html` and long cache on hashed assets |

---

## 7. Files involved

| Path | Purpose |
|------|---------|
| `frontend/agent-console/package.json` | npm manifest and build scripts |
| `frontend/agent-console/vite.config.ts` | Vite build configuration |
| `frontend/agent-console/src/main.ts` | Entry point |
| `frontend/agent-console/src/console.ts` | Console UI class |
| `frontend/agent-console/src/narrative.ts` | Event-stream → chain-of-thought |
| `frontend/agent-console/src/events.ts` | AG-UI + CRP event types |
| `frontend/agent-console/src/style.css` | Console styles |
| `crp/frontend/console.py` | Python fallback + FastAPI mount helper |
