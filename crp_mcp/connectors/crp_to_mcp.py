# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Expose a CRP ``ToolCapabilityFabric`` as an MCP server.

This lets non-CRP agents (Claude Desktop, other MCP clients) call CRP-registered
tools through the standard Model Context Protocol. CRP remains the governance
layer; MCP becomes the transport.

Example::

    from crp_mcp.connectors.crp_to_mcp import serve_crp_tools
    from crp.tools.capability_fabric import ToolCapabilityFabric

    fabric = ToolCapabilityFabric()
    # ... register tools ...
    serve_crp_tools(fabric, transport="stdio")

The generated MCP server uses ``FastMCP`` and mirrors each
``CapabilityDescriptor`` as an MCP ``Tool`` with a JSON Schema input schema.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("crp_mcp.connectors.crp_to_mcp")


def _descriptor_to_mcp_tool(desc: Any) -> dict[str, Any]:
    """Convert a CRP CapabilityDescriptor to an MCP tool dict."""
    name = desc.capability_id
    description = desc.description or f"CRP tool {name}"
    input_schema = getattr(desc, "input_schema", None) or {"type": "object", "properties": {}}
    if "type" not in input_schema:
        input_schema = {"type": "object", **input_schema}
    return {
        "name": name,
        "description": description,
        "inputSchema": input_schema,
    }


def _build_mcp_app(fabric: Any) -> Any:
    """Return a FastMCP app wrapping the given CRP fabric."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("CRP Tool Capability Fabric")

    executor = fabric.executor if hasattr(fabric, "executor") else None
    if executor is None:
        # Some fabrics keep a reference; fall back to looking up from descriptor.
        pass

    for desc in fabric.all():
        tool_def = _descriptor_to_mcp_tool(desc)
        tool_name = tool_def["name"]

        @mcp.tool(name=tool_name, description=tool_def["description"])
        def _tool_handler(arguments: dict[str, Any], _name: str = tool_name) -> Any:
            """Forward an MCP tool call to the CRP executor."""
            if executor is None:
                raise RuntimeError("No CRP executor available for this fabric")
            result = executor.call(_name, arguments)
            # FastMCP can return a dict/string/list; keep it JSON-serialisable.
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return result

    return mcp


def serve_crp_tools(
    fabric: Any,
    *,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """Run an MCP server that exposes every tool in ``fabric``.

    Args:
        fabric: A ``ToolCapabilityFabric`` instance.
        transport: ``stdio`` or ``sse``.
        host: Bind host for SSE transport.
        port: Bind port for SSE transport.
    """
    mcp = _build_mcp_app(fabric)
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
    else:
        raise ValueError(f"Unsupported MCP transport: {transport}")
