# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRPv6 Video Kit — one self-contained HTML page that shows CRP vs raw-LLM.

This script turns the unified live demo artifact into a single HTML slide deck
you can open in a browser, screen-record, or embed in a pitch. It uses the
real live output (no hardcoded values) from LM Studio + Open-Meteo.

Run:
    python examples/crp_demos/video_kit.py

Output:
    examples/crp_demos/_video_kit.html
    examples/crp_demos/_video_kit_script.md
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
UNIFIED_JSON = SCRIPT_DIR / "_unified_demo.json"
UNIFIED_PY = SCRIPT_DIR / "unified_video_demo.py"
OUT_HTML = SCRIPT_DIR / "_video_kit.html"
OUT_SCRIPT = SCRIPT_DIR / "_video_kit_script.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_fresh_artifact() -> None:
    """Re-run the unified demo so the video kit always uses live data."""
    if UNIFIED_PY.exists():
        subprocess.run(
            [sys.executable, str(UNIFIED_PY)],
            cwd=SCRIPT_DIR,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _load_artifact() -> dict[str, Any]:
    """Load the unified demo JSON artifact."""
    if not UNIFIED_JSON.exists():
        _ensure_fresh_artifact()
    with UNIFIED_JSON.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _card(label: str, value: str, css_class: str = "") -> str:
    return f'<div class="card {css_class}"><div class="label">{label}</div><div class="value">{value}</div></div>'


def _parse_narrative_steps(narrative_md: str) -> list[dict[str, str]]:
    """Turn the narrative markdown into a list of display steps."""
    steps: list[dict[str, str]] = []
    for line in narrative_md.splitlines():
        if line.startswith("## "):
            title = line[3:].strip()
            steps.append({"title": title, "detail": ""})
        elif line.startswith("*") and "—" in line:
            kind, _, detail = line.partition("—")
            kind = kind.strip().strip("*").strip()
            detail = detail.strip()
            if steps:
                steps[-1]["kind"] = kind
                steps[-1]["detail"] = detail
    return steps


def _html_page(artifact: dict[str, Any]) -> str:
    """Build the self-contained HTML video kit."""
    raw = artifact["raw_llm"]
    crp = artifact["crp_agent_no_preset"]
    crp_pre = artifact["crp_agent_with_preset"]
    steps = _parse_narrative_steps(crp["narrative_md"])

    # Pick a short chain-of-thought subset for the timeline.
    timeline = []
    for s in steps:
        if s["title"] in {
            "Intent classified",
            "Operation: RETRIEVE",
            "Tool selected — get_weather",
            "Calling get_weather",
            "Tool result received",
            "Governance summary",
            "Final answer",
        }:
            timeline.append(s)

    def step_html(s: dict[str, str]) -> str:
        detail = s.get("detail", "")
        if detail.startswith("{"):
            detail = f'<pre class="json">{_escape(detail)}</pre>'
        else:
            detail = _escape(detail)
        return (
            f'<div class="timeline-step">'
            f'<div class="dot"></div>'
            f'<div class="step-body">'
            f'<div class="step-title">{_escape(s["title"])}</div>'
            f'<div class="step-detail">{detail}</div>'
            f'</div></div>'
        )

    timeline_html = "\n".join(step_html(s) for s in timeline)

    raw_response = _escape(str(raw["response"]))
    crp_response = _escape(str(crp["response"]))
    g = crp["governance"]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CRPv6 Live Demo — Raw LLM vs CRP Agent</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #151b2e;
      --panel-2: #1e2640;
      --accent: #00d4aa;
      --accent-2: #3b82f6;
      --text: #e8eef8;
      --muted: #94a3b8;
      --danger: #f87171;
      --warning: #fbbf24;
      --font: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: var(--font);
      background: var(--bg);
      color: var(--text);
      line-height: 1.55;
    }}
    .slide {{
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 4rem 6vw;
      border-bottom: 1px solid #ffffff10;
    }}
    h1 {{ font-size: clamp(2rem, 4vw, 3.2rem); margin: 0 0 1rem; }}
    h2 {{ font-size: clamp(1.4rem, 2.5vw, 2rem); color: var(--accent); margin: 0 0 1.5rem; }}
    h3 {{ font-size: 1.2rem; color: var(--accent-2); margin: 0 0 .75rem; }}
    p {{ max-width: 70ch; margin: .5rem 0; color: var(--muted); }}
    .lead {{ font-size: 1.25rem; color: var(--text); }}
    .split {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 2rem;
      align-items: start;
    }}
    .panel {{
      background: var(--panel);
      border-radius: 1rem;
      padding: 1.5rem;
      box-shadow: 0 10px 30px #00000040;
    }}
    .panel h3 {{ margin-top: 0; }}
    .bubble {{
      background: var(--panel-2);
      border-radius: .75rem;
      padding: 1rem;
      margin-top: .75rem;
      border-left: 4px solid var(--accent-2);
    }}
    .bubble.raw {{ border-left-color: var(--danger); }}
    pre.json {{
      background: #0d1324;
      border-radius: .5rem;
      padding: .75rem;
      overflow-x: auto;
      font-size: .9rem;
      color: #a5f3fc;
      margin: .5rem 0 0;
    }}
    .governance {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: .75rem;
      margin-top: 1rem;
    }}
    .card {{
      background: var(--panel-2);
      border-radius: .5rem;
      padding: .75rem;
      text-align: center;
    }}
    .card .label {{ font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }}
    .card .value {{ font-size: 1.1rem; font-weight: 700; margin-top: .25rem; }}
    .timeline {{
      display: flex;
      flex-direction: column;
      gap: 1rem;
      margin-top: 1rem;
    }}
    .timeline-step {{
      display: flex;
      gap: 1rem;
      align-items: flex-start;
    }}
    .dot {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--accent);
      margin-top: .4rem;
      flex-shrink: 0;
    }}
    .step-body {{ flex: 1; }}
    .step-title {{ font-weight: 700; color: var(--text); }}
    .step-detail {{ color: var(--muted); font-size: .95rem; }}
    .cta {{
      display: inline-block;
      background: var(--accent);
      color: #00110d;
      padding: .75rem 1.25rem;
      border-radius: .5rem;
      font-weight: 700;
      text-decoration: none;
      margin-top: 1rem;
    }}
    .grid-3 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.5rem;
      margin-top: 1.5rem;
    }}
    .feature {{
      background: var(--panel);
      border-radius: .75rem;
      padding: 1.25rem;
    }}
    .feature strong {{ color: var(--accent); }}
    .meta {{ font-size: .85rem; color: var(--muted); margin-top: .25rem; }}
    @media (max-width: 900px) {{
      .split {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>

<section class="slide">
  <h1>CRPv6 — Raw LLM vs Governed Agent</h1>
  <p class="lead">One question. Two paths. The difference is execution, transparency, and trust.</p>
  <p class="meta">Model: {crp["model"]} &nbsp;|&nbsp; Endpoint: {crp["endpoint"]} &nbsp;|&nbsp; Generated: {artifact["generated_at"][:19]}</p>
</section>

<section class="slide">
  <h2>The Question</h2>
  <div class="panel">
    <pre class="json">{{"role":"user","content":"{crp["question"]}"}}</pre>
  </div>
</section>

<section class="slide">
  <h2>Side-by-Side Result</h2>
  <div class="split">
    <div class="panel">
      <h3>Raw LLM</h3>
      <div class="bubble raw">
        <p><strong>Emits tool-call JSON but executes nothing.</strong></p>
        <pre class="json">{raw_response}</pre>
      </div>
      <p class="meta">Finish reason: {raw["finish_reason"]} &nbsp;|&nbsp; Elapsed: {raw["elapsed_s"]}s</p>
    </div>
    <div class="panel">
      <h3>CRPv6 Agent</h3>
      <div class="bubble">
        {crp_response}
      </div>
      <div class="governance">
        {_card("Risk", g["risk"])}
        {_card("Grounded", str(g["grounded"]))}
        {_card("Chain valid", str(g["chain_valid"]))}
        {_card("Sources", str(g["sources"]))}
        {_card("Elapsed", f"{crp['elapsed_s']}s")}
      </div>
    </div>
  </div>
</section>

<section class="slide">
  <h2>What CRP Did — Chain of Thought</h2>
  <div class="timeline">
    {timeline_html}
  </div>
</section>

<section class="slide">
  <h2>Cognitive Preset — research_assistant</h2>
  <div class="split">
    <div class="panel">
      <h3>Same tool, same question, governed preset</h3>
      <div class="bubble">
        {_escape(str(crp_pre["response"]))}
      </div>
      <div class="governance">
        {_card("Risk", crp_pre["governance"]["risk"])}
        {_card("Grounded", str(crp_pre["governance"]["grounded"]))}
        {_card("Sources", str(crp_pre["governance"]["sources"]))}
      </div>
    </div>
    <div class="panel">
      <h3>Preset provides</h3>
      <ul>
        <li>Declarative reasoning phases</li>
        <li>Safeguards with warn/ask/halt actions</li>
        <li>Output tone and format expectations</li>
        <li>Emotion/affect hooks</li>
      </ul>
    </div>
  </div>
</section>

<section class="slide">
  <h2>Why CRPv6</h2>
  <div class="grid-3">
    <div class="feature"><strong>User-defined reasoning</strong><br/>Presets turn your thinking style, rules, and safeguards into runtime structure.</div>
    <div class="feature"><strong>Live transparency</strong><br/>Every intent, tool call, result, and governance check streams as AG-UI + CRP events.</div>
    <div class="feature"><strong>Provable provenance</strong><br/>Per-window HMAC chain links every step into a tamper-evident audit trail.</div>
    <div class="feature"><strong>Model-agnostic</strong><br/>Identical governance contract on LM Studio, OpenAI, Anthropic, or Kimi.</div>
    <div class="feature"><strong>Real tools, no ceremony</strong><br/>Plain Python functions become capabilities; MCP bridge is optional.</div>
    <div class="feature"><strong>Quality gate proven</strong><br/>Full SQB benchmark passes against Kimi with all five gate criteria.</div>
  </div>
</section>

<section class="slide">
  <h2>Get Started</h2>
  <p class="lead">Install the SDK and run the same live demo yourself.</p>
  <pre class="json">pip install crprotocol
python examples/crp_demos/unified_video_demo.py</pre>
  <p><a class="cta" href="https://pypi.org/project/crprotocol/6.1.1/">View on PyPI</a></p>
</section>

</body>
</html>
"""


def _presenter_script(artifact: dict[str, Any]) -> str:
    """Return a short Markdown script for narrating the video."""
    q = artifact["question"]
    raw = artifact["raw_llm"]
    crp = artifact["crp_agent_no_preset"]
    return f"""# CRPv6 Video Presenter Script

## Hook (0–10s)
Every AI agent can answer. But can it show you how it decided? Can it carry your rules and reasoning across every tool it uses?

## The Question (10–15s)
User asks: “{q}”

## Raw LLM (15–30s)
The raw LLM emits this but does nothing:

```json
{raw["response"]}
```

No execution. No sources. No audit trail.

## CRPv6 Agent (30–55s)
CRP classifies intent, selects the weather tool, executes it against Open-Meteo, and returns a grounded answer:

> {crp["response"]}

Governance: risk={crp["governance"]["risk"]}, grounded={crp["governance"]["grounded"]}, chain_valid={crp["governance"]["chain_valid"]}, sources={crp["governance"]["sources"]}

## Chain of Thought (55–80s)
Walk through the narrative: intent → operation → tool selected → tool call with arguments → tool result → quality tier → governance summary → final answer.

## Presets (80–100s)
The same question with the `research_assistant` preset shows that users can define reasoning phases, safeguards, tone, and output format in simple YAML.

## Closing (100–120s)
CRPv6 is live on PyPI. Build agents that think the way you want, and show your users exactly why.
"""


def main() -> int:
    _ensure_fresh_artifact()
    artifact = _load_artifact()

    html = _html_page(artifact)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote video kit HTML: {OUT_HTML}")

    script = _presenter_script(artifact)
    OUT_SCRIPT.write_text(script, encoding="utf-8")
    print(f"Wrote presenter script: {OUT_SCRIPT}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
