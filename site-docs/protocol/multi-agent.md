# Multi-Agent Safety

<div class="cr-hero" markdown>

## Stop runaway agent chains before they exceed governance limits

When AI agents call other AI agents, risk accumulates. CRP defines a
**chain budget** and **circuit breaker** that observe the whole chain, not just
each call, so multi-agent systems stay inside your safety envelope.

</div>

<span class="cr-badge cr-badge-live">Self-hosted today</span>
<span class="cr-badge cr-roadmap">Managed-cloud waitlist for Gateway and Comply; more endpoints on the roadmap</span>

## The Problem

Three agents chained together can each individually pass safety thresholds
yet produce a combined output whose aggregate hallucination probability is
unacceptable. The protocol must observe the chain, not just each call.

## The Mechanism

Every agent-to-agent call carries:

```http
CRP-Chain-Id: 0d2f7a09-…
CRP-Chain-Step: 3
CRP-Chain-Budget: max-risk=0.20; max-steps=8; max-tokens=180000
CRP-Risk-Accumulator: 0.14
```

When `Risk-Accumulator` would exceed the budget on the next step, the
gateway returns `409 Conflict` with `CRP-Safety-Verdict: CIRCUIT-BREAK`.

## From the SDK

```python
import crp

# A stricter safety profile lowers the multi-agent risk budget.
client = crp.SDKClient(safety_profile="strict")
client.configure(safety_profile="strict")

response = client.complete("Coordinate a three-agent research workflow.")
print(response.crp.risk)
print(response.crp.safety_budget_remaining)
```

## Interaction with MCP / A2A

CRP layers cleanly under MCP (tool calling) and A2A (agent communication):

<div class="cr-compare" markdown>
<div class="cr-card" markdown>

### A2A
Who calls whom - agent discovery and intent routing.

</div>
<div class="cr-card" markdown>

### MCP
What tools to use - model context protocol servers.

</div>
<div class="cr-card" markdown>

### CRP
Chain budget, risk accumulator, and audit chain.

</div>
</div>

[:octicons-arrow-right-24: SPEC-012 normative text](../spec/CRP-SPEC-012-multi-agent-safety.md)
