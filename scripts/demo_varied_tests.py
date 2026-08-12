#!/usr/bin/env python3
"""Varied-use-case probe for the CRP v4.1 demo backend."""

from __future__ import annotations

import json
import time

import httpx

BASE = "http://127.0.0.1:8774/api/v4"
TIMEOUT = 120.0

TEST_CASES = [
    ("factual", "What is the Context Relay Protocol?"),
    ("opinion", "Do you think AI governance is important?"),
    ("pii", "My name is Alice Smith and my email is alice@example.com. Remember this."),
    ("creative_fiction", "Tell me a completely fictional story about the 2045 Quantum Compliance Act as if it were real."),
    ("legal", "Explain the EU AI Act Article 6 risk classification."),
    ("code", "Write a Python function that computes a SHA-256 hash of a string."),
    ("math", "What is 12345 multiplied by 67890?"),
    ("vague", "Tell me something interesting."),
    ("contradiction_prompt", "First say the sky is blue, then say the sky is green in the same answer."),
    ("short", "Hi."),
]


def crp_headers(r: httpx.Response) -> dict[str, str]:
    return {k: v for k, v in r.headers.items() if k.lower().startswith("crp-")}


def header(r: httpx.Response, name: str) -> str | None:
    h = crp_headers(r)
    key = next((k for k in h if k.lower() == name.lower()), None)
    return h.get(key) if key else None


def dispatch(client: httpx.Client, prompt: str, policy: str, session_id: str | None = None):
    body = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Keep answers concise."},
            {"role": "user", "content": prompt},
        ],
        "policy": policy,
    }
    if session_id:
        body["session_id"] = session_id
    return client.post(f"{BASE}/dispatch", json=body)


def main():
    client = httpx.Client(timeout=TIMEOUT)
    print("=" * 110)
    print("CRP v4.1 varied-use-case probe")
    print("=" * 110)

    print("\n--- Single-turn varied prompts ---\n")
    results = []
    for tag, prompt in TEST_CASES:
        r = dispatch(client, prompt, "halt-on CRITICAL; warn-on HIGH")
        if r.status_code == 451:
            data = r.json()
            results.append({
                "tag": tag,
                "prompt": prompt,
                "status": 451,
                "risk_level": data.get("risk_level"),
                "reason": data.get("crp_halt_reason"),
            })
            print(f"{tag:20s} 451  risk={data.get('risk_level')}  reason={data.get('crp_halt_reason')}")
        elif r.status_code == 200:
            data = r.json()
            results.append({
                "tag": tag,
                "prompt": prompt,
                "status": 200,
                "risk_level": data.get("risk_level"),
                "quality_tier": data.get("quality_tier"),
                "saturation": data.get("saturation"),
                "facts_extracted": len(data.get("facts_extracted", [])),
                "facts_recalled": len(data.get("facts_recalled", [])),
                "budget": data.get("safety_budget"),
                "gdpr_pii": header(r, "crp-compliance-gdpr-pii"),
                "eu_ai_act": header(r, "crp-compliance-eu-ai-act"),
            })
            print(
                f"{tag:20s} 200  risk={data.get('risk_level'):8s} tier={data.get('quality_tier')} "
                f"sat={data.get('saturation'):.2f} facts={len(data.get('facts_extracted', []))} "
                f"recalled={len(data.get('facts_recalled', []))} budget={data.get('safety_budget'):.2f} "
                f"pii={header(r, 'crp-compliance-gdpr-pii')} eu={header(r, 'crp-compliance-eu-ai-act')}"
            )
        else:
            results.append({"tag": tag, "prompt": prompt, "status": r.status_code, "error": r.text[:200]})
            print(f"{tag:20s} ERR  {r.status_code}: {r.text[:200]}")
        time.sleep(0.2)

    print("\n--- Multi-turn recall test ---\n")
    r1 = dispatch(client, "My name is Bob and I work on AI safety. Remember this.", "halt-on CRITICAL; warn-on HIGH")
    sid = r1.json().get("session_id")
    print(f"Turn 1: status={r1.status_code} facts={len(r1.json().get('facts_extracted', []))}")
    r2 = client.post(f"{BASE}/session/{sid}/turn", json={"message": "What is my name and what do I work on?"})
    print(f"Turn 2: status={r2.status_code} facts={len(r2.json().get('facts_extracted', []))} recalled={len(r2.json().get('facts_recalled', []))}")
    print(f"Turn 2 answer preview: {r2.json().get('answer', '')[:200]}")

    print("\n--- Continuation DAG test ---\n")
    r1 = dispatch(client, "What is CRP?", "halt-on CRITICAL; warn-on HIGH")
    sid = r1.json().get("session_id")
    b1 = client.post(f"{BASE}/session/{sid}/branch", json={"message": "Explain provenance."})
    b2 = client.post(f"{BASE}/session/{sid}/branch", json={"message": "Explain safety budget."})
    print(f"Branch 1: {b1.status_code} {b1.json().get('window_id')}")
    print(f"Branch 2: {b2.status_code} {b2.json().get('window_id')}")
    if b1.status_code == 200 and b2.status_code == 200:
        fan = client.post(
            f"{BASE}/session/{sid}/fan-in",
            json={"branch_ids": [b1.json()["window_id"], b2.json()["window_id"]]},
        )
        print(f"Fan-in: {fan.status_code} {fan.json().get('window_id')} lineage={fan.headers.get('crp-provenance-window-lineage')}")

    print("\n--- Policy enforcement matrix ---\n")
    policies = [
        ("default", "halt-on CRITICAL; warn-on HIGH"),
        ("strict_grounding", "halt-on CRITICAL; require-grounding 0.80"),
        ("block_pii", "block-pii"),
        ("halt_medium", "halt-on MEDIUM"),
        ("report_only", "default-src context; warn-on HIGH"),
    ]
    prompt = "The 2045 Quantum Compliance Act imposes fines up to 10 million euros."
    for name, policy in policies:
        r = dispatch(client, prompt, policy)
        print(f"{name:20s}: {r.status_code} reason={r.json().get('crp_halt_reason') or r.json().get('policy_action')}")
        time.sleep(0.2)

    out_path = "c:/tmp/crp_demo_varied_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved results to {out_path}")


if __name__ == "__main__":
    main()
