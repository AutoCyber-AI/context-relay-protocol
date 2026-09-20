# Latent Bug Punch List — surfaced by the 2026-09 mypy zero-errors sweep

> During the repo-wide mypy cleanup (792 → 0 errors), the type checker exposed
> ~12 pre-existing runtime defects that were previously invisible: each raises at
> runtime but is swallowed by an `except` or fallback in the calling code.
> None were introduced by the sweep; each is marked with a `# type: ignore`
> (with reason) at its site. Triage before v6.1.1 publish.

| # | File:line | Defect | Runtime effect |
|---|-----------|--------|----------------|
| 1 | `crp/sdk/client.py` | Calls `self.config.compute_hash()`; real method is `get_config_hash()` | Always returns `""` — config hash never emitted |
| 2 | `crp/sdk/proxies_more.py` (×4) | `warm_store=` no-such-kwarg; `ConsentManager()` missing `session_id`; `ManifestLedger(session_id=...)` kwarg is `session_dir`; `StateEncryptor()` missing `session_key` | `TypeError` swallowed by fallback paths |
| 3 | `crp/comply/billing/metering.py:106` | `SubscriptionItem.create_usage_record` removed in stripe 15 | Usage metering dead on current stripe |
| 4 | `crp/comply/billing/webhook.py:80` | stripe stubs type `customer.metadata` attrs as `str`, hiding dict-like `.get` | Fragile against real payload shapes |
| 5 | `crp/comply/no_code.py:82,84` | `SafetyCoverageMap._capabilities` renamed to `capabilities` | Crashes when `cap is None` |
| 6 | `crp/core/app_profile.py:124` | `ContextSource(description=...)` — no such kwarg | `TypeError` swallowed |
| 7 | `crp/integrations/app_discovery.py` | `ContextSource` built with wrong kwargs incl. `origin="DECLARED"` | Latent `TypeError` |
| 8 | `crp/infrastructure.py` | `SQLiteBackend(path=...)`; real param is `db_path` | `TypeError` caught → returns `None` |
| 9 | `crp/state/cso.py:587` | `GoalState.completed_operations` removed in SPEC-030 rework | Stale attribute access |
| 10 | `crp/core/context_tools.py` | `MergeResult.facts` accessed via `.id` (should be `.fact.id`) | Always raises `AttributeError`, swallowed |
| 11 | `crp/scan/remediation.py` | `proposal.target_file` nonexistent field; `return pr_url` dict-vs-str | Remediation PR URL wrong |
| 12 | `crp/sdk/proxies_extra.py` (×2) | `crp.scan.github_app.CRPScanGitHubApp` and `crp.comply.gateway_client.ComplyGatewayClient` don't exist (names differ / module is functions-only) | ImportError caught; stubs always used |

## Round 2 — found by the coverage-test sweep (2026-09-20, tests-only sweep)

| # | File:line | Defect | Runtime effect |
|---|-----------|--------|----------------|
| 13 | `crp/cli/main.py` | `click.version_option(package_name="crp")` but the dist is `crprotocol` | `crp --version` raises RuntimeError |
| 14 | `crp/cli/main.py` (`safety.checkpoint`) | Declared defaults `"RISK_HIGH"`/`"HALT"` don't match enum values (`"risk >= HIGH"`/`"halt"`) | Defaults silently yield `CUSTOM_RULE`/`FALLBACK` |
| 15 | `crp/integrations/app_discovery.py:154` | `profile_from_llamaindex(query_engine=...)` passes invalid `ContextSource` kwargs | Always raises `TypeError` (see also #7) |
| 16 | `crp/cli/main.py` | `status`/`dispatch --json` report the orchestrator's internal session id, not the CLI session key | Confusing/wrong session ids in CLI JSON output |
| 17 | `crp/cli/main.py` (`scan-remediate`) | PR success path writes `/tmp/crp_remediation_pr_url` (POSIX-only) | Crashes on Windows after a successful `gh pr create` |
| 18 | feedback loop | Unknown-fact `boost` feedback silently returns 200 | No-op accepted as success |
| 19 | `crp/cli/sidecar.py` | 403 ownership branch unreachable over HTTP with single shared auth token (non-matching bearer gets 401 first) | Dead code path (unit-tested directly) |

## Environment/stub quirks (not bugs — annotated, no action)

- `crp/envelope/retrieval_integrity.py` — `math.exp2` is py3.11+; absent from py310 typeshed (runtime guards version).
- 7× `import requests` + `import yaml` — third-party libs without PEP 561 stubs.

## Suggested priority

1. #1 (config hash) and #9 (CSO stale attr) — protocol-visible correctness.
2. #5, #6, #7, #8, #10 — small kwarg/attr fixes, each a one-liner.
3. #3, #4 — verify against the pinned stripe version before the billing wave.
4. #2, #11, #12 — SDK surface; fix when the comply/scan wave lands (Wave 3).
