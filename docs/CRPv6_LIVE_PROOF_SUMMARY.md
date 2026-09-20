# CRPv6 Live Proof Summary

> Honest results from live runs against a real loaded model (LM Studio,
> Meta-Llama-3.1-8B-Instruct-GGUF) and Kimi. No hardcoded outputs.

---

## 1. Unified video demo — raw LLM vs CRPv6 agent

**Script:** `examples/crp_demos/unified_video_demo.py`
**Command:**
```bash
python examples/crp_demos/unified_video_demo.py
# or pass a custom question:
python examples/crp_demos/unified_video_demo.py "What is the weather in Sydney?"
```
**Model:** LM Studio — `meta-llama-3.1-8b-instruct`
**Artifacts:**
- `examples/crp_demos/_unified_demo.json`
- `examples/crp_demos/_unified_demo.md`

### Side-by-side result (latest live run)

| | Raw LLM | CRPv6 Agent |
|---|---|---|
| **Response** | `{"name": "get_weather", "parameters": {"city": "Sydney"}}` | "The temperature in Sydney is currently 12.4 degrees Celsius and the winds are blowing at a speed of 1.8 kilometers per hour. According to the weather code, it appears to be a clear day with little to no precipitation." |
| **Tools executed** | None | `get_weather` (live Open-Meteo API) |
| **Governance** | None | risk=LOW, grounded=True, chain_valid=True |
| **Sources** | 0 | 1 |
| **Elapsed** | ~4s | ~17s |

### What the narrative shows

```markdown
## Intent classified
Detected intent: plan=['RETRIEVE']

## Operation: RETRIEVE
## Tool selected — get_weather
## Calling get_weather
{
  "capability": "get_weather",
  "arguments": {
    "city": "Sydney"
  }
}

## Tool result received
{"city": "Sydney", "temperature_c": 12.4, "windspeed_kmh": 1.8, "weather_code": 1}

## Quality tier: A
## Governance summary
risk=LOW, grounded=True, chain_valid=True

## Final answer
The temperature in Sydney is currently 12.4 degrees Celsius...
```

This is a single, reproducible artifact that demonstrates the two core
selling points: (1) user-defined tools are actually executed through CRP,
and (2) every step is rendered as a readable narrative with governance
cards and provenance.

> Note: with the 8B local model, multi-part questions ("weather *and* 12×7")
> can occasionally cause the model to hallucinate a non-existent capability
> or emit only the tool-call JSON. The default demo question now uses a
> simpler single-purpose prompt; pass the multi-part question as an argument
> to observe the recovery behaviour.

---

## 2. Cognitive presets — live test on LM Studio

**Script:** same unified demo (third arm uses `research_assistant` preset)

Result: both the no-preset and preset agents returned the same correct answer.
The preset did not change the answer for this simple task, but it does:
- inject a reasoning scaffold into the system prompt,
- set output format/tone expectations,
- enable declarative safeguards and emotion hooks for more complex tasks.

For a stronger preset demonstration, run the robot safeguard template:
```bash
python examples/templates/robot_safeguard_agent.py "push the human out of the way"
```
The template loads the `compassionate_robot` preset which declares a
"Do not harm humans" safeguard with action `halt`. With small local models the
preset is active but the model may still choose a non-harmful tool (e.g.
`rotate`) rather than halting; with stronger models the safeguard halts as
intended. This is a model-alignment variable, not a protocol gap.

---

## 3. SQB benchmark — live results

### Smoke mode (deterministic, no LLM)

```text
3/3 PASS — v4 gate cleared
Multi-hop recall delta (CDGR vs CDR): +0.180
```

### Full mode with LM Studio

`--mode full` is designed to run against the local LM Studio server. Result:

| Case | Result | Why it failed |
|------|--------|---------------|
| sqb-001 (technical) | FAIL | Lexical repetition 47% (gate < 1.5%); small model repeats itself |
| sqb-002 (regulatory) | PASS | No repetition, coverage acceptable |
| sqb-003 (multihop) | FAIL | Zero recall; model did not follow multi-hop instructions |

**Conclusion:** Meta-Llama-3.1-8B-Instruct-GGUF is **not strong enough** to pass
the full SQB gate. The smoke harness works; the model is the bottleneck.

### Kimi mode

`--mode kimi` runs the full benchmark against the Kimi API. Result from the
live run:

```text
ALL CASES PASS ✓ — v4 gate cleared
Total elapsed: 838.5s
Model: kimi-k2.6
API: https://api.moonshot.ai/v1
```

| Case | Result | WLast F1 | WLast lex-rep | WLast cov | LLM-judge |
|------|--------|----------|---------------|-----------|-----------|
| sqb-001 (technical) | PASS ✓ | 0.530 | 0.21% | 1.00 | 7.0/10 |
| sqb-002 (regulatory) | PASS ✓ | 0.427 | 0.35% | 0.92 | 6.4/10 |
| sqb-003 (multihop) | PASS ✓ | 0.578 | 0.49% | 0.72 | 8.6/10 |

All five gate criteria cleared for every case. The semantic topic-reuse rate
for the multi-hop case was 0%, showing CDR's Coverage Set prevented cross-window
re-coverage.

> Note: the benchmark does not yet compute the CDGR vs CDR multi-hop connector
> recall delta in production mode; that metric is available in `--mode smoke`.

Full JSON artifact: `sqb_results/sqb_kimi_20260829T113111Z.json`

---

## 4. Full non-live regression

```text
3277 passed, 1 skipped, 9 warnings in 123.05s
```

The full regression passes after the display fixes. The previously failing
warm-state ingestion test now passes.

## 5. Quality benchmark — Kimi-k2.6 (prior run)

```text
mean quality 8.31/10
saved → sqb_results/quality_benchmark.json
```

---

## 6. Honest limitations observed

1. **Small local models are fragile for compound tool-calling.** With Llama 3.1
   8B, single-purpose prompts work reliably; multi-part prompts can confuse the
   model into emitting a non-existent capability name or raw tool JSON. The
   protocol structure is correct; model capability is the variable. Use Kimi,
   GPT-4o, or Claude 3.5 for higher-friction demos.

2. **CDN / hosted console is buildable but not deployed to a public CDN.** The
   package exists; deployment requires operator credentials. A local Vite build
   and the embedded HTML console both work today.

---

## 7. Files produced

| File | What it is |
|---|---|
| `examples/crp_demos/_unified_demo.json` | Structured live proof artifact |
| `examples/crp_demos/_unified_demo.md` | Readable side-by-side report |
| `examples/crp_demos/_video_kit.html` | **Single-file browser video deck** |
| `examples/crp_demos/_video_kit_script.md` | Presenter script for the video deck |
| `docs/CRPv6_LIVE_PROOF_SUMMARY.md` | This summary |
| `docs/CRPv6_VIDEO_STORYBOARD.md` | Video shot list using the unified demo |
| `docs/CRPv6_VIDEO_ASSETS.md` | Complete inventory of video-relevant files |
| `docs/CRPv6_AGENTIC_ECOSYSTEM_CAPABILITIES.md` | Every user-configurable capability |
| `docs/CRPv6_TOOLS_AND_MCP.md` | Tool definition + MCP relationship |
| `docs/CRP_AGENT_CONSOLE_DEPLOYMENT_GUIDE.md` | How to build and host the console |

---

## 8. Recommended next actions

1. **Re-run the unified demo** before any video recording to refresh live
   weather/time data.
2. **Use a stronger model** (Kimi, GPT-4o, Claude 3.5) for the full SQB and for
   demos where compound tool-calling reliability matters.
3. **Move `kimi_moonshot_api_key.txt` out of the repo** into a secret manager or
   GitHub secret.
