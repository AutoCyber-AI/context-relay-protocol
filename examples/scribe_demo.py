#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Scribe — Long-form document generation example.

Demonstrates:
  1. Listing available templates
  2. Generating a document outline
  3. Generating a full multi-chapter document with progress

Requires an LLM provider (OPENAI_API_KEY or ANTHROPIC_API_KEY).

Run:
  python examples/scribe_demo.py --topic "AI Ethics in Healthcare"
  python examples/scribe_demo.py --template whitepaper --chapters 5
  python examples/scribe_demo.py --topic "Blockchain" --output-dir ./docs/
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure CRP is importable from the repo root
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.isfile(os.path.join(_REPO_ROOT, "pyproject.toml")):
    sys.path.insert(0, _REPO_ROOT)

from crp.products.scribe import CRPScribe  # noqa: E402


def _detect_provider() -> tuple[str, str]:
    """Auto-detect an LLM provider from environment variables."""
    if os.environ.get("OPENAI_API_KEY"):
        return "openai", os.environ.get("OPENAI_MODEL", "gpt-4o")
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    print("⚠  No LLM API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")
    print("   Generating outline only (no LLM required).")
    return "", ""


def main() -> None:
    parser = argparse.ArgumentParser(description="CRP Scribe — Document Generation Demo")
    parser.add_argument("--topic", default="AI Governance and the EU AI Act",
                        help="Document topic")
    parser.add_argument("--template", default="whitepaper",
                        help="Template name (whitepaper, technical_manual, guide, report, book)")
    parser.add_argument("--chapters", type=int, default=5,
                        help="Number of chapters")
    parser.add_argument("--output-dir", default=None,
                        help="Save generated document to this directory")
    parser.add_argument("--provider", default=None,
                        help="LLM provider: openai, anthropic, ollama, lmstudio")
    parser.add_argument("--model", default=None,
                        help="LLM model override")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  CRP Scribe — Unlimited Long-Form Document Generation")
    print("=" * 60)

    # ── 1. Available Templates ──────────────────────────────────
    print("\n━━━ 1. Available Templates ━━━\n")
    scribe_preview = CRPScribe(template=args.template)
    for name, desc in scribe_preview.available_templates.items():
        marker = " ◀ selected" if name == args.template else ""
        print(f"  📝 {name}: {desc}{marker}")

    # ── 2. Outline Generation ───────────────────────────────────
    print(f"\n━━━ 2. Outline for \"{args.topic}\" ━━━\n")
    scribe_for_outline = CRPScribe(template=args.template)
    outline = scribe_for_outline.generate_outline(
        topic=args.topic,
        chapters=args.chapters,
    )
    for i, title in enumerate(outline, 1):
        print(f"  Chapter {i}: {title}")

    # ── 3. Full Document Generation ─────────────────────────────
    provider_name, model_name = args.provider, args.model
    if not provider_name:
        provider_name, model_name = _detect_provider()

    if not provider_name:
        print("\n  Skipping document generation (no LLM provider).")
        print("  Set OPENAI_API_KEY or ANTHROPIC_API_KEY to generate.")
        print()
        return

    print(f"\n━━━ 3. Generating Document ({provider_name}/{model_name}) ━━━\n")

    try:
        from crp import CRPOrchestrator  # noqa: E402

        orchestrator = CRPOrchestrator(
            provider_name=provider_name,
            model_name=model_name or "gpt-4o",
        )
        scribe = CRPScribe(orchestrator=orchestrator)

        def on_progress(chapter_num: int, title: str, status: str) -> None:
            icons = {"generating": "⏳", "complete": "✅", "error": "❌"}
            print(f"  {icons.get(status, '•')} Chapter {chapter_num}: {title} [{status}]")

        result = scribe.generate(
            topic=args.topic,
            outline=outline,
            template=args.template,
            progress_callback=on_progress,
            auto_save_dir=args.output_dir,
        )

        print(f"\n  Total chapters: {len(result.chapters)}")
        print(f"  Total length: {len(result.full_text):,} characters")
        print(f"  Template used: {result.template}")

        if args.output_dir:
            result.save(args.output_dir)
            print(f"  Saved to: {args.output_dir}/")

    except ImportError:
        print("  Error: CRP orchestrator not available. Check installation.")
    except Exception as e:
        print(f"  Error during generation: {e}")

    print()
    print("=" * 60)
    print("  CRP Scribe — Powered by the Context Relay Protocol™")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
