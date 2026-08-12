# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP demo applications — package marker.

Two zero-dependency, browser-based demos that drive a *local* LLM (via LM
Studio / Ollama / llama.cpp) through the Context Relay Protocol and surface
every governance signal CRP produces:

* **App 1 — AI Safety & Governance Console** (``safety.html``)
* **App 2 — Context Management & Provenance Explorer** (``context.html``)

Run with::

    python -m examples.crp_demos.server

then open http://127.0.0.1:8770 in a browser.
"""
