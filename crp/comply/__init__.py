# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Comply — the management + compliance plane over CRP Gateway.

Phase 0: Billing (Stripe + Clerk)
Phase 1: Gateway swap (proxy → CRP Gateway)
Phase 2: Safety layer (DPE, Safety Policy, checkpoints)
Phase 3: GitHub + Scan connection
Phase 4: Agent on v4 retrieval
Phase 5: No-code governance translator
"""

from __future__ import annotations
