# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Verification Relay (SPEC-049)."""

from __future__ import annotations

from crp.vr.exec_verifier import ExecVerifier
from crp.vr.extract import extract_claims, verify_text
from crp.vr.interface import Claim, Verdict, VerificationResult, Verifier
from crp.vr.prm import ProcessRewardVerifier
from crp.vr.relay import VerificationRelay
from crp.vr.z3_verifier import Z3Verifier

__all__ = [
    "Claim",
    "ExecVerifier",
    "ProcessRewardVerifier",
    "VerificationRelay",
    "VerificationResult",
    "Verdict",
    "Verifier",
    "Z3Verifier",
    "extract_claims",
    "verify_text",
]
