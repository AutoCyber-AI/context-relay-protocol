#!/usr/bin/env python3
"""Smoke-test the self-hosted console chat endpoint."""
from __future__ import annotations

import json
import sys
import urllib.request

URL = "http://127.0.0.1:8000/v1/chat/completions"
PAYLOAD = json.dumps({
    "messages": [{"role": "user", "content": "What is 7 times 8?"}]
}).encode("utf-8")

req = urllib.request.Request(
    URL,
    data=PAYLOAD,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        text = resp.read().decode("utf-8")
        print("status:", resp.status)
        print(text[:2000])
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8")
    print("HTTP FAILED status:", exc.code)
    print(body[:2000])
    sys.exit(1)
except Exception as exc:  # noqa: BLE001
    print("FAILED:", exc)
    sys.exit(1)
