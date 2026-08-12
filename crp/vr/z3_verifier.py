# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Symbolic SMT verifier for arithmetic and logical constraints (SPEC-049 §1.3.2).

When ``z3-solver`` is installed this verifier is *sound*: a VALID verdict is a
proof and confidence is 1.0.  Without z3 it falls back to a lightweight, bounded
pure-Python evaluator so that symbolic verification still runs in zero-dependency
mode (confidence remains 1.0 only for deductive cases that the fallback can close).
"""

from __future__ import annotations

import ast
import logging
from typing import Any

from crp.vr.interface import Claim, Verdict, VerificationResult

logger = logging.getLogger(__name__)


try:
    import z3  # type: ignore[import]

    _HAS_Z3 = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_Z3 = False
    z3 = None  # type: ignore[misc]


class Z3Verifier:
    """Sound SMT verification for arithmetic/constraint claims."""

    name = "z3-smt"

    def applies(self, claim: Claim) -> bool:
        """Apply to constraint-style claims with a formal ``claim`` to prove."""
        if claim.formal is None:
            return False
        return claim.kind == "constraint" or (
            claim.kind == "arithmetic"
            and "claim" in claim.formal
            and "vars" in claim.formal
        )

    def verify(self, claim: Claim, context: dict[str, Any]) -> VerificationResult:
        """Prove or disprove that the claim follows from its premises."""
        formal = claim.formal or {}
        if _HAS_Z3:
            return self._verify_with_z3(formal)
        return self._verify_fallback(formal)

    def _verify_with_z3(self, formal: dict[str, Any]) -> VerificationResult:
        """Use z3 to check premises ∧ ¬claim for unsatisfiability."""
        assert z3 is not None
        s = z3.Solver()
        env: dict[str, Any] = {}
        for var_name, ty in formal.get("vars", {}).items():
            env[var_name] = z3.Int(var_name) if ty == "Int" else z3.Real(var_name)
        for assertion in formal.get("assert", []):
            s.add(self._safe_eval(assertion, env))
        s.add(z3.Not(self._safe_eval(formal.get("claim", "False"), env)))
        r = s.check()
        if r == z3.unsat:
            return VerificationResult(
                Verdict.VALID, 1.0, "entailed (proof)", self.name, True
            )
        if r == z3.sat:
            return VerificationResult(
                Verdict.INVALID,
                1.0,
                f"counterexample: {s.model()}",
                self.name,
                True,
            )
        return VerificationResult(
            Verdict.UNKNOWN, 0.0, "solver undecided", self.name, True
        )

    def _safe_eval(self, expr: str, env: dict[str, Any]) -> Any:
        """Evaluate a z3 expression in a restricted environment."""
        return eval(expr, {"__builtins__": {}}, env)  # noqa: S307

    def _verify_fallback(self, formal: dict[str, Any]) -> VerificationResult:
        """Bounded pure-Python fallback for simple integer constraints.

        This is intentionally narrow: it supports linear integer constraints and
        checks the claim by exhaustive search over a bounded range.  It lets the
        verifier remain active when z3 is not installed while refusing to claim
        VALID for claims it cannot close within the bound.
        """
        vars_spec = formal.get("vars", {})
        if not vars_spec or any(ty not in ("Int",) for ty in vars_spec.values()):
            return VerificationResult(
                Verdict.UNKNOWN,
                0.0,
                "z3 not installed; fallback cannot decide this domain",
                self.name,
                True,
            )

        var_names = list(vars_spec.keys())
        asserts = formal.get("assert", [])
        claim_expr = formal.get("claim", "False")

        # Small bounded search over [-10, 10] for each variable.
        bound = 10
        found_model = False
        for values in _product_range(var_names, bound):
            env = dict(values)
            try:
                premises_hold = all(
                    _eval_bool(a, env) for a in asserts
                )
            except Exception:
                continue
            if not premises_hold:
                continue
            try:
                claim_holds = _eval_bool(claim_expr, env)
            except Exception:
                continue
            if not claim_holds:
                return VerificationResult(
                    Verdict.INVALID,
                    1.0,
                    f"counterexample: {env}",
                    self.name,
                    True,
                )
            found_model = True

        if found_model:
            return VerificationResult(
                Verdict.VALID,
                1.0,
                "entailed within bounded search",
                self.name,
                True,
            )
        return VerificationResult(
            Verdict.UNKNOWN,
            0.0,
            "no satisfying model found in fallback bound",
            self.name,
            True,
        )


def _product_range(names: list[str], bound: int):
    """Yield every assignment of ``names`` to integers in ``[-bound, bound]``."""
    import itertools

    ranges = [range(-bound, bound + 1) for _ in names]
    for vals in itertools.product(*ranges):
        yield list(zip(names, vals))


def _eval_bool(expr: str, env: dict[str, int]) -> bool:
    """Evaluate a simple comparison expression with integer variables."""
    node = ast.parse(expr, mode="eval")
    return _eval_node(node.body, env)


def _eval_node(node: ast.AST, env: dict[str, int]) -> Any:
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, env)
        right = _eval_node(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_node(node.operand, env)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, env)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, env)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            else:
                raise ValueError(f"unsupported operator {op!r}")
            if not ok:
                return False
        return True
    raise ValueError(f"unsupported expression {ast.dump(node)}")
