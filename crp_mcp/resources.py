# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""MCP resource handlers for the CRP spec corpus, schemas, templates, and registries."""

from __future__ import annotations

import json
from typing import Any

from crp.headers import names as header_names
from crp.security.control_plane import get_default_control_plane
from crp_mcp.capabilities import SAFETY_PROFILES
from crp_mcp.corpus import get_corpus


def _json(data: Any) -> str:
    return json.dumps(data, indent=2)


async def get_spec_resource(spec_id: str) -> str:
    """Resource: crp://spec/{spec_id} — full authoritative spec text."""
    corpus = get_corpus()
    result = corpus.read_spec(spec_id)
    if "error" in result:
        return f"# Not found\n{result['error']}"
    return f"# {result['title']}\n\nSource: {result['source']}\n\n{result['text']}"


async def get_topic_resource(topic: str) -> str:
    """Resource: crp://topic/{topic} — topic page text."""
    corpus = get_corpus()
    result = corpus.read_topic(topic)
    if "error" in result:
        return f"# Not found\n{result['error']}"
    return result["text"]


async def get_schema_resource(schema_name: str) -> str:
    """Resource: crp://schema/{schema_name} — JSON schema."""
    corpus = get_corpus()
    result = corpus.read_schema(schema_name)
    if "error" in result:
        return _json(result)
    return _json(result["data"])


async def get_config_template(profile: str) -> str:
    """Resource: crp://template/config/{profile} — ready-to-use crp.config.yaml."""
    if profile not in SAFETY_PROFILES:
        return f"# Unknown profile '{profile}'. Use one of: {', '.join(SAFETY_PROFILES)}."
    yaml = f"""# CRP v4 config — {profile} profile
version: "4.0"
model:
  default: gpt-4o-mini
safety:
  profile: {profile}
  settings:
    require_grounding: 0.70
    hallucination_halt: CRITICAL
    pii_handling: flag
  coverage:
    jailbreak: on
    toxicity: warn
context:
  mode: auto
  depth: auto
knowledge:
  sources: ["docs/"]
"""
    return yaml


async def get_policy_template(profile: str) -> str:
    """Resource: crp://template/policy/{profile} — CRP-Safety-Policy string."""
    templates: dict[str, str] = {
        "balanced": "default-src 'self'; halt-on CRITICAL; warn-on HIGH; require-grounding 0.70; block-fabrication; block-distortion; pii flag",
        "strict": "default-src 'self'; halt-on HIGH; warn-on MEDIUM; require-grounding 0.85; block-fabrication; block-distortion; pii block",
        "medical": "default-src 'self'; halt-on MEDIUM; warn-on LOW; require-grounding 0.90; block-fabrication; block-distortion; pii block; oversight manual",
        "financial": "default-src 'self'; halt-on HIGH; warn-on MEDIUM; require-grounding 0.85; block-fabrication; block-distortion; pii redact; oversight manual",
        "public": "default-src 'self'; halt-on CRITICAL; warn-on HIGH; require-grounding 0.75; block-fabrication; pii redact",
    }
    return templates.get(profile, f"# Unknown profile '{profile}'. Use one of: {', '.join(SAFETY_PROFILES)}.")


async def get_example_resource(task: str) -> str:
    """Resource: crp://example/{task} — copy-paste SDK snippet."""
    examples: dict[str, str] = {
        "ingest": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nclient.knowledge.ingest("docs/")\n',
        "ask": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nclient.knowledge.ingest("docs/")\nanswer = client.ask("What is our refund policy?")\nprint(answer.text)\nprint(answer.crp.risk, answer.crp.grounded)\n',
        "tool": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\n\n@client.tool\ndef get_metrics(service: str) -> dict:\n    return {"cpu": 0.5}\n\nanswer = client.ask("How is the API service doing?", depth="thorough")\n',
        "safety": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nclient.safety.set(require_grounding=0.8, hallucination_halt="HIGH")\nclient.safety.set_profile("medical")\nprint(client.safety.show())\n',
        "checkpoint": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\ncheckpoint = client.safety.checkpoint(trigger="RISK_HIGH")\n',
        "session": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nsession = client.session()\nprint(session.id, session.status)\n',
        "complete": 'import crp\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\nr = client.complete("Summarise the EU AI Act")\nprint(r.text)\nprint(r.crp.risk, r.crp.grounded)\n',
        "migrate": 'import crp\n# v3 -> v4: use crp.SDKClient, crp.config.yaml, and client.safety.* helpers\nclient = crp.SDKClient(api_key=os.environ["CRP_API_KEY"])\n',
    }
    return examples.get(task, f"# Unknown task '{task}'. Use one of: {', '.join(examples)}.")


async def get_safety_registry() -> str:
    """Resource: crp://registry/safety — JSON safety capability registry."""
    cp = get_default_control_plane()
    data = {
        "capabilities": [cap.to_dict() for cap in cp.list_capabilities()],
        "out_of_scope": list(cp.coverage.out_of_scope),
    }
    return _json(data)


async def get_header_registry() -> str:
    """Resource: crp://registry/headers — JSON catalog of CRP-* headers."""
    headers: dict[str, str] = {}
    for name, value in vars(header_names).items():
        if name.isupper() and isinstance(value, str) and value.startswith("CRP-"):
            headers[name] = value
    return _json(headers)


def resolve_resource_uri(uri: str) -> tuple[str, dict[str, str]]:
    """Parse a crp:// URI into (handler_key, params)."""
    if not uri.startswith("crp://"):
        return "", {}
    rest = uri[6:]
    parts = rest.split("/", 1)
    handler = parts[0]
    arg = parts[1] if len(parts) > 1 else ""
    return handler, {"arg": arg}


async def get_oauth_authorization_server_metadata() -> str:
    """Resource: crp://.well-known/oauth-authorization-server."""
    return _json(
        {
            "issuer": "https://auth.crprotocol.io",
            "authorization_endpoint": "https://auth.crprotocol.io/oauth/authorize",
            "token_endpoint": "https://auth.crprotocol.io/oauth/token",
            "token_endpoint_auth_methods_supported": ["client_secret_post", "private_key_jwt"],
            "scopes_supported": ["crp:gateway", "crp:comply", "crp:scan"],
        }
    )


async def get_oauth_resource_server_metadata() -> str:
    """Resource: crp://.well-known/oauth-resource-server.

    Conforms to RFC 8707 resource indicators for token binding.
    """
    return _json(
        {
            "resource": "https://gateway.crprotocol.io",
            "scopes_supported": {
                "crp:gateway": "Governed inference calls and deployment.",
                "crp:comply": "Repository compliance analysis.",
                "crp:scan": "Ungoverned AI-call discovery.",
            },
            "authorization_servers": ["https://auth.crprotocol.io"],
        }
    )
