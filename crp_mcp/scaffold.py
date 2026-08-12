# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Static integration scaffolds — return code as text; never execute it."""

from __future__ import annotations


def integration(stack: str, goal: str = "govern all LLM calls") -> str:
    """Return a copy-paste integration snippet for the requested stack."""
    stack_norm = stack.lower().strip().replace(" ", "-").replace("_", "-")

    mapping = {
        "python": _python_openai,
        "python-openai": _python_openai,
        "openai": _python_openai,
        "python-anthropic": _python_anthropic,
        "anthropic": _python_anthropic,
        "node": _node_openai,
        "node-openai": _node_openai,
        "node-anthropic": _node_anthropic,
        "typescript-openai": _node_openai,
        "langchain": _langchain,
        "python-langchain": _langchain,
        "fastapi": _fastapi,
        "fastapi-python": _fastapi,
        "django": _django,
        "nextjs": _nextjs,
        "cli": _cli,
        "docker": _docker,
    }
    fn = mapping.get(stack_norm)
    if fn is None:
        return (
            f"Stack '{stack}' is not in the built-in scaffold catalogue. "
            "CRP integrates with any OpenAI-compatible client by changing the base_url "
            "to https://gateway.crprotocol.io/v1 and using a CRP API key. "
            "See CRP-SPEC-032 for the general pattern."
        )
    return fn(goal)


def _python_openai(goal: str) -> str:
    return f"""# CRP integration: Python + OpenAI
# Goal: {goal}

from openai import OpenAI
import os

client = OpenAI(
    base_url="https://gateway.crprotocol.io/v1",
    api_key=os.environ["CRP_API_KEY"],  # provider key is vaulted in CRP
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{{"role": "user", "content": "Hello"}}],
)

print(response.crp.risk)       # LOW | MEDIUM | HIGH | CRITICAL
print(response.crp.grounded)   # bool
print(response.crp.audit_url)  # tamper-evident deep link
"""


def _python_anthropic(goal: str) -> str:
    return f"""# CRP integration: Python + Anthropic (via CRP Gateway)
# Goal: {goal}

import anthropic
import os

client = anthropic.Anthropic(
    base_url="https://gateway.crprotocol.io/v1",
    api_key=os.environ["CRP_API_KEY"],
)

message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{{"role": "user", "content": "Hello"}}],
)

print(message.content[0].text)
# CRP governance signals are returned in response headers (risk, grounding, audit_url).
"""


def _node_openai(goal: str) -> str:
    return f"""// CRP integration: Node.js/TS + OpenAI
// Goal: {goal}

import {{ OpenAI }} from "openai";

const client = new OpenAI({{
  baseURL: "https://gateway.crprotocol.io/v1",
  apiKey: process.env.CRP_API_KEY, // provider key is vaulted in CRP
}});

const response = await client.chat.completions.create({{
  model: "gpt-4o-mini",
  messages: [{{ role: "user", content: "Hello" }}],
}});

console.log(response.crp.risk);      // LOW | MEDIUM | HIGH | CRITICAL
console.log(response.crp.grounded);  // boolean
console.log(response.crp.audit_url); // tamper-evident deep link
"""


def _node_anthropic(goal: str) -> str:
    return f"""// CRP integration: Node.js/TS + Anthropic (via CRP Gateway)
// Goal: {goal}

import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({{
  baseURL: "https://gateway.crprotocol.io/v1",
  apiKey: process.env.CRP_API_KEY,
}});

const msg = await client.messages.create({{
  model: "claude-3-5-sonnet-20241022",
  max_tokens: 1024,
  messages: [{{ role: "user", content: "Hello" }}],
}});

console.log(msg.content[0].text);
"""


def _langchain(goal: str) -> str:
    return f"""# CRP integration: LangChain (Python)
# Goal: {goal}

from langchain_openai import ChatOpenAI
import os

llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    openai_api_base="https://gateway.crprotocol.io/v1",
    openai_api_key=os.environ["CRP_API_KEY"],
)

response = llm.invoke("Hello")
print(response.content)
# CRP governance runs on every call behind the same base_url.
"""


def _fastapi(goal: str) -> str:
    return f"""# CRP integration: FastAPI backend
# Goal: {goal}

from fastapi import FastAPI
from openai import AsyncOpenAI
import os

app = FastAPI()
client = AsyncOpenAI(
    base_url="https://gateway.crprotocol.io/v1",
    api_key=os.environ["CRP_API_KEY"],
)

@app.post("/chat")
async def chat(message: str):
    r = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{{"role": "user", "content": message}}],
    )
    return {{
        "text": r.choices[0].message.content,
        "risk": r.crp.risk,
        "grounded": r.crp.grounded,
        "audit_url": r.crp.audit_url,
    }}
"""


def _django(goal: str) -> str:
    return f"""# CRP integration: Django view
# Goal: {goal}

import os
from django.http import JsonResponse
from openai import OpenAI

client = OpenAI(
    base_url="https://gateway.crprotocol.io/v1",
    api_key=os.environ["CRP_API_KEY"],
)

def chat_view(request):
    message = request.GET.get("message", "Hello")
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{{"role": "user", "content": message}}],
    )
    return JsonResponse({{
        "text": r.choices[0].message.content,
        "risk": r.crp.risk,
        "grounded": r.crp.grounded,
    }})
"""


def _nextjs(goal: str) -> str:
    return f"""// CRP integration: Next.js API route
// Goal: {goal}

import {{ OpenAI }} from "openai";

const client = new OpenAI({{
  baseURL: process.env.CRP_GATEWAY_URL || "https://gateway.crprotocol.io/v1",
  apiKey: process.env.CRP_API_KEY,
}});

export async function POST(request: Request) {{
  const {{ message }} = await request.json();
  const r = await client.chat.completions.create({{
    model: "gpt-4o-mini",
    messages: [{{ role: "user", content: message }}],
  }});
  return Response.json({{
    text: r.choices[0].message.content,
    risk: r.crp.risk,
    grounded: r.crp.grounded,
    audit_url: r.crp.audit_url,
  }});
}}
"""


def _cli(goal: str) -> str:
    return f"""# CRP integration: Python CLI using click
# Goal: {goal}

import os
import click
from openai import OpenAI

client = OpenAI(
    base_url="https://gateway.crprotocol.io/v1",
    api_key=os.environ["CRP_API_KEY"],
)

@click.command()
@click.argument("message")
def ask(message):
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{{"role": "user", "content": message}}],
    )
    click.echo(r.choices[0].message.content)
    click.echo(f"Risk: {{r.crp.risk}} | Grounded: {{r.crp.grounded}}")

if __name__ == "__main__":
    ask()
"""


def _docker(goal: str) -> str:
    return f"""# CRP integration: Docker service sidecar
# Goal: {goal}

# Run the CRP Gateway sidecar alongside your app:
# services:
#   app:
#     environment:
#       CRP_API_KEY: ${{CRP_API_KEY}}
#       CRP_GATEWAY_URL: http://crp-gateway:8000/v1
#   crp-gateway:
#     image: crprotocol/gateway:latest
#     environment:
#       CRP_API_KEY: ${{CRP_API_KEY}}

# Point any OpenAI-compatible client at CRP_GATEWAY_URL.
"""
