# CRPv6 — Coding Agent Compatibility

CRPv6 is built to power coding agents: agents that read, understand, modify, and reason about codebases. This requires more than text chunking — it requires a structured understanding of code.

## What a coding agent needs

| Need | CRP capability | Status |
|---|---|---|
| Ingest large repositories | Structure-aware extraction + CKF | ✅ Implemented |
| Track symbols across files | Graph-structured facts | ✅ Implemented |
| Reason about dependencies | CKF graph walk + community summaries | ✅ Implemented |
| Edit code safely | Tool Capability Fabric + policy | ✅ Implemented |
| Verify edits compile/run | Verification Relay + Python/Z3 verifiers | ✅ Implemented |
| Explain what changed | Transparency Emission Layer (AG-UI) | ✅ Implemented |
| IDE integration | MCP server + LSP-like queries | ⬜ TODO |

## How CRP models a codebase

1. **Ingest** — parse files into AST-aware chunks.
2. **Extract** — pull out functions, classes, imports, calls, types, docstrings.
3. **Relate** — build a fact graph: `def A` calls `def B`, `class C` imports `module D`.
4. **Query** — answer "where is X used?", "what breaks if I change Y?", "summarize this module".
5. **Act** — generate edits through capabilities, verify with tests/linter, update CKF.

## Key components to build

| Component | Purpose | Where |
|---|---|---|
| AST-aware ingestion | Parse Python/JS/TS/Java/Go/Rust into facts | `crp/scan/semantic_ingestion.py` |
| Symbol graph | Cross-reference definitions and usages | `crp/ckf/graph_edges.py` extended |
| Code diff verifier | Check that edits compile and tests pass | `crp/vr/exec_verifier.py` |
| GitHub remediation flow | Open PRs with proposed changes | `crp/scan/github_app.py` |
| IDE/MCP bridge | Let Cursor/Copilot use CRP memory | `crp/mcp/` + this page |

## TODO

| # | Task | Where |
|---|------|-------|
| D3.1 | Extend semantic ingestion for Python, TypeScript, Go, Rust | `crp/scan/semantic_ingestion.py` |
| D3.2 | Build symbol-level CKF facts | `crp/ckf/` |
| D3.3 | Add code-specific agent template | `crp/agent_sdk/agent.py` |
| D3.4 | Integrate with `crp-scan` GitHub App for auto-remediation PRs | `crp/scan/github_app.py` |
| D3.5 | Publish MCP server for IDE integration | `crp/mcp/` |

## Example target flow

```python
import crp

agent = crp.Agent(
    model="local/qwen2.5-coder-7b",
    tools=[crp.tools.builtins.read_file, crp.tools.builtins.run_tests],
    policy=crp.agent_sdk.policy.Policy.strict(),
)

result = agent.run(
    "Refactor auth.py to use dependency injection and make sure all tests still pass."
)

print(result.answer)
print(result.sources)  # files read, tests run
print(result.crp.risk)
```
