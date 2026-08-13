# CRPv6 Wave 2 Launch Package

> **Status:** Wave 2 verification complete — protocol demos run against live SLMs with real public APIs.  
> **Applies to:** `crprotocol >= 6.0.0`  
> **Last updated:** 2026-08-13  
> **Owner:** Agent B — Safety Surface, SDK, Config, Products  

---

## 1. What Wave 2 now delivers

Wave 2 of the CRPv6 implementation is **launch-ready for the open-source protocol**. This means the public repo, PyPI package, and LinkedIn campaign can proceed while Wave 3 (managed-cloud money-funnel products) continues in parallel.

| Deliverable | File | Proof |
|-------------|------|-------|
| Real-world API research agent | `examples/agents/real_world_research_agent.py` | Calls Open-Meteo, CoinGecko, Wikipedia live; runs against LM Studio |
| Raw LLM vs. CRPv6 real-API proof | `examples/crp_demos/live_real_world_api_proof.py` | Side-by-side terminal output with governance block |
| Final synthesis in positioned loop | `crp/stl/positioned.py` | Tool JSON payloads are turned into natural-language answers |
| Public demo & test runbook | `site-docs/crpv6/CRPv6_PUBLIC_DEMO_AND_TEST_GUIDE.md` | Copy-paste commands for PowerShell, CMD, and Git Bash |
| Video demo guide | `site-docs/crpv6/CRPv6_VIDEO_DEMO_GUIDE.md` | One-take script and scene breakdown |
| Updated site nav | `mkdocs.yml` | Demos section with video, public, and agent guides |

### ML-first foundation (Wave 1 remains valid)

- `AutoCyberAI/crp-intent-setfit` — 0.934 held-out accuracy
- `AutoCyberAI/crp-prm-deberta-v1` — AUC 0.793 advisory process-reward model
- `AutoCyberAI/crp-safety-deberta-v1` — 12/12 adversarial pass
- `crp download-models` CLI command exists for local retrieval

### Functional test gate

- Full non-live test suite: `3232 passed, 3 skipped` on Windows with `CRP_GLINER_DISABLED=1`
- Wave 2 critical tests pass after final-synthesis fix:
  - `tests/test_agent_sdk.py`
  - `tests/test_positioned.py`
  - `tests/test_smoke.py`
  - `tests/test_integration.py`

---

## 2. Before you run any public demo

### 2.1 Reinstall the local package in editable mode

A stale `crprotocol` wheel installed in `.venv/Lib/site-packages` can shadow the local source code. Always reinstall before demos or videos after any code change.

```powershell
# Windows
.venv\Scripts\pip install -e . --no-deps
```

```bash
# Git Bash / Linux / macOS
.venv/bin/pip install -e . --no-deps
```

Verify the active package points at the repo:

```powershell
python -c "import crp.stl.positioned as p; print(p.__file__)"
```

Expected: `C:\Users\User\Desktop\context-relay-protocol\crp\stl\positioned.py` (or your repo path).

### 2.2 Start LM Studio

1. Open LM Studio.
2. Load `meta-llama-3.1-8b-instruct` (or any 8B instruct model).
3. Start the local server on port `1234`.
4. Confirm the log shows:
   ```
   POST http://192.168.1.17:1234/v1/chat/completions
   ```

### 2.3 Set environment variables

```powershell
# PowerShell / CMD
set CRP_LMSTUDIO_URL=http://192.168.1.17:1234/v1
set CRP_LMSTUDIO_MODEL=meta-llama-3.1-8b-instruct
```

```bash
# Git Bash / Linux / macOS
export CRP_LMSTUDIO_URL=http://192.168.1.17:1234/v1
export CRP_LMSTUDIO_MODEL=meta-llama-3.1-8b-instruct
```

---

## 3. Run the flagship real-API demo

### 3.1 Agent SDK version

```powershell
python examples/agents/real_world_research_agent.py
```

Expected output (abridged):

```
Q: What is the current weather in Tokyo?
A: According to the data from open-meteo.com, the current weather in Tokyo is mild with a temperature of approximately 24.6 degrees Celsius...
Operations: retrieve
Risk: LOW | Grounded: True | Chain valid: True
Sources: 1

Q: What is the current Bitcoin price in USD?
A: According to the data from api.coingecko.com, the current price of Bitcoin in USD is $63,588.
...

Q: What does the Wikipedia article on Machine learning say?
A: According to the Wikipedia article on Machine Learning, this field of study in artificial intelligence...
...
```

### 3.2 Raw LLM vs. CRPv6 version (best for video)

```powershell
python examples/crp_demos/live_real_world_api_proof.py
```

This prints the raw LLM JSON tool request next to the CRPv6 natural-language answer + governance block.

### 3.3 Offline version (no SLM needed)

Both scripts fall back to a deterministic mock provider when `CRP_LMSTUDIO_URL` is not set. The tool calls still hit the live public APIs.

---

## 4. What the protocol emits (what to highlight on camera)

Every CRPv6 Agent run returns:

| Field | Meaning | Where |
|-------|---------|-------|
| `result.answer` | Natural-language answer | `A:` line in demo |
| `result.crp.risk` | Risk tier (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) | governance block |
| `result.crp.grounded` | `True` when backed by a tool observation | governance block |
| `result.crp.chain_valid` | `True` when the HMAC audit chain is intact | governance block |
| `result.operations` | STL operations used (`RETRIEVE`, `GENERATE`, etc.) | governance block |
| `result.sources` | Tool observations with capability_id, operation type, payload | governance block |

These values are **computed at runtime**. None are hardcoded in the demo script.

---

## 5. Wave 2 launch checklist

- [ ] `pip install -e . --no-deps` completed in the demo environment.
- [ ] LM Studio running with an 8B instruct model.
- [ ] `examples/agents/real_world_research_agent.py` runs and returns natural-language answers for all 3 questions.
- [ ] `examples/crp_demos/live_real_world_api_proof.py` runs and shows raw LLM JSON vs. CRPv6 prose + governance.
- [ ] `pytest tests/ -q --tb=short` passes.
- [ ] `mkdocs build --strict` passes.
- [ ] GitHub repo contribution controls are locked (CODEOWNERS + branch protection).
- [ ] PyPI token rotated (if previously exposed).
- [ ] Railway secrets rotated (if previously exposed).
- [ ] LinkedIn campaign draft reviewed (`docs/CRPv6_LINKEDIN_LAUNCH_CAMPAIGN.md`).

---

## 6. Video scene guide for real-API demo

Use `examples/crp_demos/live_real_world_api_proof.py` for a 90-second demo.

### Scene 1 — setup (10 sec)

- LM Studio with 8B model loaded.
- Terminal with `pip show crprotocol` version check.

> “This is a stock Meta Llama 3.1 8B running locally. No cloud provider. I’m going to ask it three real-world questions and show you the difference between prompting it directly and running it through CRPv6.”

### Scene 2 — weather (20 sec)

- Raw LLM returns `{"tool": "get_weather", ...}` but does not execute it.
- CRPv6 returns a natural sentence and cites `open-meteo.com`.

> “Raw prompt: the model asks for the weather tool. That’s it — it never calls it. CRPv6 calls the live Open-Meteo API and answers in plain English, with a grounded risk flag and the source in the governance block.”

### Scene 3 — Bitcoin price (20 sec)

- Raw LLM returns `{"tool": "get_crypto_price", ...}`
- CRPv6 returns the live USD price and cites `api.coingecko.com`.

### Scene 4 — Wikipedia summary (20 sec)

- Raw LLM returns `{"tool": "wikipedia_summary", ...}`
- CRPv6 retrieves the real Wikipedia extract and summarises it.

### Scene 5 — closing (20 sec)

Show the final banner:

```
All CRP results above use live public APIs and runtime governance.
No API keys required. No governance values are hardcoded.
```

> “Same 8B model. Same laptop. Three live public APIs. The raw model emits JSON and stops. CRPv6 executes the APIs, synthesises answers, and gives you risk, grounding, chain validity, operations, and sources — all computed at runtime.”

---

## 7. Common problems and fixes

| Problem | Cause | Fix |
|---------|-------|-----|
| Demo uses old code / no final synthesis | Stale `crprotocol` wheel in `.venv` | `pip install -e . --no-deps` |
| `Connection refused` | LM Studio not running or wrong URL | Start server and check `CRP_LMSTUDIO_URL` |
| `Model selected unknown capability` | Model confused operation name with tool id | Re-run; sampling varies; protocol still recovers |
| `No module named 'setfit'` | SetFit not installed | Harmless; CRP falls back to rule-based intent. Optional: `pip install setfit` |
| Answer is raw JSON | Final synthesis not active | Reinstall editable package; ensure local source is loaded |

---

## 8. What is still Wave 3 (post-protocol-launch)

Wave 3 is the managed-cloud revenue layer. It can be developed while the protocol launch campaign runs.

| Wave 3 item | Status | Repo |
|-------------|--------|------|
| Gateway production hardening | Not started | `crp/gateway/` or `AutoCyber-AI/crp-gateway` |
| Comply upgrade to Gateway consumer | Not started | `AutoCyber-AI/crp-comply` |
| Scan remediation + GitHub App | Not started | `AutoCyber-AI/crp-scan` |
| Stripe + Clerk webhook entitlement | Not started | `crp/monetisation/` |
| Redis/S3/Postgres defaults | Not started | infra docs |
| Self-serve Scan→Comply→Gateway funnel docs | Not started | site-docs |

---

## 9. Security reminders

- **PyPI token**: if a token was ever pasted into chat, rotate it at https://pypi.org/manage/account/token/ before publishing.
- **Railway secrets**: if live variables were printed, rotate DB credentials, Clerk secret, and Stripe webhook secret in Railway.
- **GitHub repo**: enable branch protection and require CODEOWNERS review before public launch.

---

## 10. Next actions for launch

1. Run the real-API demo once more on camera.
2. Record the video using this guide.
3. Publish the updated site (`mkdocs build --strict` then push `main`; GitHub Actions deploys).
4. Publish `crprotocol 6.0.0` to PyPI after rotating the token.
5. Execute the LinkedIn campaign from `docs/CRPv6_LINKEDIN_LAUNCH_CAMPAIGN.md`.
6. While the campaign runs, proceed with Wave 3 managed-cloud products.
