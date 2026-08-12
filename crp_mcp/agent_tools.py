# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Agent-centric MCP tools that make discovering and building CRPv4 easy.

These tools are read-only, safe for any AI agent to call, and avoid secrets or
remote backends. They bridge high-level goals to concrete specs, config, code,
and next actions.
"""

from __future__ import annotations

import json
import re
from typing import Annotated, Any

from pydantic import Field

from crp_mcp.capabilities import (
    CRP_CAPABILITY_MAP,
    CRP_SCHEMAS,
    CRP_SPECS,
    SAFETY_PROFILES,
    SUPPORTED_STACKS,
)
from crp_mcp.config_tools import generate_config, generate_safety_policy
from crp_mcp.corpus import get_corpus
from crp_mcp.resources import get_config_template, get_policy_template
from crp_mcp.scaffold import integration as scaffold_integration
from crp_mcp.scan_tools import crp_scan_local_preview
from crp_mcp.types import err, ok

_KNOWN_POLICY_DIRECTIVES: set[str] = {
    "default-src",
    "halt-on",
    "warn-on",
    "require-grounding",
    "block-fabrication",
    "block-distortion",
    "block-pii",
    "pii",
    "oversight",
    "upgrade-on-risk",
}


async def crp_list_specs() -> str:
    """List every authoritative CRP specification with its title."""
    corpus = get_corpus()
    specs = CRP_SPECS if CRP_SPECS else corpus.list_specs()
    return ok({"specs": specs, "count": len(specs)})


async def crp_read_spec(
    spec_id: Annotated[
        str,
        Field(description="CRP spec id, e.g. 'CRP-SPEC-001'.", min_length=1, max_length=50),
    ],
) -> str:
    """Read the full authoritative text of a CRP specification."""
    corpus = get_corpus()
    result = corpus.read_spec(spec_id)
    if "error" in result:
        return err(result["error"])
    return ok({"spec_id": result["spec_id"], "title": result["title"], "text": result["text"]})


async def crp_list_schemas() -> str:
    """List the CRP JSON schemas available as resources."""
    return ok({"schemas": CRP_SCHEMAS, "count": len(CRP_SCHEMAS)})


async def crp_list_profiles() -> str:
    """List the built-in CRP safety profiles."""
    return ok({"profiles": SAFETY_PROFILES})


async def crp_list_stacks() -> str:
    """List the integration stacks supported by the scaffold tool."""
    return ok({"stacks": SUPPORTED_STACKS})


async def crp_recommend_capability(
    goal: Annotated[
        str,
        Field(description="Plain-language goal, e.g. 'stop hallucinations in customer support'.", min_length=1, max_length=500),
    ],
) -> str:
    """Recommend CRPv4 capabilities and specs for a stated goal."""
    goal_l = goal.lower()
    matches: list[dict[str, Any]] = []
    for cap in CRP_CAPABILITY_MAP:
        score = 0
        for intent in cap["intents"]:
            if intent in goal_l:
                score += 3
        for word in re.findall(r"[a-z0-9]+", goal_l):
            if len(word) < 3:
                continue
            if word in cap["name"] or word in cap["description"].lower():
                score += 1
            for spec in cap["specs"]:
                if word in spec.lower():
                    score += 1
        if score > 0:
            matches.append({"capability": cap, "score": score})
    matches.sort(key=lambda x: x["score"], reverse=True)
    return ok(
        {
            "goal": goal,
            "recommendations": [m["capability"] for m in matches[:5]],
            "next_steps": [
                "Use crp_scaffold_integration to generate starter code.",
                "Use crp_generate_config to produce a crp.config.yaml.",
                "Use crp_validate_config to check the config.",
            ],
        }
    )


async def crp_build_integration_plan(
    goal: Annotated[
        str,
        Field(description="What the integration must achieve.", min_length=1, max_length=500),
    ],
    stack: Annotated[
        str,
        Field(default="python-openai", description="Target stack, e.g. 'python-openai', 'node-openai', 'langchain'.", max_length=60),
    ] = "python-openai",
    safety_profile: Annotated[
        str,
        Field(default="balanced", description="Safety profile: balanced, strict, medical, financial, public.", max_length=30),
    ] = "balanced",
) -> str:
    """Produce a step-by-step CRP integration plan with config and code."""
    if safety_profile not in SAFETY_PROFILES:
        return err(f"Unknown profile '{safety_profile}'. Use one of: {', '.join(SAFETY_PROFILES)}.")
    code = scaffold_integration(stack=stack, goal=goal)
    config_yaml = await get_config_template(safety_profile)
    policy = await get_policy_template(safety_profile)
    plan = f"""# CRP v4 integration plan

**Goal:** {goal}
**Stack:** {stack}
**Safety profile:** {safety_profile}

## 1. One-line integration
{code}

## 2. Config (crp.config.yaml)
```yaml
{config_yaml}
```

## 3. Safety policy directive
```
{policy}
```

## 4. Next steps
- Validate config with `crp_validate_config`.
- Run conformance check with `crp_conformance_check`.
- Scan repo for ungoverned calls with `crp_scan_repo`.
"""
    return ok({"stack": stack, "profile": safety_profile, "plan": plan})


async def crp_validate_safety_policy(
    policy: Annotated[
        str,
        Field(description="A CRP-Safety-Policy directive string to validate.", min_length=1, max_length=2000),
    ],
) -> str:
    """Parse a CRP-Safety-Policy string and report unknown directives or anti-patterns."""
    notes: list[str] = []
    directives = [p.strip() for p in policy.split(";") if p.strip()]
    seen: set[str] = set()
    for directive in directives:
        keyword = directive.split()[0].lower() if directive else ""
        if keyword not in _KNOWN_POLICY_DIRECTIVES:
            notes.append(f"Unknown directive keyword: '{keyword}'")
        if keyword in seen and keyword != "default-src":
            notes.append(f"Duplicate directive: {keyword}")
        seen.add(keyword)
    if "halt-on" not in seen and "warn-on" not in seen:
        notes.append("No halt-on or warn-on directive found; risk events will not trigger policy action.")
    return ok({"policy": policy, "valid": not notes, "notes": notes})


async def crp_generate_scan_workflow(
    repo_ref: Annotated[
        str,
        Field(description="GitHub repo 'owner/repo' to scan.", min_length=1, max_length=200),
    ],
) -> str:
    """Return a GitHub Actions workflow YAML for CRP Scan."""
    workflow = f"""name: CRP Scan
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  crp-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run CRP Scan
        uses: crprotocol/scan-action@v1
        with:
          repo_ref: {repo_ref}
          fail_on_findings: "true"
"""
    return ok({"repo_ref": repo_ref, "workflow_yaml": workflow})


async def crp_generate_gateway_compose() -> str:
    """Return a docker-compose snippet for self-hosting the CRP Gateway."""
    compose = """version: "3.8"
services:
  crp-gateway:
    image: crprotocol/gateway:latest
    ports:
      - "8000:8000"
    environment:
      CRP_API_KEY: ${CRP_API_KEY}
      CRP_GATEWAY_URL: http://localhost:8000/v1
    volumes:
      - crp-gateway-state:/data
  volumes:
    crp-gateway-state:
"""
    return ok({"compose_yaml": compose})


async def crp_config_from_text(
    description: Annotated[
        str,
        Field(description="Plain-language description of desired governance, e.g. 'block hallucinations, require grounding, redact PII'.", min_length=1, max_length=2000),
    ],
) -> str:
    """Generate a crp.config.yaml and safety policy from plain English."""
    desc_l = description.lower()
    config_intent: dict[str, Any] = {}
    policy_intent: dict[str, Any] = {}
    if any(k in desc_l for k in ("hallucination", "fabrication", "grounding")):
        config_intent["prevent_hallucinations"] = True
        config_intent["grounding_threshold"] = 0.8
        policy_intent["grounding_threshold"] = 0.8
        policy_intent["block_fabrications"] = True
    if "pii" in desc_l or "personal data" in desc_l:
        config_intent["pii_detection"] = True
        policy_intent["pii"] = "redact" if "redact" in desc_l else "block"
    if "strict" in desc_l or "block" in desc_l:
        config_intent["halt_on_critical"] = True
        policy_intent["halt_on"] = "HIGH"
    else:
        policy_intent["halt_on"] = "CRITICAL"
    if "human" in desc_l or "oversight" in desc_l or "manual" in desc_l:
        config_intent["human_oversight"] = True
        policy_intent["human_oversight"] = True
    if "jailbreak" in desc_l or "injection" in desc_l:
        config_intent["prompt_injection_shield"] = True
        policy_intent["prompt_injection_shield"] = True
    if "toxicity" in desc_l:
        config_intent["toxicity_filter"] = True

    config_result = generate_config(config_intent)
    policy_result = generate_safety_policy(policy_intent)
    return ok(
        {
            "description": description,
            "config_intent": config_intent,
            "policy_intent": policy_intent,
            "config": config_result,
            "policy": policy_result,
        }
    )


async def crp_audit_project(
    codebase_path: Annotated[
        str,
        Field(default="./", description="Path to the codebase root.", max_length=200),
    ] = "./",
    source_text: Annotated[
        str,
        Field(default="", description="Optional representative source snippet to scan.", max_length=50000),
    ] = "",
) -> str:
    """Audit a project for CRP readiness: scan snippet and return a remediation checklist."""
    findings: list[dict[str, Any]] = []
    if source_text:
        scan_result = json.loads(await crp_scan_local_preview(source_text=source_text))
        findings = scan_result.get("findings", [])
    checklist = [
        "1. Replace raw LLM client initialisation with CRP SDK or Gateway base_url swap.",
        "2. Add crp.config.yaml with a safety profile.",
        "3. Run crp_scan_repo on the full repository.",
        "4. Run crp_conformance_check to validate behaviour.",
        "5. Use crp_comply_repo to map to EU AI Act / ISO 42001 / GDPR if needed.",
    ]
    return ok(
        {
            "codebase_path": codebase_path,
            "findings": findings,
            "checklist": checklist,
            "next_tool": "crp_build_integration_plan",
        }
    )


async def crp_quickstart() -> str:
    """Return a concise getting-started guide for CRPv4."""
    guide = """# CRPv4 quickstart

1. Install the SDK: `pip install crprotocol`
2. Set your CRP API key: `export CRP_API_KEY=...`
3. Swap the OpenAI base_url to `https://gateway.crprotocol.io/v1`
4. Add a `crp.config.yaml` (use `crp_generate_config`).
5. Run `crp_conformance_check` to verify.

For no-code compliance, connect your repo with `crp_connect_repo_link`
and run `crp_comply_repo`.
"""
    return ok({"guide": guide})
