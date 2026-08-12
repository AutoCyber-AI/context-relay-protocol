# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Sandboxed executor verifier for computational claims (SPEC-049 §1.3.3).

Deterministically evaluates arithmetic expressions supplied in a structured
``formal`` field.  The expression is executed in a locked-down subprocess using
the same Python interpreter, isolated with ``-I`` and a minimal environment.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Any

from crp.vr.interface import Claim, Verdict, VerificationResult

logger = logging.getLogger(__name__)


class ExecVerifier:
    """Verify arithmetic claims by deterministic, sandboxed execution."""

    name = "sandboxed-exec"

    def applies(self, claim: Claim) -> bool:
        """Apply to arithmetic claims that carry a formal ``expr`` field."""
        return (
            claim.kind == "arithmetic"
            and claim.formal is not None
            and "expr" in claim.formal
        )

    def verify(self, claim: Claim, context: dict[str, Any]) -> VerificationResult:
        """Execute ``formal["expr"]`` and compare with ``formal["expected"]``."""
        formal = claim.formal or {}
        expr = formal.get("expr", "")
        expected = formal.get("expected")

        if not expr or expected is None:
            return VerificationResult(
                Verdict.UNKNOWN,
                0.0,
                "missing expr or expected value",
                self.name,
                True,
            )

        try:
            actual = self._run_isolated(expr)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("ExecVerifier failed for expr=%r: %s", expr, exc)
            return VerificationResult(
                Verdict.UNKNOWN,
                0.0,
                f"exec error: {exc}",
                self.name,
                True,
            )

        if actual == expected:
            return VerificationResult(
                Verdict.VALID,
                1.0,
                f"{actual} == {expected}",
                self.name,
                True,
            )
        return VerificationResult(
            Verdict.INVALID,
            1.0,
            f"computed {actual}, claim said {expected}",
            self.name,
            True,
        )

    def _run_isolated(self, expr: str) -> Any:
        """Run *expr* in a subprocess with the same Python binary.

        Uses ``-I`` (isolated mode), no user site, and a minimal environment to
        limit attack surface.  Only a pure numeric expression is safe to pass;
        callers must parse/validate formal expressions through SPEC-054 before
        invoking the verifier.
        """
        code = f"import json; print(json.dumps({expr}))"
        env = {"PATH": os.environ.get("PATH", "")}
        proc = subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=2,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "subprocess failed")
        return json.loads(proc.stdout.strip())
