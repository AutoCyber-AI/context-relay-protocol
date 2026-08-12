# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Judge a saved local-model SQB run with the Kimi (Moonshot) LLM-as-judge.

This produces the SPEC-026 Gate-5 usefulness score for the *local model's actual
output* — i.e. "CRP-governed local generation, scored by a frontier judge". It
reuses the SQB rubric (``case.judge_criteria``) and the ``llm_judge`` function.

Usage:
    python examples/crp_demos/sqb_kimi_judge.py sqb_results/v5_local_8b.json

The Kimi key is read from ``kimi_moonshot_api_key.txt`` (repo root) or the
``MOONSHOT_API_KEY`` environment variable. It is never printed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.crp_demos.sqb_benchmark import get_all_test_cases, llm_judge

KIMI_URL = "https://api.moonshot.ai/v1"
KIMI_MODEL = "kimi-k2.6"


def _load_key() -> str:
    key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    if key:
        return key
    key_file = Path(__file__).resolve().parents[2] / "kimi_moonshot_api_key.txt"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    raise SystemExit("No Kimi key: set MOONSHOT_API_KEY or add kimi_moonshot_api_key.txt")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: sqb_kimi_judge.py <results.json>")
        return 2
    results_path = Path(sys.argv[1])
    data = json.loads(results_path.read_text(encoding="utf-8"))
    key = _load_key()
    cases_by_id = {c.case_id: c for c in get_all_test_cases()}

    print(f"Kimi judge ({KIMI_MODEL}) on {results_path.name}\n")
    scores: list[float] = []
    for case_dict in data.get("cases", []):
        cid = case_dict["case_id"]
        case = cases_by_id.get(cid)
        full_output = case_dict.get("full_output", "")
        if case is None or not full_output:
            print(f"  {cid}: skipped (no case/output)")
            continue
        judge = llm_judge(
            case,
            full_output,
            api_url=KIMI_URL,
            api_key=key,
            model=KIMI_MODEL,
            temperature=0.6,
            extra_request_fields={"thinking": {"type": "disabled"}},
        )
        mean = judge.get("mean_score", 0.0)
        if judge.get("error"):
            print(f"  {cid} ({case.domain}): ERROR {judge['error']}")
            continue
        scores.append(float(mean))
        notes = str(judge.get("overall_notes", ""))[:110]
        print(f"  {cid} ({case.domain}): {mean}/10  — {notes}")

    if scores:
        print(f"\n  MEAN usefulness (Kimi judge, local generation): {sum(scores)/len(scores):.2f}/10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
