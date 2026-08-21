#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent Template — Data Analyst Agent.

Loads a CSV, answers questions with structured queries, and generates a
simple chart description. Runs against a REAL model (LM Studio / OpenAI /
Anthropic / Ollama — auto-detected).

Run:
    python examples/templates/data_analyst_agent.py
"""

from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))

import crp
from _shared import resolve_provider

# ── Mock dataset ────────────────────────────────────────────────────────────

_SALES: list[dict[str, Any]] = [
    {"region": "APAC", "product": "A", "q1": 120, "q2": 150},
    {"region": "APAC", "product": "B", "q1": 90, "q2": 110},
    {"region": "EMEA", "product": "A", "q1": 80, "q2": 95},
    {"region": "EMEA", "product": "B", "q1": 60, "q2": 70},
]


# ── Tools ─────────────────────────────────────────────────────────────────


def load_csv(filename: str) -> list[dict[str, Any]]:
    """Return rows from the mock CSV."""
    if filename != "sales.csv":
        return []
    return _SALES


def query_data(region: str | None = None, product: str | None = None) -> dict[str, Any]:
    """Aggregate sales by optional filters."""
    rows = [r for r in _SALES if (region is None or r["region"] == region) and (product is None or r["product"] == product)]
    total_q1 = sum(r["q1"] for r in rows)
    total_q2 = sum(r["q2"] for r in rows)
    return {
        "rows_matched": len(rows),
        "total_q1": total_q1,
        "total_q2": total_q2,
        "growth_pct": round((total_q2 - total_q1) / total_q1 * 100, 1) if total_q1 else 0,
    }


def plot_chart(chart_type: str, x_axis: str, y_axis: str, title: str) -> dict[str, str]:
    """Return a chart specification that a frontend can render."""
    return {
        "chart_type": chart_type,
        "x_axis": x_axis,
        "y_axis": y_axis,
        "title": title,
        "status": "spec_ready",
    }


# ── Mock SLM ────────────────────────────────────────────────────────────────

provider = resolve_provider()


# ── Agent ─────────────────────────────────────────────────────────────────

agent = crp.Agent(
    provider=provider,
    tools=[load_csv, query_data, plot_chart],
    system=(
        "You are a data analyst. Load the CSV, run queries, and produce "
        "chart specifications. Always ground answers in the queried data."
    ),
    profile="capable-local",
)


# ── Run ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    step1 = agent.run("Load sales.csv.")
    print("Step 1 —", step1.answer)
    print("  Operations:", step1.how_it_was_built, " Sources:", len(step1.sources))

    step2 = agent.run("Calculate the APAC region's growth from Q1 to Q2.", prior_cso=step1.cso)
    print("Step 2 —", step2.answer)
    print("  Operations:", step2.how_it_was_built, " Sources:", len(step2.sources))

    step3 = agent.run("Create a bar chart of growth by region.", prior_cso=step2.cso)
    print("Step 3 —", step3.answer)
    print("  Operations:", step3.how_it_was_built, " Grounded:", step3.crp.grounded)
