# CRP Demo Apps — Local LLM Governance

Browser-based applications that demonstrate the **Context Relay Protocol (CRP)**
governing a **real local LLM** end-to-end.

## �️ Live Checkpoint Console (new — CRPv6 Agent SDK)

`checkpoint_console.py` is a real, clickable web UI for CRP's human-in-the-loop
oversight gate (CHEATSHEET.md §5.6) — not a mockup. It runs the exact
`security_analyst_agent.py` scenario against a real local LLM, streams the
agent's live governance events (AG-UI + `crp.*`) over SSE, and when the model
tries to call the DESTRUCTIVE `quarantine_host` tool, the running agent
thread genuinely blocks on a `queue.Queue.get()` until you click Approve or
Deny in the browser.

```bash
python examples/crp_demos/checkpoint_console.py    # http://127.0.0.1:8782
```

Zero extra dependencies (stdlib `http.server` + `EventSource`, same
zero-dependency pattern as the v3 demos below).

## � Raw LLM vs. CRP — JSON proof capture

`live_llm_vs_crp.py` runs the identical task through a raw LLM call and
through `crp.Agent`, side by side, then writes a structured JSON artifact
(`_video_proof.json` by default) alongside the console transcript — for
anyone who wants the underlying evidence, not just a narrated screen
recording.

```bash
python examples/crp_demos/live_llm_vs_crp.py                      # synthetic weather/temp tools
CRP_DEMO_REAL_SEARCH=1 python examples/crp_demos/live_llm_vs_crp.py  # real Wikipedia Search API tools
```

The real-search mode reuses the exact `web_search`/`read_page` tools from
`examples/templates/research_assistant_agent.py` (Wikipedia's public,
documented Search API — no scraper, no key) so the contrast is genuine: the
raw LLM emits literal tool-call JSON and stops, while the CRP agent actually
retrieves and reads a real page and synthesises a grounded, cited answer.

## �🚀 CRP v4 Protocol Demo

The `v4/` directory contains a **single-page, comprehensive CRP v4 showcase** that
drives a local model through the real CRP v4 shared runtime:

- **OpenAI-compatible provider discovery** via LM Studio / Ollama / llama.cpp
- **SPEC-007 signed session tokens** (`crp_shared.session_token`)
- **Full `X-CRP-*` header namespace** (`crp_shared.crp_headers`)
- **HMAC-SHA256 audit chain** with per-session keys
- **Tamper detection / chain verification**
- **Context Knowledge Fabric (CKF)** fact extraction and recall
- **DPE-style risk scoring** (grounding, fabrication, completeness)
- **Policy enforcement** — halt on critical risk
- **Audit export** (NDJSON)

### Run the v4 demo

```bash
# From the repo root, with a local LLM running on http://127.0.0.1:1234
python -m examples.crp_demos.v4.server    # http://127.0.0.1:8774
```

To point at a different local endpoint:

```bash
LM_STUDIO_BASE_URL=http://192.168.0.6:1234/v1 python -m examples.crp_demos.v4.server
```

Then open **http://127.0.0.1:8774/**.

### Programmatic demo recording

```bash
cd video-production
npm run record:protocol      # records output/crp-protocol-v4-demo.webm
npm run convert:mp4          # converts all .webm recordings to .mp4
npm run deploy:demos         # copies videos to Gateway / Comply / company site
```

## Legacy CRP v3 demos

The files at the top level (`server.py`, `pipeline.py`, `static/`) are the
original CRP v3 demos. They are kept for reference but are superseded by the v4
demo above.

```bash
python -m examples.crp_demos.server          # http://127.0.0.1:8770
```

## Prerequisites

```bash
pip install -e .                    # install crp + crp_shared deps
# or, if working from the Gateway/Comply workspace:
pip install fastapi httpx uvicorn
```

Run a local LLM (recommended: **LM Studio**):
- Load a chat model, e.g. `meta-llama-3.1-8b-instruct`.
- Start its server (Developer tab → Start Server) → listens on `http://127.0.0.1:1234`.
- **Ollama** (`:11434`) and **llama.cpp** (`:8080`) are auto-detected too.
- Use `127.0.0.1`, not `localhost`.

The demos still run with no model loaded — detection, the HMAC chain, the CKF and
session tokens all work; only the generated replies will be empty.

## Files

- `v4/server.py` — FastAPI backend using `crp_shared` + LM Studio proxy.
- `v4/static/` — single-page React-style vanilla HTML/CSS/JS app.
- `server.py` — legacy stdlib `ThreadingHTTPServer` (CRP v3).
- `pipeline.py` — legacy CRP v3 governance brain.
- `static/` — legacy CRP v3 demo pages.
