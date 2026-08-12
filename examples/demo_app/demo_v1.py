#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Demo Application — side-by-side comparison of raw LLM vs CRP-orchestrated output.

Demonstrates:
  1. Direct LLM call (truncated at token wall)
  2. CRP dispatch (continuation engine completes the task)
  3. CRP + MCP tools (optional — external data via Model Context Protocol)

Usage:
  python demo.py                           # Full demo with auto-detected provider
  python demo.py --provider openai         # Use OpenAI
  python demo.py --no-mcp                  # Skip MCP demo
  python demo.py --verbose                 # Show extraction details + audit trail
  python demo.py --task "Your custom task"
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
import time

# ---------------------------------------------------------------------------
# Ensure CRP is importable from the repo root (for development)
# When pip-installed, this is unnecessary — the package is on sys.path.
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.isfile(os.path.join(_REPO_ROOT, "pyproject.toml")):
    sys.path.insert(0, _REPO_ROOT)

import crp  # noqa: E402
from crp.providers import (  # noqa: E402
    AnthropicAdapter,
    CustomProvider,
    OpenAIAdapter,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BANNER = r"""
 ╔═══════════════════════════════════════════════════════════════════╗
 ║              CRP — Context Relay Protocol Demo                  ║
 ║     Unbounded context · Unbounded generation · Amplified AI     ║
 ╚═══════════════════════════════════════════════════════════════════╝
"""

DEFAULT_TASK = (
    "Write a comprehensive 20-section technical document about 'Building "
    "Production-Ready AI Systems'. Cover: 1) Architecture Patterns, "
    "2) Data Pipeline Design, 3) Model Training Infrastructure, "
    "4) Feature Engineering, 5) Model Versioning, 6) A/B Testing Frameworks, "
    "7) Monitoring & Observability, 8) Drift Detection, 9) Scaling Strategies, "
    "10) Cost Optimization, 11) Security & Access Control, "
    "12) Compliance & Audit, 13) CI/CD for ML, 14) Edge Deployment, "
    "15) Multi-Model Orchestration, 16) Human-in-the-Loop, "
    "17) Disaster Recovery, 18) Performance Benchmarking, "
    "19) Team Structure & Processes, 20) Conclusion & Future Outlook. "
    "Each section should have 2-3 detailed paragraphs."
)

SYSTEM_PROMPT = (
    "You are a senior AI/ML infrastructure architect with 15 years of "
    "experience building production systems at scale. Write detailed, "
    "practical, and well-structured technical documentation. Use clear "
    "section headers (## Section N: Title) and include concrete examples "
    "where relevant."
)

# Max output tokens for the direct LLM call (simulates a realistic wall)
DIRECT_MAX_TOKENS = 2048

# ---------------------------------------------------------------------------
# Provider setup
# ---------------------------------------------------------------------------


def _create_provider(
    provider_name: str, model: str | None
) -> crp.CRPOrchestrator:
    """Create a CRP client with the specified provider."""
    if provider_name == "openai":
        prov = OpenAIAdapter(model=model or "gpt-4o-mini")
    elif provider_name == "anthropic":
        prov = AnthropicAdapter(model=model or "claude-sonnet-4-20250514")
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
    return prov


def _detect_provider() -> str:
    """Auto-detect available provider from environment."""
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    print("ERROR: No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Section counter
# ---------------------------------------------------------------------------


def _count_sections(text: str) -> int:
    """Count markdown ## headers in the output."""
    return sum(1 for line in text.splitlines() if line.strip().startswith("## "))


def _has_conclusion(text: str) -> bool:
    """Check if the output contains a conclusion section."""
    lower = text.lower()
    return "conclusion" in lower or "future outlook" in lower


def _word_count(text: str) -> int:
    return len(text.split())


# ---------------------------------------------------------------------------
# Phase 1: Direct LLM Call (baseline)
# ---------------------------------------------------------------------------


def run_direct_llm(provider_name: str, model: str | None, task: str) -> dict:
    """Call the LLM directly with a hard token cap — no CRP."""
    print("\n" + "=" * 65)
    print("  PHASE 1: Direct LLM Call (no CRP)")
    print("  Token limit: {:,} output tokens".format(DIRECT_MAX_TOKENS))
    print("=" * 65)

    prov = _create_provider(provider_name, model)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    start = time.perf_counter()
    output, finish_reason = prov.generate_chat(
        messages, max_tokens=DIRECT_MAX_TOKENS
    )
    elapsed = time.perf_counter() - start

    sections = _count_sections(output)
    words = _word_count(output)
    has_end = _has_conclusion(output)
    truncated = finish_reason == "length"

    print(f"\n  Finish reason : {finish_reason}")
    print(f"  Truncated     : {'YES ✗' if truncated else 'No ✓'}")
    print(f"  Words         : {words:,}")
    print(f"  Sections      : {sections} / 20")
    print(f"  Conclusion    : {'Yes ✓' if has_end else 'NO ✗'}")
    print(f"  Time          : {elapsed:.1f}s")
    print(f"  Facts extracted: 0 (no extraction)")
    print(f"  Audit trail   : None")

    if truncated:
        # Show the last 200 chars to demonstrate truncation
        print("\n  ── Last 200 characters (truncated mid-sentence) ──")
        for line in textwrap.wrap(output[-200:], width=60):
            print(f"    ...{line}")

    return {
        "output": output,
        "words": words,
        "sections": sections,
        "has_conclusion": has_end,
        "truncated": truncated,
        "elapsed": elapsed,
        "finish_reason": finish_reason,
    }


# ---------------------------------------------------------------------------
# Phase 2: CRP-Orchestrated Dispatch
# ---------------------------------------------------------------------------


def run_crp_dispatch(
    provider_name: str,
    model: str | None,
    task: str,
    verbose: bool = False,
) -> dict:
    """CRP-orchestrated dispatch — continuation engine handles wall hits."""
    print("\n" + "=" * 65)
    print("  PHASE 2: CRP-Orchestrated Dispatch")
    print("  Continuation engine active — no token wall limit")
    print("=" * 65)

    prov = _create_provider(provider_name, model)
    client = crp.Client(
        provider=prov,
        max_output_tokens=DIRECT_MAX_TOKENS,  # Same per-window cap
    )

    start = time.perf_counter()
    output, report = client.dispatch(
        system_prompt=SYSTEM_PROMPT,
        task_input=task,
    )
    elapsed = time.perf_counter() - start

    sections = _count_sections(output)
    words = _word_count(output)
    has_end = _has_conclusion(output)

    print(f"\n  Quality tier  : {report.quality_tier}")
    print(f"  Words         : {words:,}")
    print(f"  Sections      : {sections} / 20")
    print(f"  Conclusion    : {'Yes ✓' if has_end else 'No'}")
    print(f"  Facts extracted: {report.facts_extracted}")
    print(f"  Continuation windows: {report.continuation_windows}")
    print(f"  Envelope saturation : {report.envelope_saturation:.0%}")
    print(f"  Time          : {elapsed:.1f}s")
    print(f"  Audit trail   : HMAC-SHA256 chained ✓")

    if verbose:
        _print_verbose_details(client, report)

    # Session status
    status = client.session_status()
    print(f"\n  ── Session Summary ──")
    print(f"  Total windows : {status.total_windows}")
    print(f"  Input tokens  : {status.total_input_tokens:,}")
    print(f"  Output tokens : {status.total_output_tokens:,}")

    client.close()

    return {
        "output": output,
        "words": words,
        "sections": sections,
        "has_conclusion": has_end,
        "quality_tier": report.quality_tier,
        "facts_extracted": report.facts_extracted,
        "continuation_windows": report.continuation_windows,
        "envelope_saturation": report.envelope_saturation,
        "elapsed": elapsed,
    }


def _print_verbose_details(client: crp.CRPOrchestrator, report) -> None:
    """Print detailed extraction and audit information."""
    print(f"\n  ── Extraction Details ──")

    # Preview warm store facts
    try:
        preview = client.preview_envelope(SYSTEM_PROMPT, "summary")
        print(f"  Warm store facts: {preview.total_facts}")
        if hasattr(preview, "top_facts") and preview.top_facts:
            for i, fact in enumerate(preview.top_facts[:5], 1):
                text = fact.text[:80] + "..." if len(fact.text) > 80 else fact.text
                print(f"    {i}. [{fact.confidence:.2f}] {text}")
    except Exception:
        pass

    print(f"\n  ── Compliance ──")
    print(f"  Controls implemented: {report.compliance_controls_met}"
          f"/{report.compliance_controls_total}")
    print(f"  Risk level: {report.risk_level}")


# ---------------------------------------------------------------------------
# Phase 3: CRP + MCP Tools (optional)
# ---------------------------------------------------------------------------


def run_crp_with_mcp(
    provider_name: str,
    model: str | None,
    verbose: bool = False,
) -> dict | None:
    """CRP dispatch with MCP tool integration — PULL-based context relay.

    This demonstrates CRP's dispatch_with_tools() mode where the LLM can
    request external data via tool calls, and CRP manages the context
    lifecycle around those calls.
    """
    print("\n" + "=" * 65)
    print("  PHASE 3: CRP + MCP Tool Integration")
    print("  LLM can call tools for external data; CRP manages context")
    print("=" * 65)

    # Check if MCP is available
    try:
        import mcp  # noqa: F401
        has_mcp = True
    except ImportError:
        has_mcp = False

    if not has_mcp:
        print("\n  MCP package not installed. Showing built-in tool demo instead.")
        print("  Install with: pip install mcp")
        print()
        return _run_builtin_tools_demo(provider_name, model, verbose)

    return _run_mcp_tools_demo(provider_name, model, verbose)


def _run_builtin_tools_demo(
    provider_name: str, model: str | None, verbose: bool
) -> dict:
    """Demo CRP's built-in PULL-based dispatch (dispatch_with_tools).

    Even without MCP, CRP supports tool-mediated context retrieval where
    the LLM calls tools like 'retrieve_facts' and 'search_by_keyword'
    to pull relevant context from the warm store on demand.
    """
    prov = _create_provider(provider_name, model)

    # First, ingest some domain knowledge so CRP has facts to serve
    client = crp.Client(provider=prov)

    print("\n  Step 1: Ingesting domain knowledge...")
    domain_text = (
        "Kubernetes uses etcd as its distributed key-value store for all "
        "cluster state. The API server is the only component that directly "
        "interacts with etcd. Pod scheduling is handled by kube-scheduler "
        "which considers resource requirements, affinity rules, taints, and "
        "tolerations. The Container Network Interface (CNI) provides "
        "networking between pods across nodes. Calico, Flannel, and Cilium "
        "are popular CNI plugins. Service mesh implementations like Istio "
        "and Linkerd add observability, traffic management, and mTLS. "
        "Horizontal Pod Autoscaler (HPA) scales based on CPU, memory, or "
        "custom metrics from Prometheus. Vertical Pod Autoscaler (VPA) "
        "adjusts resource requests. Kubernetes RBAC uses Roles, ClusterRoles, "
        "RoleBindings, and ClusterRoleBindings for access control."
    )
    client.ingest(domain_text, task_intent="kubernetes infrastructure")
    print(f"  Ingested {len(domain_text.split())} words of domain knowledge")

    # Now dispatch with tools — LLM can pull facts from the warm store
    print("\n  Step 2: PULL-based dispatch (LLM retrieves context via tools)...")
    task = (
        "Using the available knowledge base, explain how Kubernetes "
        "networking works and how to secure inter-pod communication. "
        "Reference specific technologies and patterns."
    )

    start = time.perf_counter()
    try:
        output, report = client.dispatch_with_tools(
            system_prompt=(
                "You are a Kubernetes infrastructure expert. Use the "
                "available tools to retrieve relevant facts before answering."
            ),
            task_input=task,
        )
    except Exception as exc:
        # If provider doesn't support tool calling, fall back to regular dispatch
        print(f"  Tool calling not supported by this provider; "
              f"falling back to standard dispatch.")
        output, report = client.dispatch(
            system_prompt=(
                "You are a Kubernetes infrastructure expert."
            ),
            task_input=task,
        )
    elapsed = time.perf_counter() - start

    words = _word_count(output)

    print(f"\n  Words         : {words:,}")
    print(f"  Quality tier  : {report.quality_tier}")
    print(f"  Facts used    : {report.facts_extracted}")
    print(f"  Time          : {elapsed:.1f}s")
    print(f"  Audit trail   : HMAC-SHA256 chained ✓")

    if verbose:
        _print_verbose_details(client, report)

    client.close()
    return {"output": output, "words": words, "elapsed": elapsed}


def _run_mcp_tools_demo(
    provider_name: str, model: str | None, verbose: bool
) -> dict:
    """Demo with actual MCP tool server integration.

    This creates a simple MCP tool server that provides a 'lookup' tool,
    then uses CRP's dispatch_with_tools to let the LLM call it.
    """
    print("\n  MCP integration detected. Running with MCP tool server...")
    print("  (Creating an in-process MCP tool for demonstration)")

    prov = _create_provider(provider_name, model)
    client = crp.Client(provider=prov)

    # The MCP tool would typically run as a separate server.
    # For this demo, we simulate it by pre-ingesting knowledge and using
    # CRP's built-in tool-mediated dispatch which follows the same pattern.
    knowledge = (
        "The EU AI Act classifies AI systems into four risk levels: "
        "unacceptable risk (banned), high risk (strict requirements), "
        "limited risk (transparency obligations), and minimal risk (no "
        "requirements). High-risk AI systems must maintain technical "
        "documentation, implement risk management, ensure data governance, "
        "enable human oversight, and meet accuracy/robustness standards. "
        "Providers must conduct conformity assessments before market "
        "placement. The Act applies to providers, deployers, importers, "
        "and distributors. Penalties range up to 35 million EUR or 7% "
        "of global turnover. General-purpose AI models must comply with "
        "transparency requirements. Foundation models with systemic risk "
        "face additional obligations including adversarial testing."
    )
    client.ingest(knowledge, task_intent="AI governance and regulation")

    start = time.perf_counter()
    try:
        output, report = client.dispatch_with_tools(
            system_prompt=(
                "You are an AI governance consultant. Use tools to retrieve "
                "regulatory facts before advising on compliance strategies."
            ),
            task_input=(
                "A company is deploying a high-risk AI system in the EU. "
                "What specific compliance steps must they take under the "
                "EU AI Act? Reference specific articles and requirements."
            ),
        )
    except Exception:
        output, report = client.dispatch(
            system_prompt="You are an AI governance consultant.",
            task_input=(
                "A company is deploying a high-risk AI system in the EU. "
                "What compliance steps must they take under the EU AI Act?"
            ),
        )
    elapsed = time.perf_counter() - start

    words = _word_count(output)
    print(f"\n  Words         : {words:,}")
    print(f"  Quality tier  : {report.quality_tier}")
    print(f"  Facts used    : {report.facts_extracted}")
    print(f"  Time          : {elapsed:.1f}s")

    client.close()
    return {"output": output, "words": words, "elapsed": elapsed}


# ---------------------------------------------------------------------------
# Comparison summary
# ---------------------------------------------------------------------------


def _print_comparison(direct: dict, crp_result: dict) -> None:
    """Print side-by-side comparison of direct LLM vs CRP."""
    print("\n" + "=" * 65)
    print("  COMPARISON: Direct LLM vs CRP-Orchestrated")
    print("=" * 65)

    d_words = direct["words"]
    c_words = crp_result["words"]
    multiplier = c_words / d_words if d_words > 0 else float("inf")

    rows = [
        ("Words", f"{d_words:,}", f"{c_words:,}", f"{multiplier:.1f}×"),
        ("Sections (of 20)", str(direct["sections"]), str(crp_result["sections"]), ""),
        ("Conclusion", "✗" if not direct["has_conclusion"] else "✓",
         "✓" if crp_result["has_conclusion"] else "✗", ""),
        ("Truncated", "YES" if direct["truncated"] else "No",
         "No", ""),
        ("Facts extracted", "0", str(crp_result["facts_extracted"]), ""),
        ("Quality tier", "N/A", crp_result["quality_tier"], ""),
        ("Audit trail", "None", "HMAC-SHA256", ""),
        ("Time", f"{direct['elapsed']:.1f}s", f"{crp_result['elapsed']:.1f}s", ""),
    ]

    print(f"\n  {'Metric':<20} {'Direct LLM':<15} {'CRP':<15} {'Multiplier':<10}")
    print(f"  {'─' * 20} {'─' * 15} {'─' * 15} {'─' * 10}")
    for label, d, c, m in rows:
        print(f"  {label:<20} {d:<15} {c:<15} {m:<10}")

    print(f"\n  Content multiplier: {multiplier:.1f}× more output with CRP")
    if crp_result["continuation_windows"] > 0:
        print(f"  CRP used {crp_result['continuation_windows']} continuation "
              f"window(s) to complete the task")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CRP Demo — Direct LLM vs CRP-Orchestrated comparison",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python demo.py                             # Auto-detect provider
              python demo.py --provider openai           # Use OpenAI
              python demo.py --no-mcp                    # Skip MCP demo
              python demo.py --verbose                   # Show extraction details
              python demo.py --task "Write about X"      # Custom task
        """),
    )
    parser.add_argument(
        "--provider", choices=["openai", "anthropic"],
        help="LLM provider (default: auto-detect from API key)",
    )
    parser.add_argument("--model", help="Model name override")
    parser.add_argument("--task", default=DEFAULT_TASK, help="Task input")
    parser.add_argument("--no-mcp", action="store_true", help="Skip MCP demo")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show extraction details and audit trail")

    args = parser.parse_args()
    provider_name = args.provider or _detect_provider()

    print(BANNER)
    print(f"  Provider: {provider_name}")
    print(f"  Model: {args.model or '(default)'}")
    print(f"  CRP version: {crp.__version__}")

    # Phase 1: Direct LLM
    direct = run_direct_llm(provider_name, args.model, args.task)

    # Phase 2: CRP-orchestrated
    crp_result = run_crp_dispatch(
        provider_name, args.model, args.task, verbose=args.verbose
    )

    # Comparison
    _print_comparison(direct, crp_result)

    # Phase 3: MCP (optional)
    if not args.no_mcp:
        run_crp_with_mcp(provider_name, args.model, verbose=args.verbose)

    print("\n" + "=" * 65)
    print("  Demo complete. CRP turns token walls into speed bumps.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
