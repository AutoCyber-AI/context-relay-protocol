#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent Template — Data Analyst Agent.

Loads a CSV, answers questions with structured queries, and generates a
simple chart description. Demonstrates structured tool decoding and the
CRP structured-output path.
"""

from __future__ import annotations

import json
import re
from typing import Any

import crp
from crp.providers.custom import CustomProvider

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


def _mock_generate(messages: list[dict[str, str]]) -> tuple[str, str]:
    prompt = messages[-1]["content"]
    objective_match = re.search(r"objective:\s*(.+)", prompt, re.IGNORECASE)
    objective = (objective_match.group(1).strip() if objective_match else prompt).lower()

    if "load" in objective or "csv" in objective or "data" in objective:
        return (
            json.dumps({"capability_id": "load_csv", "arguments": {"filename": "sales.csv"}}),
            "stop",
        )
    if "query" in objective or "total" in objective or "sales" in objective or "growth" in objective:
        region = "APAC" if "apac" in objective else None
        return (
            json.dumps({"capability_id": "query_data", "arguments": {"region": region}}),
            "stop",
        )
    if "chart" in objective or "plot" in objective or "visual" in objective:
        return (
            json.dumps({"capability_id": "plot_chart", "arguments": {"chart_type": "bar", "x_axis": "region", "y_axis": "growth_pct", "title": "Q1→Q2 Growth by Region"}}),
            "stop",
        )

    return (
        json.dumps({"capability_id": None, "answer": "Analysis complete."}),
        "stop",
    )


provider = CustomProvider(
    generate_fn=_mock_generate,
    count_tokens_fn=lambda text: max(1, len(text.split())),
    context_size=8192,
    name="mock-slm",
)


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
    result = agent.run("Load sales.csv, calculate APAC growth, and create a bar chart")
    print("Answer:", result.answer)
    print("Operations:", result.how_it_was_built)
    print("Grounded:", result.crp.grounded)
    print("Sources:", result.sources)
