# CRPv6 Video Presenter Script

## Hook (0–10s)
Every AI agent can answer. But can it show you how it decided? Can it carry your rules and reasoning across every tool it uses?

## The Question (10–15s)
User asks: “Compare the weather in Tokyo and New York using real data.”

## Raw LLM (15–30s)
The raw LLM emits this but does nothing:

```json
{"name": "get_weather", "parameters": {"city1": "Tokyo", "city2": "New York"}}
```

No execution. No sources. No audit trail.

## CRPv6 Agent (30–55s)
CRP classifies intent, selects the weather tool, executes it against Open-Meteo, and returns a grounded answer:

> In Tokyo, the current temperature is a warm 28.2 degrees Celsius and the wind speed is relatively low at 4.3 kilometers per hour. The weather in Tokyo is currently clear or partly cloudy, indicated by a weather code of 2. In contrast to Tokyo's pleasant weather, we do not have any information about the current weather conditions in New York.

Governance: risk=LOW, grounded=True, chain_valid=True, sources=1

## Chain of Thought (55–80s)
Walk through the narrative: intent → operation → tool selected → tool call with arguments → tool result → quality tier → governance summary → final answer.

## Presets (80–100s)
The same question with the `research_assistant` preset shows that users can define reasoning phases, safeguards, tone, and output format in simple YAML.

## Closing (100–120s)
CRPv6 is live on PyPI. Build agents that think the way you want, and show your users exactly why.
