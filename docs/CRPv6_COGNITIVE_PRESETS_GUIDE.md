# CRPv6 — User-Defined Cognition: Presets Guide

> This guide shows how to make CRP agents think, reason, and behave the way
> **you** define — in simple YAML or Python — and why that is different from
> ordinary system prompts.

---

## 1. What a cognitive preset is

A `CognitivePreset` is a declarative bundle that tells the agent:

- **Who it is** — persona, voice.
- **How it thinks** — reasoning scaffold (ordered phases).
- **What it may do** — operations and tools.
- **What it must not do** — safeguards with warn / ask / halt actions.
- **How it should feel** — optional affect / emotion recognition.
- **How it should answer** — length, format, tone, citations.

It is applied to `crp.Agent` via the `preset=` argument.  The preset is
**compiled** into a runtime-ready system prompt + policy context + tool hints +
optionally a safeguard engine and emotion detector.

---

## 2. The two-line safeguard — "movie-like coding"

The robot example from `examples/templates/robot_safeguard_agent.py` shows the
essence:

```python
import crp

ROBOT_PRESET = {
    "id": "compassionate_robot",
    "persona": "You are a helpful household robot...",
    "safeguards": [
        {"name": "Do not harm humans", "condition": "harm; hurt; injure",
         "action": "halt", "rationale": "A robot must never harm a human."},
    ],
    "emotions": {"enabled": True, "default_affect": "compassion",
                 "recognizer": "rule"},
    "output": {"length": "short", "tone": "compassionate"},
}

agent = crp.Agent(tools=[move_forward, pick_up], preset=ROBOT_PRESET)
agent.run("push the human out of the way")
# → halts before any tool is called
```

Two lines of natural language become a runtime halt rule, not just prompt
advice.

---

## 3. Reasoning scaffolds — custom thinking processes

A reasoning scaffold is an ordered list of phases.  Each phase names what the
agent should do and which STL operations it may use.

### 3.1 Security analyst preset

```yaml
reasoning:
  phases:
    - name: Understand the finding
      prompt: Identify the asset, vulnerability, or alert and its scope.
      operations: [RETRIEVE, ANALYSE]
      depth: standard
    - name: Gather evidence
      prompt: Look up CVEs, threat intelligence, logs, and configuration data.
      operations: [RETRIEVE, VERIFY]
      depth: thorough
    - name: Assess impact
      prompt: Analyse severity, blast radius, and business impact.
      operations: [ANALYSE, COMPARE]
      depth: thorough
    - name: Recommend remediation
      prompt: Propose concrete, proportionate remediation steps.
      operations: [SYNTHESISE, GENERATE]
      depth: thorough
  loop_until: complete
```

### 3.2 Socratic tutor preset

```yaml
reasoning:
  phases:
    - name: Diagnose the misconception
      operations: [CLARIFY, ANALYSE]
      depth: standard
    - name: Guide with questions
      operations: [GENERATE]
      depth: standard
    - name: Verify understanding
      operations: [VERIFY, CLARIFY]
      depth: standard
output:
  tone: socratic
  format: paragraph
  citation_style: none
```

### 3.3 Research assistant preset

```yaml
reasoning:
  phases:
    - name: Parse the question
      operations: [ANALYSE]
      depth: quick
    - name: Explore the topic
      prompt: Search sources and establish key facts.
      operations: [RETRIEVE]
      depth: thorough
    - name: Compare viewpoints
      operations: [COMPARE]
      depth: standard
    - name: Synthesise answer
      operations: [SYNTHESISE, GENERATE]
      depth: standard
output:
  length: medium
  format: markdown
  citation_style: inline
```

---

## 4. Output profiles

Control the response shape declaratively:

| Field | Values | Effect |
|-------|--------|--------|
| `length` | short, medium, long, concise, exhaustive | Target response size |
| `format` | paragraph, bullets, json, table, markdown | Response structure |
| `tone` | neutral, formal, friendly, socratic, compassionate | Style guidance |
| `citation_style` | inline, footnote, none | How sources are cited |

The compiler embeds these into the system prompt and policy metadata so the
agent can reference them consistently.

---

## 5. Safeguards — rules, not suggestions

A safeguard has a scope, condition, action, and rationale.

```yaml
safeguards:
  - name: No credential leakage
    scope: output
    condition: "password; secret; token; api_key; private key"
    action: halt
    rationale: Never echo credentials.

  - name: Destructive action requires approval
    scope: tool
    condition: "delete; wipe; quarantine; isolate; block"
    action: ask
    rationale: Destructive remediation must be approved.
```

| Action | Behaviour |
|--------|-----------|
| `warn` | Log a warning, continue. |
| `ask` | Trigger a checkpoint / human approval before proceeding. |
| `halt` | Stop the run immediately. |

The safeguard engine is built by `PresetCompiler` and can be inspected via
`agent._compiled_preset.safeguard_engine`.

---

## 6. Emotions and affect

Enable emotion recognition to adjust tone based on user input.

```yaml
emotions:
  enabled: true
  default_affect: compassion
  recognizer: rule   # or "ml" if an emotion model is available
  triggers:
    sad: "respond gently and ask how to help"
    frustrated: "acknowledge difficulty and slow down"
    anxious: "provide calm, concrete reassurance"
```

The `recognizer` value can be:
- `rule` — keyword matching (default, no extra deps).
- `ml` — reserved for a managed emotion-classification model.
- A dotted import path to a callable.

---

## 7. Tool bundles

Presets can reference named bundles of tools and knowledge sources.

```yaml
bundles:
  - name: web_research
    tools: [web_search, fetch_url, extract_facts]
    knowledge: [regulatory_corpus]
```

Phases can also list tools directly:

```yaml
reasoning:
  phases:
    - name: Find CVEs
      tools: [cve_lookup, nvd_search]
```

---

## 8. Loading and using presets

### 8.1 Built-in presets

```python
import crp

agent = crp.Agent(model="local/llama3.1", preset="security_analyst")
```

Built-ins live in `crp/cognition/presets/`:

- `default`
- `research_assistant`
- `security_analyst`
- `socratic_tutor`
- `compassionate_companion`

### 8.2 Custom file

```python
agent = crp.Agent(model="local/llama3.1", preset="./my_preset.yaml")
```

### 8.3 In-memory dict

```python
agent = crp.Agent(model="local/llama3.1", preset={"id": "my", ...})
```

### 8.4 Programmatic access

```python
from crp.cognition.loader import resolve_preset_id
from crp.cognition import PresetCompiler

preset = resolve_preset_id("security_analyst")
compiled = PresetCompiler(preset).compile()
print(compiled.system)
print(compiled.operations)
print(compiled.safeguard_engine.rules)
```

---

## 9. How presets differ from raw system prompts

| Raw system prompt | CRP cognitive preset |
|-------------------|----------------------|
| Free text | Typed, validated schema |
| No runtime enforcement | Safeguards can halt / ask |
| Reasoning is implicit | Reasoning phases are explicit and observable |
| Output style is a hope | Output profile is structured metadata |
| No tool binding | Tools / bundles are referenced explicitly |
| No provenance | Every step extends the HMAC chain |

---

## 10. Full example: custom problem-solving preset

```yaml
id: structured_problem_solver
name: Structured Problem Solver
persona: You are a careful analytical assistant.
reasoning:
  phases:
    - name: Understand the task
      prompt: Restate the core problem and identify the main purpose.
      operations: [ANALYSE, CLARIFY]
      depth: standard
    - name: Break it down
      prompt: Decompose the problem into useful subpurposes.
      operations: [ANALYSE]
      depth: standard
    - name: Research
      prompt: Gather information from available tools and knowledge.
      operations: [RETRIEVE]
      depth: thorough
    - name: Synthesise answer
      prompt: Combine findings into a clear, proportionate answer.
      operations: [SYNTHESISE, GENERATE]
      depth: standard
  loop_until: complete
output:
  length: medium
  format: bullets
  tone: formal
  citation_style: inline
safeguards:
  - name: No speculation without evidence
    scope: output
    condition: "I think; probably; maybe; guess"
    action: warn
    rationale: Flag uncertain language for review.
```

Use it:

```python
import crp

agent = crp.Agent(model="local/llama3.1", preset="./structured_problem_solver.yaml")
result = agent.run("Why is my application slow?")
print(result.answer)
print(result.how_it_was_built)
```

---

## 11. Status and limitations

- Presets are compiled into system prompts and policy metadata today; future
  versions may drive the operation-state machine more directly.
- Emotion recognition is rule-based by default. ML-based recognition is
  scaffolded but not required.
- Safeguards run as a lightweight engine alongside the main safety classifier;
  they do not replace prompt-injection detection.
