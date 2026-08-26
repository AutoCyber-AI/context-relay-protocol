# CRP SDK Hardening & Verification Report — 2026-08-26

> Honest done/not-done status for this session's work. No aspirational
> claims — every ✅ below has a corresponding live test run, regression
> suite pass, or reproducible artifact cited next to it. Anything not
> fully verified is marked 🔶 or ⬜, not rounded up to ✅.

## Scope

This session's work was triggered by one question: **does `crp.Client()`'s
"zero-config auto-detection" actually work, or is it marketing?** Answering
that honestly surfaced three real, previously-undiscovered bugs, which led
to a broader pass across templates, documentation, and demos. Below is the
full accounting, mapped to the original request list.

---

## 1. Bug fixes (verified via live tests + regression suite)

| Item | Status | Evidence |
|---|---|---|
| LM Studio never in `_auto_detect_provider()`'s resolution chain | ✅ FIXED | Direct provider-instantiation test confirms `OpenAIAdapter` + correct ctx=8192; live `crp.Client().dispatch()` end-to-end proof produced a real, non-empty answer with zero config, only LM Studio running |
| Repetition loop on trivial/short answers (continuation engine never terminated) | ✅ FIXED | Added raw-output repetition guard (`crp/continuation/manager.py`) + raised `gap_override_min_output_tokens` 16→48 (`crp/continuation/trigger.py`). 102/102 tests pass (`test_orchestrator_perf.py` + `test_phase5.py` + `test_production_hardening.py`). Live re-test: terminated correctly on window 1, no repetition, twice in a row |
| Opaque OpenAI provider error logging (`type(exc).__name__` only, no message) | ✅ FIXED | Both `logger.error()` call sites in `crp/providers/openai.py` now include `str(exc)`. The specific `BadRequestError` that motivated this did not reproduce on 3 subsequent runs — assessed as transient local resource contention, not a code bug |
| Silent-fallback-to-broken-`CustomProvider` in `crp/sdk/client.py` when no provider detected | ⬜ NOT FIXED | Known secondary risk, noted but not addressed this session — `_ensure_orchestrator()` still falls back to a stub `CustomProvider` returning `("", "stop")` on `ValueError` from auto-detection, rather than raising. Flagged as a follow-up |

## 2. Marketing / documentation accuracy

| Item | Status | Evidence |
|---|---|---|
| README claimed auto-detect only covers OpenAI/Anthropic/Ollama (LM Studio omitted) | ✅ FIXED | Updated Key Differentiators bullet, quickstart code comment, `.env` comment, and the Built-in Providers table in `README.md` |
| "`dispatch()` returns unmodified output, always" (Axiom 9) doesn't disclose the license watermark append | ✅ DISCLOSED (not removed) | `crp/core/dispatch_router.py` appends a `<!-- CRP™ | ELv2 | ... -->` comment by default (`CRP_DISABLE_WATERMARK=1` to opt out) — this is intentional IP-protection, not a bug, so the code is untouched. Added one honest sentence to README's Output Guarantee section |
| Same disclosure gap in `specification/02_CORE_PROTOCOL.md`, `crp/core/session.py` docstring, `schemas/quality-report.json` | ⬜ NOT DONE | Same wording issue exists in these 3 places; not updated this session — flagged for a follow-up spec-text audit |

## 3. `CHEATSHEET.md` comprehensive rewrite

| Item | Status | Evidence |
|---|---|---|
| Full `crp.SDKClient()` / `CRPClient` method inventory | ✅ DONE | New §4.1 table lists all 14 public methods (`.complete()`, `.stream()`, `.ingest()`, `.ask()`, `.tool()`, `.call_tool()`, `.dispatch_positioned()`, `.conversation()`, `.make_agent()`, `.derive_profile()`, `.configure()`, `.session()`, `.save_config()`/`.config_hash()`, `.reset()`/`.close()`) — read directly from `crp/sdk/client.py` source, not guessed |
| `crp.Client` vs `crp.SDKClient` confusion (previously undocumented — literally two different classes) | ✅ DOCUMENTED | New callout box in §3 — confirmed via `crp/__init__.py` source (`Client = CRPOrchestrator`; `SDKClient` lazy-loads `crp.sdk.client.CRPClient`) — a genuine, confirmed source-level naming wart, not fixed (would be a breaking API rename) but now clearly explained with a comparison table |
| Agentic loop / ecosystem explanation | ✅ DONE | New §0 with a Mermaid diagram of the actual request→intent→positioning→tool-call→checkpoint→verification→response flow |
| Ingestion from file / directory / URL / "anything" | ✅ DOCUMENTED HONESTLY | New §4.2 — confirmed via source (`crp/core/extraction_facade.py::ingest`) that CRP has **no built-in URL fetcher**: `client.ingest()` only reads local file/dir paths; URL/"anything" ingestion means "you fetch it, then hand CRP the text" via `client.orchestrator.ingest(text, source_label=...)`. All 3 ingestion snippets (file, dir, "URL") and the 3 visibility calls (`client.knowledge.location`, `client.storage.overview()`, `client.ckf.health()`) live-executed and verified against a real orchestrator, not guessed |
| Namespace proxies (`client.safety`, `.ckf`, `.audit`, etc. — ~25 of them) | ✅ DONE | New §4.3 table — every proxy read from `crp/sdk/proxies.py` source; the two example calls (`client.safety.control_plane().get_surface_map()`, `client.audit.verify()`) were corrected after live testing showed the first-drafted method names didn't exist (`get_surface_map()` needs `.control_plane()` first; `window_chain.verify()` doesn't exist — `client.audit.verify()` does) |
| "3 ways to declare tools" clarified with a decision guide | ✅ DONE | New table in §5.2 mapping situation → form (plain callable / dict-with-impl / `CapabilityDescriptor`) |
| Checkpoints made concrete (not abstract) | ✅ DONE | §5.6 rewritten as a numbered walkthrough of the exact mechanism, cross-referencing the real `security_analyst_agent.py` file and its exact run commands (including `CRP_DEMO_DENY=1`) |
| Elevator pitch on every major section, especially `AgentResponse` | ✅ DONE | Added to §0, §3, §4, §4.2, §4.3, §5, §5.2, §5.6, §5.8, §5.9 |

## 4. Templates & demos

| Item | Status | Evidence |
|---|---|---|
| Replace `research_assistant_agent.py`'s undocumented DuckDuckGo HTML scrape | ✅ DONE | Now uses Wikipedia's real, versioned, free, documented MediaWiki Search API (`https://www.mediawiki.org/wiki/API:Search`). Live-verified 3-turn run: real grounded, cited answers from real Wikipedia articles ("AI agent", "List of large language models", "Mistral AI") |
| Checkpoints made "viewable" via a real web interface (not just console) | ✅ DONE | New `examples/crp_demos/checkpoint_console.py` + `static/checkpoint.html` — a genuine web UI where the browser's Approve/Deny click POSTs to `/api/decide`, which unblocks a real `queue.Queue.get()` inside the agent's own execution thread. Live-verified BOTH paths via browser automation against LM Studio: **Approve** → real `TOOL_CALL_RESULT` + the tool's own `[ACTION]` print appears in the server log; **Deny** → `RUN_ERROR` event, no `[ACTION]` print at all |
| Live-verify streaming end-to-end | ✅ DONE | Proven as a side effect of the checkpoint console build — `agent.run_tel()` streamed a real, live, correctly-ordered AG-UI event sequence (RUN_STARTED → REASONING_CONTENT → TOOL_CALL_START/ARGS/END/RESULT → STATE_SNAPSHOT → RUN_FINISHED) to a real browser via SSE |
| Video-proof results captured as JSON | ✅ DONE | `examples/crp_demos/live_llm_vs_crp.py` now writes a structured `_video_proof.json` artifact (task, both arms' full output, governance metadata, word-count/operation-count summary) alongside its console output. `CRP_DEMO_REAL_SEARCH=1` swaps in the same Wikipedia-backed tools instead of synthetic mocks — live-verified: raw LLM emitted literal tool-call JSON and stopped (6 words, no governance); CRP agent produced a genuine 101-word grounded, cited answer with `risk=LOW, grounded=true, chain_valid=true` |

## 5. Not yet done this session

| Item | Status | Notes |
|---|---|---|
| PyPI fix release (6.0.1) | 🔶 PREPPED, NOT PUBLISHED | Version bumped, `CHANGELOG.md` updated, full suite re-run — publish step requires the user's own PyPI token typed directly into their terminal (never routed through chat), per `docs/PYPI_PUBLISH_CHECKLIST.md` |
| Silent-fallback-to-broken-`CustomProvider` fix in `crp/sdk/client.py` | ⬜ NOT FIXED | Should raise loudly instead of degrading to permanent empty output |
| Axiom 9 disclosure in `specification/`, `crp/core/session.py`, `schemas/quality-report.json` | ⬜ NOT DONE | Same wording gap as README, not yet propagated to the formal spec text |
| Full spec/reference consistency pass (AGENTS.md Wave 2 item) | 🔄 UNCHANGED | Not addressed this session — pre-existing item |
| `crp download-models` clean-machine verification | ⬜ NOT DONE | Pre-existing item, out of scope this session |

## 6. Full regression suite (after version bump to 6.0.1)

`pytest tests/ -q` (excluding `test_live_*.py`): **3232 passed, 2 skipped, 1 failed** — 210s.

The 1 failure (`test_phase7.py::test_ingest_updates_warm_state`) is a
**pre-existing, environment-flaky** test unrelated to this session's changes:
it depends on the `transformers` NER backend, which threw two *different*
errors across two separate runs on this machine (`Cannot copy out of meta
tensor` once, `cannot import name 'pipeline'` once) — a known Windows
torch/transformers instability (see repo memory), not a regression. It falls
back to spaCy correctly either way; it just extracts one fewer fact than the
test's fixed threshold on an unlucky run. `test_smoke.py::test_version` was
updated to expect `6.0.1` and passes.

## 7. Release build (6.0.1) — verified, publish step left to the user

| Item | Status | Evidence |
|---|---|---|
| Version bump + CHANGELOG | ✅ DONE | `crp/_version.py` -> `6.0.1`; `CHANGELOG.md` has a full `[6.0.1]` entry |
| **New packaging bug found + fixed**: sdist never included `site-docs/spec`/`site-docs/topics`, which the wheel's `force-include` depends on | ✅ FIXED | `pyproject.toml`'s sdist `include` list now covers both directories. Root cause: `hatch build` direct-from-source silently worked, but the correct/recommended `python -m build` (sdist-then-wheel round trip) failed with `FileNotFoundError: Forced include not found` — a real, previously-latent packaging bug, not introduced by this session's other changes |
| Build artifacts | ✅ BUILT + VERIFIED | `python -m build` succeeded: `dist/crprotocol-6.0.1-py3-none-any.whl` (438 files, confirmed contains `crp_mcp/spec_corpus/{spec,topics}`) and `dist/crprotocol-6.0.1.tar.gz`. Installed into a throwaway venv and confirmed `import crp; crp.__version__ == "6.0.1"` |
| **Actual PyPI upload** | ⛔ NOT DONE — BY DESIGN | Requires the user's own PyPI API token. Per security policy, secrets are never typed into chat or routed through the agent — the user must run the publish command themselves in their own terminal. See `docs/PYPI_PUBLISH_CHECKLIST.md` |

**To finish publishing**, run this yourself (token typed directly into your terminal, not via chat):

```bash
pip install twine   # already installed in this environment
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<your-pypi-api-token>
twine upload dist/crprotocol-6.0.1-*
```

If you pasted a token in chat earlier in this conversation, **rotate it now** on PyPI (Account Settings → API tokens) — a token that has appeared in plaintext chat should be treated as compromised regardless of whether it was actually used.

---

## How to reproduce the key claims above

```bash
# Auto-detect + repetition-fix proof (writes JSON to stdout)
python -c "import crp; c=crp.Client(); o,r=c.dispatch(system_prompt='You are a helpful assistant.', task_input='In one sentence, what is 12 * 7?'); print(o, r.quality_tier)"

# Wikipedia-search-backed research template
cd examples/templates && python research_assistant_agent.py "your topic"

# Live web checkpoint console (both Approve and Deny paths)
python examples/crp_demos/checkpoint_console.py    # open http://127.0.0.1:8782

# Raw-LLM-vs-CRP JSON proof (real search tools)
CRP_DEMO_REAL_SEARCH=1 python examples/crp_demos/live_llm_vs_crp.py   # writes _video_proof.json
```
