# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase-8 policy compiler for CRP checkpoint conditions.

Parses a small, safe expression language and evaluates it against a context
dictionary.  This lets users write rules such as:

    risk >= HIGH
    tool_call == "approve_loan" and amount > 1000000
    pii_detected and not internal_user

Supported literals:
  * numbers (int / float)
  * strings (single or double quotes)
  * booleans: true, false
  * null

Supported operators:
  * comparison: ==, !=, <, >, <=, >=
  * logical: and, or, not
  * grouping: parentheses

Variables are looked up in the supplied context dict. Dotted paths such as
``risk.level`` are supported.
"""

from __future__ import annotations

import ast
import json
import operator
from collections.abc import Callable
from typing import Any


class CheckpointPolicyError(ValueError):
    """Raised when a checkpoint condition cannot be parsed or evaluated."""


# Allowed AST node types for the sandboxed evaluator.
_ALLOWED_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.BoolOp,
    ast.UnaryOp,
    ast.BinOp,
    ast.Compare,
    ast.Name,
    ast.Constant,
    ast.Load,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.USub,
    ast.UAdd,
)


def _get_variable(ctx: dict[str, Any], name: str) -> Any:
    """Resolve a variable name, supporting dotted paths like ``risk.level``."""
    parts = name.split(".")
    value: Any = ctx
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            return None
    return value


_RISK_LEVELS = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}


def _coerce_operand(value: Any) -> Any:
    """Map recognised risk-level strings to ordinal numbers for comparison."""
    if isinstance(value, str) and value.upper() in _RISK_LEVELS:
        return _RISK_LEVELS[value.upper()]
    return value


def _compare(
    left: Any,
    op: ast.cmpop,
    right: Any,
) -> bool:
    operators: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }
    fn = operators.get(type(op))
    if fn is None:
        raise CheckpointPolicyError(f"unsupported comparison: {type(op).__name__}")

    # Allow natural risk-level ordering (e.g. risk >= HIGH).
    if isinstance(left, str) or isinstance(right, str):
        coerced_left = _coerce_operand(left)
        coerced_right = _coerce_operand(right)
        if isinstance(coerced_left, int) and isinstance(coerced_right, int):
            return fn(coerced_left, coerced_right)
    return fn(left, right)


def _eval_node(node: ast.AST, ctx: dict[str, Any]) -> Any:
    if type(node) not in _ALLOWED_NODES:
        raise CheckpointPolicyError(f"disallowed expression node: {type(node).__name__}")

    if isinstance(node, ast.Expression):
        return _eval_node(node.body, ctx)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        # Support policy shorthand like `risk >= HIGH` by treating all-caps
        # identifiers as string literals rather than context variables.
        if node.id.isupper():
            return node.id
        return _get_variable(ctx, node.id)

    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, ctx) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise CheckpointPolicyError(f"unsupported bool op: {type(node.op).__name__}")

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, ctx)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        raise CheckpointPolicyError(f"unsupported unary op: {type(node.op).__name__}")

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, ctx)
        right = _eval_node(node.right, ctx)
        op_map: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
        }
        fn = op_map.get(type(node.op))
        if fn is None:
            raise CheckpointPolicyError(f"unsupported binary op: {type(node.op).__name__}")
        return fn(left, right)

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, ctx)
        result = True
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, ctx)
            result = result and _compare(left, op, right)
            left = right
        return result

    raise CheckpointPolicyError(f"cannot evaluate: {type(node).__name__}")


def compile_condition(condition: str) -> Callable[[dict[str, Any]], bool]:
    """Parse a checkpoint condition and return a callable evaluator."""
    try:
        tree = ast.parse(condition, mode="eval")
    except SyntaxError as exc:
        raise CheckpointPolicyError(f"invalid condition syntax: {exc}") from exc

    # Validate the tree only contains allowed nodes.
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            raise CheckpointPolicyError(
                f"disallowed expression node: {type(node).__name__}"
            )

    def evaluator(ctx: dict[str, Any]) -> bool:
        try:
            result = _eval_node(tree, ctx)
        except CheckpointPolicyError:
            raise
        except Exception as exc:
            raise CheckpointPolicyError(f"condition evaluation failed: {exc}") from exc
        return bool(result)

    return evaluator


def evaluate_condition(condition: str, context_json: str) -> dict[str, Any]:
    """Evaluate a condition against a JSON context and return a structured result."""
    try:
        ctx = json.loads(context_json)
    except json.JSONDecodeError as exc:
        raise CheckpointPolicyError(f"invalid context JSON: {exc}") from exc
    if not isinstance(ctx, dict):
        raise CheckpointPolicyError("context must be a JSON object")

    evaluator = compile_condition(condition)
    return {
        "condition": condition,
        "matched": evaluator(ctx),
        "context_keys": sorted(ctx.keys()),
    }


def resolve_route(
    trigger: str,
    condition: str | None,
    context: dict[str, Any],
    default_connector: str = "console",
) -> tuple[str, str]:
    """Pick a review channel based on the first matching route rule.

    Routes are read from ``CRP_MCP_CHECKPOINT_ROUTES`` as a JSON array:

    [
      {"condition": "risk >= HIGH", "connector": "slack", "route_to": "#safety"},
      {"condition": "tool_call == 'deploy_endpoint'", "connector": "pagerduty"}
    ]

    Returns (connector, route_to).  If nothing matches, falls back to the
    default connector and an empty route_to.
    """
    import os

    raw = os.environ.get("CRP_MCP_CHECKPOINT_ROUTES", "")
    if not raw:
        return default_connector, ""

    try:
        rules = json.loads(raw)
    except json.JSONDecodeError:
        return default_connector, ""
    if not isinstance(rules, list):
        return default_connector, ""

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_condition = rule.get("condition")
        if rule_condition is None:
            continue
        try:
            if compile_condition(rule_condition)(context):
                return (
                    rule.get("connector", default_connector),
                    rule.get("route_to", ""),
                )
        except CheckpointPolicyError:
            continue

    return default_connector, ""
