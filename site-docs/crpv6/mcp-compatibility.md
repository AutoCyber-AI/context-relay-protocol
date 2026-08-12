# CRPv6 — MCP Compatibility

CRPv6 is designed to complement the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). MCP standardizes how LLMs discover and call tools; CRP standardizes how agents are positioned on the right task with the right context. The two are complementary.

## CRP as an MCP server

CRP can expose its capabilities as an MCP server so any MCP client (Claude Desktop, Cursor, Windsurf, etc.) can:

- Query the Contextual Knowledge Fabric (CKF).
- Run governed tool calls through the CRP capability router.
- Retrieve facts, audit trails, and provenance evidence.

### Planned server capabilities

| Capability | MCP tool name | What it does |
|---|---|---|
| Knowledge query | `crp_query_knowledge` | Semantic + graph search over CKF |
| Tool execution | `crp_execute_capability` | Run a CRP capability with policy enforcement |
| Audit export | `crp_export_audit` | Return HMAC-signed audit events |
| Provenance check | `crp_check_provenance` | Verify claim-to-source attribution |

### Implementation target

- Directory: `crp/mcp/` (new)
- Transport: stdio and SSE
- Mapping: `ToolCapabilityFabric` → MCP tool definitions; `CapabilityExecutor` → MCP tool calls

## CRP as an MCP client

CRP agents can consume any MCP server. This means a `crp.Agent` can use:

- Filesystem servers
- Database servers
- Web search servers
- GitHub servers
- Any custom MCP tool

### Planned adapter

- File: `crp/tools/adapters.py` extended with `MCPAdapter`
- Behavior: discover tools from MCP server, convert schemas to CRP `ToolSpec`, route calls through policy + audit

## Why this matters

MCP solves tool *access*. CRP solves tool *context* — what the agent knows, what it should do next, and how to prove it was safe. Together they let a small local model use a universe of tools without drowning in schemas.

## TODO

| # | Task | Where |
|---|------|-------|
| D1 | Implement MCP server | `crp/mcp/` |
| D2 | Implement MCP client adapter | `crp/tools/adapters.py` |
| D3 | Example: CRP agent using filesystem + web MCP servers | `examples/mcp/` |
| D4 | Document authentication and sandboxing | This page |
