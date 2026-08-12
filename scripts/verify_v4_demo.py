#!/usr/bin/env python3
"""Smoke-test the CRP v4.1 protocol demo backend.

Runs without external dependencies beyond ``httpx``. Expects the demo server on
http://127.0.0.1:8774.
"""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8774/api/v4"
TIMEOUT = 240.0
MODEL = "qwen3-4b"
PROVIDER = "local"


def crp_headers(r: httpx.Response) -> dict[str, str]:
    return {k: v for k, v in r.headers.items() if k.lower().startswith("crp-")}


def has_prefix_only(h: dict[str, str], prefix: str = "CRP-") -> bool:
    return all(k.lower().startswith(prefix.lower()) for k in h)


def has_header(h: dict[str, str], name: str) -> bool:
    return any(k.lower() == name.lower() for k in h)


def main() -> int:
    client = httpx.Client(timeout=TIMEOUT)
    failures: list[str] = []

    # 1. Provider discovery
    r = client.get(f"{BASE}/models")
    if r.status_code != 200:
        failures.append(f"/models returned {r.status_code}")
    else:
        data = r.json()
        if data.get("protocol_version") != "4.1.1":
            failures.append("protocol_version is not 4.1.1")
        providers = data.get("providers", [])
        local = next((p for p in providers if p.get("provider") == "local"), None)
        if not local or not local.get("reachable"):
            failures.append("local provider is not reachable")

    # 2. Normal dispatch returns CRP-* headers, no X-CRP-* headers
    r = client.post(
        f"{BASE}/dispatch",
        json={
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the Context Relay Protocol?"},
            ],
            "policy": "halt-on CRITICAL; warn-on HIGH",
            "model": MODEL,
            "provider": PROVIDER,
        },
    )
    if r.status_code != 200:
        failures.append(f"dispatch returned {r.status_code}: {r.text[:200]}")
        return 1

    headers = crp_headers(r)
    if not headers:
        failures.append("no CRP-* headers returned")
    if not has_prefix_only(headers):
        failures.append("non-CRP-* governance header leaked")
    if any(k.lower().startswith("x-crp-") for k in r.headers):
        failures.append("legacy X-CRP-* header leaked")

    data = r.json()
    session_id = data.get("session_id")
    if not session_id:
        failures.append("missing session_id")
        return 1

    required = [
        "CRP-Context-Protocol-Version",
        "CRP-Context-Session-Id",
        "CRP-Context-Window",
        "CRP-Context-Quality-Tier",
        "CRP-Context-Saturation",
        "CRP-Safety-Hallucination-Risk",
        "CRP-Safety-Grounding-Pct",
        "CRP-Provenance-Window-HMAC",
        "CRP-Provenance-Chain-Integrity",
        "CRP-Compliance-EU-AI-Act",
        "CRP-Compliance-GDPR-PII",
        "CRP-Agent-Safety-Budget",
        "CRP-Set-Session",
    ]
    missing = [h for h in required if not has_header(headers, h)]
    if missing:
        failures.append(f"missing headers: {missing}")

    # 3. Safety budget decrements across turns
    r2 = client.post(
        f"{BASE}/session/{session_id}/turn",
        json={"message": "How does CRP ensure provenance?", "model": MODEL, "provider": PROVIDER},
    )
    if r2.status_code != 200:
        failures.append(f"turn returned {r.status_code}: {r2.text[:200]}")
    else:
        def get_budget(r: httpx.Response) -> float:
            h = crp_headers(r)
            key = next((k for k in h if k.lower() == "crp-agent-safety-budget"), "")
            return float(h.get(key, "1"))

        budget1 = get_budget(r)
        budget2 = get_budget(r2)
        if budget2 >= budget1:
            failures.append("safety budget did not decrement after turn")
        def get_window(r: httpx.Response) -> str:
            h = crp_headers(r)
            return h.get(next((k for k in h if k.lower() == "crp-context-window"), ""), "")

        window1 = get_window(r)
        window2 = get_window(r2)
        if window1 == window2:
            failures.append("window did not advance after turn")

    # 4. Policy halt returns HTTP 451
    r3 = client.post(
        f"{BASE}/dispatch",
        json={
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"},
            ],
            "policy": "halt-on HIGH",
            "model": MODEL,
            "provider": PROVIDER,
        },
    )
    if r3.status_code != 451:
        failures.append(f"expected HTTP 451, got {r3.status_code}")
    else:
        body = r3.json()
        if "crp_halt_reason" not in body:
            failures.append("451 body missing crp_halt_reason")
        if "audit_trail_uri" not in body:
            failures.append("451 body missing audit_trail_uri")

    # 5. Audit chain verifies then breaks on tamper
    r_verify = client.get(f"{BASE}/session/{session_id}/verify")
    if r_verify.status_code != 200 or not r_verify.json().get("valid"):
        failures.append("chain did not verify before tamper")

    r_tamper = client.post(f"{BASE}/session/{session_id}/tamper", json={"index": 0})
    if r_tamper.status_code != 200:
        failures.append(f"tamper returned {r_tamper.status_code}")
    else:
        r_verify2 = client.get(f"{BASE}/session/{session_id}/verify")
        if r_verify2.json().get("valid"):
            failures.append("chain still valid after tamper")

    # 6. Export endpoints exist
    r_ndjson = client.get(f"{BASE}/session/{session_id}/export.ndjson")
    if r_ndjson.status_code != 200:
        failures.append(f"export.ndjson returned {r_ndjson.status_code}")
    r_ocsf = client.get(f"{BASE}/session/{session_id}/export.ocsf")
    if r_ocsf.status_code != 200:
        failures.append(f"export.ocsf returned {r_ocsf.status_code}")
    else:
        ocsf = r_ocsf.json()
        if not isinstance(ocsf, list) or not any(e.get("class_uid") == 6003 for e in ocsf):
            failures.append("OCSF export missing class_uid=6003 records")

    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("All CRP v4.1 demo smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
