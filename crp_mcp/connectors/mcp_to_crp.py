# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Import external MCP servers as CRP Tool Capability Fabric sources.

MCP (Model Context Protocol) exposes tools. CRP positions them. This bridge lets
a ``crp.Agent`` consume any MCP-compatible server without rewriting its tools.

Example — load a local MCP server via stdio::

    from crp_mcp.connectors.mcp_to_crp import load_mcp_tools

    tools = load_mcp_tools(command=["python", "-m", "wasa_ai.mcp.server"])
    agent = crp.Agent(model="local/llama3.1", tools=tools)

Example — load from a WASA HTTP endpoint::

    tools = load_mcp_tools(url="http://127.0.0.1:8080/sse")
    agent = crp.Agent(model="local/llama3.1", tools=tools)

The bridge translates each MCP ``Tool`` into a CRP ``CapabilityDescriptor`` plus
a wrapper callable that forwards calls back to the MCP server. The wrapper is
registered in the agent's ``CapabilityExecutor`` so the positioned loop can call
it like any native CRP tool.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger("crp_mcp.connectors.mcp_to_crp")


def _schema_to_json_schema(mcp_schema: dict[str, Any] | None) -> dict[str, Any]:
    """Normalise an MCP input schema to JSON Schema.

    MCP 2024-11-05 uses ``inputSchema`` which is already JSON Schema. Older
    servers may omit it; we fall back to an empty object schema.
    """
    if not mcp_schema:
        return {"type": "object", "properties": {}}
    if "type" not in mcp_schema:
        mcp_schema = {"type": "object", **mcp_schema}
    return mcp_schema


def _mcp_tool_to_crp_dict(tool: Any, caller: Any) -> dict[str, Any]:
    """Convert an MCP Tool object to a CRP tool dict with an ``impl`` wrapper."""
    tool_name = getattr(tool, "name", "unknown_tool")
    description = getattr(tool, "description", "") or ""
    input_schema = _schema_to_json_schema(getattr(tool, "inputSchema", None))

    async def _wrapper(**kwargs: Any) -> Any:
        """Forward a CRP tool call to the MCP server."""
        if asyncio.iscoroutinefunction(caller):
            return await caller(tool_name, kwargs)
        # Callers may be sync callables that return a coroutine (e.g. a lambda
        # wrapping an async helper). Await the result if it is a coroutine;
        # otherwise run the sync callable in the default executor.
        result = caller(tool_name, kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result

    # Expose a sync entry point for CapabilityExecutor. MCP stdio clients need
    # their own event loop; running them on the caller's loop risks deadlock, so
    # we always execute in a fresh short-lived thread pool unless no loop exists
    # at all (then asyncio.run is the cheapest path).
    def _sync_wrapper(**kwargs: Any) -> Any:
        def _run_coro() -> Any:
            return asyncio.run(_wrapper(**kwargs))

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return _run_coro()

        if not loop.is_running():
            return loop.run_until_complete(_wrapper(**kwargs))

        # We are inside a running event loop; offload to a worker thread so the
        # MCP client gets a clean loop and the caller still blocks for a result.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(_run_coro).result()

    _sync_wrapper.__name__ = tool_name
    _sync_wrapper.__doc__ = description

    return {
        "capability_id": tool_name,
        "description": description,
        "input_schema": input_schema,
        "output_schema": {"type": "object"},
        "impl": _sync_wrapper,
        "mcp_source": True,
    }


async def _list_tools_stdio(command: list[str]) -> list[Any]:
    """Connect to an MCP server over stdio and return its tool list."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=command[0], args=command[1:], env=os.environ.copy()
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.list_tools()
        return list(result.tools)


async def _call_tool_stdio(command: list[str], tool_name: str, arguments: dict[str, Any]) -> Any:
    """Call a single tool on an MCP server over stdio."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=command[0], args=command[1:], env=os.environ.copy()
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(tool_name, arguments=arguments)
        if result.isError:
            raise RuntimeError(f"MCP tool {tool_name} error: {result.content}")
        # Aggregate text content.
        texts = [
            c.text
            for c in result.content
            if getattr(c, "type", None) == "text"
        ]
        if len(texts) == 1:
            return texts[0]
        return texts or [c.model_dump() for c in result.content]


def load_mcp_tools(
    *,
    command: list[str] | None = None,
    url: str | None = None,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """Load tools from an MCP server and return CRP-compatible tool dicts.

    Args:
        command: Command to spawn an MCP server via stdio (e.g.
            ``["python", "-m", "wasa_ai.mcp.server"]``).
        url: URL of an SSE-based MCP server. Either ``command`` or ``url``
            must be provided, not both.
        timeout: Seconds to wait for the tool list.

    Returns:
        A list of dicts that can be passed directly to ``crp.Agent(tools=...)``.
    """
    if (command and url) or (not command and not url):
        raise ValueError("Provide exactly one of command= or url=")

    if command:
        tools = asyncio.run(_list_tools_stdio(command))
        return [
            _mcp_tool_to_crp_dict(t, lambda name, args: _call_tool_stdio(command, name, args))  # type: ignore[misc]
            for t in tools
        ]

    # SSE/HTTP path (not yet implemented; raise with guidance).
    raise NotImplementedError(
        "SSE MCP client is not yet implemented. Use command= to spawn a local server."
    )
