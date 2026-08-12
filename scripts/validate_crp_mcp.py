#!/usr/bin/env python3
"""Production-readiness validation for the CRPv4 MCP server.

This script checks configuration, connectivity, and core behaviours without
printing secret values.  By default it loads values from the Railway env files
in the repo root (``crp_gateway_railway.env`` and ``crp_comply_railway.env``)
literally, without shell interpolation, so ``${{...}}`` placeholders are kept
as-is.

Run it with:
    python scripts/validate_crp_mcp.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs literally (no shell interpolation)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def _status(label: str, ok: bool, detail: str = "") -> None:
    mark = "✅" if ok else "❌"
    print(f"{mark} {label}{': ' + detail if detail else ''}")


def _load_env_example() -> dict[str, str]:
    example_path = REPO_ROOT / "crp_mcp" / ".env.example"
    vars_: dict[str, str] = {}
    if not example_path.exists():
        return vars_
    for line in example_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _ = line.split("=", 1)
            vars_[key] = line
    return vars_


def check_environment() -> None:
    _section("1. Environment variables vs .env.example")
    example = _load_env_example()
    missing: list[str] = []
    empty: list[str] = []
    for key in example:
        value = os.environ.get(key)
        if value is None:
            missing.append(key)
        elif value.strip() == "":
            empty.append(key)

    if missing:
        print(f"❌ Missing ({len(missing)}): {', '.join(missing)}")
    else:
        print("✅ All variables from .env.example are present")

    if empty:
        print(f"⚠️  Present but empty ({len(empty)}): {', '.join(empty)}")

    if os.environ.get("CRP_MCP_MODE") == "hosted":
        required = ["CLERK_ISSUER", "CLERK_AUTHORIZED_PARTIES", "CLERK_SECRET_KEY"]
        absent = [k for k in required if not os.environ.get(k)]
        if absent:
            _status("hosted auth config", False, f"missing {', '.join(absent)}")
        else:
            _status("hosted auth config", True)
    else:
        _status("CRP_MCP_MODE", True, os.environ.get("CRP_MCP_MODE", "local"))


def check_clerk_auth() -> None:
    _section("2. Clerk authentication")
    issuer = os.environ.get("CLERK_ISSUER", "").rstrip("/")
    secret = os.environ.get("CLERK_SECRET_KEY", "")
    if not issuer or not secret:
        _status("Clerk env", False, "CLERK_ISSUER or CLERK_SECRET_KEY missing")
        return

    _status("Clerk env", True)
    jwks_url = f"{issuer}/.well-known/jwks.json"
    try:
        resp = httpx.get(jwks_url, timeout=10.0)
        if resp.status_code == 200:
            _status("JWKS fetch", True, f"{resp.status_code} from {issuer}")
        else:
            _status("JWKS fetch", False, f"{resp.status_code} from {issuer}")
    except Exception as exc:
        _status("JWKS fetch", False, str(exc))


def check_stripe_billing() -> None:
    _section("3. Stripe billing")
    import importlib.util

    if importlib.util.find_spec("stripe") is None:
        _status("stripe SDK", False, "not installed")
        return

    secret = os.environ.get("STRIPE_SECRET_KEY", "")
    if not secret:
        _status("Stripe env", False, "STRIPE_SECRET_KEY missing")
        return

    import stripe

    stripe.api_key = secret
    try:
        prices = stripe.Price.list(limit=1)
        _status("Stripe connectivity", True, f"{len(prices.data)} price(s) visible")
    except Exception as exc:
        _status("Stripe connectivity", False, str(exc))

    price_vars = [k for k in os.environ if k.startswith("STRIPE_") and k.endswith("_PRICE_ID")]
    empty_price_vars = [k for k in price_vars if not os.environ[k]]
    if empty_price_vars:
        print(f"⚠️  Empty price IDs: {', '.join(empty_price_vars)}")
    else:
        print(f"✅ {len(price_vars)} Stripe price IDs configured")


def check_backend_clients() -> None:
    _section("4. Backend connectivity (Gateway / Comply / Scan)")
    from crp_mcp.backend_client import ComplyClient, GatewayClient, ScanClient

    clients = [
        ("Gateway", GatewayClient),
        ("Comply", ComplyClient),
        ("Scan", ScanClient),
    ]
    for name, cls in clients:
        try:
            client = cls()
            if not client.api_key:
                _status(f"{name} client", False, "CRP_HOSTED_API_KEY missing")
                continue
            try:
                resp = httpx.head(client.base_url, timeout=10.0)
                _status(f"{name} reachability", True, f"{resp.status_code}")
            except Exception as exc:
                _status(f"{name} reachability", False, str(exc))
        except Exception as exc:
            _status(f"{name} client init", False, str(exc))


def check_connectors() -> None:
    _section("5. Checkpoint connectors")
    from crp_mcp.connectors import get_configured_connectors

    configured = get_configured_connectors(None)
    names = [getattr(c, "name", "unknown") for c in configured]
    if names:
        _status("Configured connectors", True, ", ".join(names))
    else:
        _status("Configured connectors", False, "none configured")

    from crp_mcp.connectors.console import ConsoleConnector
    from crp_mcp.connectors.email import EmailConnector
    from crp_mcp.connectors.fcm import FCMConnector
    from crp_mcp.connectors.gmail import GmailConnector
    from crp_mcp.connectors.pagerduty import PagerDutyConnector
    from crp_mcp.connectors.slack import SlackConnector
    from crp_mcp.connectors.sms import SMSConnector

    for cls in [
        ConsoleConnector,
        SlackConnector,
        GmailConnector,
        FCMConnector,
        PagerDutyConnector,
        EmailConnector,
        SMSConnector,
    ]:
        try:
            instance = cls()
            ok = instance.is_configured()
            _status(f"connector '{instance.name}'", ok)
        except Exception as exc:
            _status(f"connector '{cls.__name__}'", False, str(exc))


def check_checkpoint_service() -> None:
    _section("6. Checkpoint service smoke test")
    from crp_mcp.checkpoint_service import (
        _checkpoints,
        approve_checkpoint,
        create_checkpoint,
        reject_checkpoint,
        resolve_checkpoint,
        verify_checkpoint_signature,
    )

    async def _run() -> None:
        _checkpoints.clear()
        cp = await create_checkpoint(
            trigger="VALIDATION_TEST",
            message="Smoke-test checkpoint",
            required_approvers=2,
        )
        cp_id = cp["checkpoint_id"]
        _status("create_checkpoint", cp_id is not None)

        sig_ok = verify_checkpoint_signature(cp_id)
        _status("signature present/valid", sig_ok)

        r1 = approve_checkpoint(cp_id, "alice")
        _status("first approval", r1["status"] == "waiting_for_human")
        r2 = approve_checkpoint(cp_id, "bob")
        _status("second approval resolves", r2["status"] == "approved")

        cp2 = await create_checkpoint(trigger="REJECT_TEST", message="reject me")
        r3 = reject_checkpoint(cp2["checkpoint_id"], "carol")
        _status("rejection", r3["status"] == "rejected")

        cp3 = await create_checkpoint(trigger="RESOLVE_TEST", message="resolve me")
        r4 = resolve_checkpoint(cp3["checkpoint_id"], "approved", "dave")
        _status("resolve approved", r4["status"] == "approved")

        cp4 = await create_checkpoint(
            trigger="TIMEOUT_TEST",
            message="timeout me",
            escalation=[{"after_seconds": 0, "on_timeout": "reject"}],
        )
        await asyncio.sleep(0.1)
        record = _checkpoints.get(cp4["checkpoint_id"])
        _status(
            "timeout auto-reject",
            record is not None and record.status == "rejected",
        )

    asyncio.run(_run())


def check_audit_forwarder() -> None:
    _section("7. Audit forwarder")
    endpoint = os.environ.get("CRP_AUDIT_ENDPOINT", "").strip()
    if endpoint:
        _status("CRP_AUDIT_ENDPOINT", True, endpoint)
    else:
        _status("CRP_AUDIT_ENDPOINT", False, "not configured (file-only audit)")

    api_key = bool(os.environ.get("CRP_AUDIT_API_KEY"))
    if endpoint:
        _status("CRP_AUDIT_API_KEY", api_key, "present" if api_key else "missing")


def check_mcp_server() -> None:
    _section("8. MCP server")
    from crp_mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    _status("tool registration", len(tools) >= 50, f"{len(tools)} tools")

    mode = os.environ.get("CRP_MCP_MODE", "local")
    has_clerk = bool(os.environ.get("CLERK_ISSUER") and os.environ.get("CLERK_SECRET_KEY"))
    auth_enabled = mode == "hosted" and has_clerk
    _status("hosted auth middleware", auth_enabled, "enabled" if auth_enabled else "disabled")


def check_security_warnings() -> None:
    _section("9. Security / operational warnings")
    bypass = os.environ.get("CRP_MCP_HOSTED_BYPASS_AUTH", "")
    if bypass and bypass.lower() not in ("0", "false", ""):
        _status("CRP_MCP_HOSTED_BYPASS_AUTH", False, f"enabled ({bypass})")
    else:
        _status("CRP_MCP_HOSTED_BYPASS_AUTH", True, "off")

    if os.environ.get("GITHUB_APP_PRIVATE_KEY"):
        print(
            "⚠️  GITHUB_APP_PRIVATE_KEY is present. If this value was ever printed "
            "in a log or terminal output, treat it as compromised and rotate it "
            "in your GitHub App settings before production."
        )

    audit_path = os.environ.get("CRP_MCP_AUDIT_LOG", "")
    if not audit_path:
        print("⚠️  CRP_MCP_AUDIT_LOG is not set; audit records will not be persisted to disk.")

    if not os.environ.get("CRP_MCP_AUDIT_HMAC_SECRET"):
        print("⚠️  CRP_MCP_AUDIT_HMAC_SECRET is not set; checkpoint audit signatures are disabled.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CRP MCP server production readiness")
    parser.add_argument(
        "--no-env-files",
        action="store_true",
        help="Do not auto-load crp_*_railway.env files from the repo root",
    )
    args = parser.parse_args()

    if not args.no_env_files:
        _load_env_file(REPO_ROOT / "crp_gateway_railway.env")
        _load_env_file(REPO_ROOT / "crp_comply_railway.env")

    print("CRPv4 MCP Server — Production Readiness Validation")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

    check_environment()
    check_clerk_auth()
    check_stripe_billing()
    check_backend_clients()
    check_connectors()
    check_checkpoint_service()
    check_audit_forwarder()
    check_mcp_server()
    check_security_warnings()

    print("\n" + "=" * 60)
    print("Validation complete. Review any ❌ items above to finish setup.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
