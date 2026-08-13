# CRPv6 Wave 2 — Protocol Launch Readiness

CRPv6 Wave 2 is the open-source protocol launch wave. It proves that a small local language model can execute real tools, call live public APIs, and emit runtime governance metadata — all without a cloud provider or paid API key.

---

## What Wave 2 proves

| Proof | How to run it | What you see |
|-------|---------------|--------------|
| Live public API agent | `examples/agents/real_world_research_agent.py` | Weather, crypto price, and Wikipedia answers in natural language |
| Raw LLM vs. CRPv6 | `examples/crp_demos/live_real_world_api_proof.py` | Raw JSON tool request next to executed CRP answer + governance |
| Non-live test gate | `pytest tests/ -q --tb=short` | 3232+ tests pass |
| ML-first foundation | `scripts/eval_crp_intent_setfit.py` etc. | Published AutoCyberAI models with reported metrics |

---

## Live public API demos

Both demos use these free, no-key public endpoints:

- **Open-Meteo** — live weather
- **CoinGecko** — live cryptocurrency prices
- **Wikipedia REST** — article summaries
- **Nominatim** — geocoding (used internally by the weather tool)

### Run the research agent

```powershell
set CRP_LMSTUDIO_URL=http://localhost:1234/v1
set CRP_LMSTUDIO_MODEL=meta-llama-3.1-8b-instruct
python examples/agents/real_world_research_agent.py
```

### Run the side-by-side proof

```powershell
set CRP_LMSTUDIO_URL=http://localhost:1234/v1
set CRP_LMSTUDIO_MODEL=meta-llama-3.1-8b-instruct
python examples/crp_demos/live_real_world_api_proof.py
```

---

## What CRPv6 emits

Every Agent run returns:

| Field | Meaning |
|-------|---------|
| `result.answer` | Natural-language answer |
| `result.crp.risk` | Per-run risk tier |
| `result.crp.grounded` | `True` when backed by a tool observation |
| `result.crp.chain_valid` | HMAC audit-chain status |
| `result.operations` | STL operations used |
| `result.sources` | Tool observations with provenance |

These are computed at runtime, not hardcoded.

---

## Launch checklist

- [ ] `pip install -e . --no-deps` in the demo environment
- [ ] LM Studio loaded with an 8B instruct model
- [ ] Real-API demo runs end-to-end
- [ ] Test suite passes
- [ ] Site builds with `mkdocs build --strict`
- [ ] GitHub branch protection enabled
- [ ] PyPI token rotated if exposed
- [ ] LinkedIn campaign ready

---

## What comes next (Wave 3)

Wave 3 is the managed-cloud and money-funnel layer: Gateway hardening, Comply upgrade, Scan remediation, Stripe + Clerk webhooks, and self-serve product docs. Wave 3 can proceed in parallel with the protocol launch campaign.

For the complete public runbook, see the [Public Demo & Test Guide](CRPv6_PUBLIC_DEMO_AND_TEST_GUIDE.md).  
For the one-take video script, see the [Video Demo Guide](CRPv6_VIDEO_DEMO_GUIDE.md).
