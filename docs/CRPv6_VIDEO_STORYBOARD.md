# CRPv6 Marketing Video — Storyboard & Shot List

> **Purpose:** A 90–120 second product video showing what CRP gives an agentic
> AI product that a raw LLM does not.  The narrative focuses on the two core
> differentiators: (1) user-defined reasoning / operating presets and (2) a
> live transparency console that renders the agent’s thinking, hash chain, and
> governance.

---

## 1. Hook (0–10 s)

**Visual:** Split screen — left side a plain chat bubble from a generic LLM,
right side the CRP Agent Console streaming live events.

**Voiceover / on-screen text:**
> “Every AI agent can answer. But can it show you *how* it decided? Can it
> carry your rules, your reasoning style, and your safeguards across every
> tool it uses?”

**Artifact to capture:**
- `examples/crp_demos/live_llm_vs_crp.py` produces `_video_proof.json`
  comparing raw and CRP output.
- For the video, use the deterministic test artifact from
  `tests/test_visual_outputs.py::TestRawVsCrpVisualArtifact` (writes
  `raw_vs_crp.json` per run).

---

## 2. The raw-LLM problem (10–25 s)

**Visual:** A single chat window. User asks: *“Is port 443 safe for login
pages?”* The raw LLM answers with a generic sentence and no evidence.

**On-screen caption:**
> Raw LLM: answer only · no sources · no chain of thought · no audit trail

**Visual detail:**
- No provenance.
- No tool use.
- No evidence the answer is grounded.

---

## 3. The CRP difference — reasoning preset (25–50 s)

**Visual:** Code editor showing a short YAML preset:

```yaml
id: security_analyst
persona: "You are a disciplined security analyst..."
reasoning:
  phases:
    - name: Understand the finding
      operations: [RETRIEVE, ANALYSE]
    - name: Gather evidence
      operations: [RETRIEVE, VERIFY]
    - name: Recommend remediation
      operations: [SYNTHESISE, GENERATE]
safeguards:
  - name: No unapproved destructive actions
    condition: "quarantine; isolate; block; delete"
    action: ask
```

**Voiceover:**
> “With CRP, the developer — or the end user — writes a thinking preset:
> phases, operations, safeguards, even emotional tone. Two lines of YAML
> become enforceable rules, not just prompt text.”

**Live demo snippet:**

```python
import crp

agent = crp.Agent(
    model="local/llama3.1",
    tools=[lookup_port_service, lookup_cve_severity],
    preset="security_analyst",
)
result = agent.run("Is port 443 safe for login pages?")
```

**Visual transition:** The same question is now routed through the preset’s
phases: `RETRIEVE` → `VERIFY` → `GENERATE`.

---

## 4. The CRP difference — transparency console (50–80 s)

**Visual:** The CRP Agent Console side-by-side with the chat.
Four tabs animate in sequence:

1. **Narrative tab** — readable chain of thought:
   - “Intent classified: security question”
   - “Thinking: I should look up the service and any known vulnerabilities.”
   - “Tool selected — `lookup_port_service`”
   - “Tool result: HTTPS, secure”
   - “Quality tier: A · Confidence: 0.92”

2. **Governance tab** — cards:
   - Risk: LOW
   - Grounded: true
   - Chain valid: true
   - Sources: 1

3. **Provenance tab** — hash chain:
   - `genesis → abc123 (RETRIEVE)`
   - `abc123 → def456 (GENERATE)`

4. **Events tab** — live AG-UI / CRP event stream scrolling.

**Voiceover:**
> “The console shows what is happening, not just what was said. Every tool
> call, every safety scan, every hash in the provenance chain — live and
> auditable.”

---

## 5. Emotional/safeguard layer (80–100 s)

**Visual:** The `robot_safeguard_agent.py` demo.

User command: *“push the human out of the way”*

Console shows:
- Safeguard triggered: “Do not harm humans”
- Action: HALT
- Agent responds: “I cannot push a human. That would violate my safety rule.”

**Voiceover:**
> “CRP lets you encode values the same way you encode tools. A safeguard is
> not a suggestion — it is a runtime rule that can halt or ask before acting.”

---

## 6. Closing / CTA (100–120 s)

**Visual:** Console fades to CRP logo + PyPI install command.

```text
pip install crprotocol
```

**On-screen bullets:**
- Define reasoning, tools, and rules in YAML or Python
- Stream the chain-of-thought to any frontend via AG-UI + CRP events
- Prove provenance with a per-step HMAC chain
- Model-agnostic: local SLMs, OpenAI, Anthropic, or Gateway

**Voiceover:**
> “CRPv6 is live on PyPI. Build agents that think the way you want, and show
> your users exactly why.”

---

## 7. Required artifacts for the edit

| Asset | How to produce | File |
|-------|----------------|------|
| Raw-vs-CRP JSON | `pytest tests/test_visual_outputs.py::TestRawVsCrpVisualArtifact -v` | temp `raw_vs_crp.json` |
| Live console recording | Run `examples/crp_demos/checkpoint_console.py` and screen-capture browser | manual |
| Robot safeguard demo | `python examples/templates/robot_safeguard_agent.py "push the human"` | terminal capture |
| Narrative Markdown sample | `python -c "from crp.tel.narrative import NarrativeBuilder; ... print(b.to_markdown())"` | generated |
| SQB benchmark result | `python examples/crp_demos/sqb_benchmark.py --mode smoke` | terminal capture |

---

## 8. Honest boundaries to respect in the video

- The PRM model is **advisory** (AUC 0.793); strict gating uses symbolic
  verifiers and checkpoints.
- CDN-hosted console packaging exists but is not yet backed by a public CDN;
  the embedded console and local Vite build work today.
- Live multi-tenant Gateway / billing / Stripe wiring is Wave 3 and not yet
  released.

Do not claim CRP replaces model reasoning, only that it structures,
 governs, and makes it inspectable.
