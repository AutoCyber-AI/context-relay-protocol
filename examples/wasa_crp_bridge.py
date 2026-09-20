# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
r"""CRP ↔ WASA AI MCP bridge example.

This example loads tools from the WASA AI MCP server (``wasa_ai/mcp/server.py``)
and makes them available to a ``crp.Agent``. CRP's positioning layer then
selects only the relevant WASA tools for each operation instead of flooding the
small model with all 138 tool schemas.

WASA's MCP server is started as a stdio subprocess. The bridge translates each
MCP ``Tool`` into a CRP ``CapabilityDescriptor`` with a wrapper that forwards
calls back to the running WASA server.

Prerequisites::

    * WASA AI must be installed at ``C:\\Users\\User\\Desktop\\wasa_ai-master``
      (adjust ``WASA_ROOT`` below if your path differs).
    * The ``mcp`` Python package must be installed (WASA already depends on it).

Usage::

    python examples/wasa_crp_bridge.py "run a quick nmap scan on 192.168.1.1"

If the WASA server cannot start, the script prints diagnostics and exits without
hanging.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import crp
from crp.providers.openai import OpenAIAdapter
from crp_mcp.connectors.mcp_to_crp import load_mcp_tools

WASA_ROOT = Path(os.environ.get("WASA_ROOT", r"C:\Users\User\Desktop\wasa_ai-master"))


def _build_wasa_command() -> list[str]:
    """Return a Python command that starts the WASA MCP server over stdio.

    WASA's ``wasa_ai/mcp/server.py`` does not have a ``__main__`` block; the
    supported entry point is ``python -m wasa_ai.main mcp``. Prefer WASA's
    own virtual-environment interpreter when it exists, because WASA pulls in
    heavy native dependencies (paramiko, cryptograpy, etc.) that may not be
    installed in the CRP environment.
    """
    wasa_venv_python = WASA_ROOT / "venv" / "Scripts" / "python.exe"
    python = str(wasa_venv_python) if wasa_venv_python.exists() else sys.executable
    return [python, "-m", "wasa_ai.main", "mcp"]


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} '<task>'")
        print(f"WASA root: {WASA_ROOT}")
        sys.exit(1)

    task = sys.argv[1]

    if not WASA_ROOT.exists():
        print(f"ERROR: WASA root not found: {WASA_ROOT}")
        print("Set WASA_ROOT to the correct path and retry.")
        sys.exit(1)

    # Ensure WASA is importable so its server can start.
    wasa_root_str = str(WASA_ROOT)
    sys.path.insert(0, wasa_root_str)
    os.environ["PYTHONPATH"] = wasa_root_str + os.pathsep + os.environ.get("PYTHONPATH", "")

    command = _build_wasa_command()
    print(f"Loading WASA MCP tools from: {' '.join(command)}")

    try:
        wasa_tools = load_mcp_tools(command=command)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to load WASA tools: {exc}")
        print("\nDiagnostics:")
        print(f"  Python: {sys.executable}")
        print(f"  WASA_ROOT: {WASA_ROOT}")
        print(f"  Command: {command}")
        print("\nMake sure WASA dependencies are installed and the server starts cleanly.")
        sys.exit(1)

    print(f"Loaded {len(wasa_tools)} WASA tools into CRP.")
    print("Examples:", ", ".join(t.get("capability_id", "unknown") for t in wasa_tools[:5]))

    model_id = os.environ.get("CRP_LMSTUDIO_MODEL", "local/meta-llama-3.1-8b-instruct")
    provider: crp.providers.LLMProvider | None = None
    if model_id.startswith("local/") or model_id.startswith("lm-studio/"):
        base_url = os.environ.get("CRP_LM_STUDIO_URL", "http://127.0.0.1:1234/v1")
        model_name = model_id.split("/", 1)[1] if "/" in model_id else model_id
        provider = OpenAIAdapter(model=model_name, base_url=base_url, api_key="not-needed")
        model_id = None

    agent = crp.Agent(
        model=model_id,
        provider=provider,
        tools=wasa_tools,
        system=(
            "You are a cautious security analyst. Only run non-destructive reconnaissance tools. "
            "Explain what you are doing before calling any tool."
        ),
        profile="capable-local",
        depth="standard",
        max_operations=6,
    )

    result = agent.run(task)
    print("\n--- CRP Agent result ---")
    print("Answer:", result.answer)
    print("Operations:", result.how_it_was_built)
    print("Sources:", len(result.sources))
    print("Risk:", result.crp.risk)
    print("Grounded:", result.crp.grounded)
    print("Chain valid:", result.crp.chain_valid)


if __name__ == "__main__":
    main()
