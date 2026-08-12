# CRP v3 — LinkedIn Launch Series

A 4-post sequence introducing the Context Relay Protocol. Post them a few days apart.
Hashtags and a call-to-action are included; trim to taste.

---

## Post 1 — The problem (hook)

**We let LLMs into production without a seatbelt. CRP is the seatbelt.**

Every team shipping AI features hits the same wall:

→ How do you *prove* an answer was grounded in your data and not hallucinated?
→ How do you stop prompt injection before it reaches the model?
→ How do you show a regulator what your AI actually did — and that the logs weren't edited?

Today most of this is handled by vibes, a system prompt, and hope.

I built the **Context Relay Protocol (CRP)** to fix that. It's a governance layer that
sits between your app and *any* LLM — local or hosted — and answers three questions on
every single call:

**What model is running? · Is this output safe to release? · Can we prove what happened?**

Over the next few posts I'll show CRP v3 doing exactly that — against a real model
running on my own laptop, with nothing in the cloud.

#AI #AISafety #LLM #AIGovernance #MLOps

---

## Post 2 — The "it detects the model" moment

**Before CRP sends a single token, it already knows everything about the model it's about to govern.**

Most "AI safety" tooling treats the model as a black box. CRP doesn't.

I pointed CRP at LM Studio running on my machine. With zero configuration it detected
**every** local runtime and, for each model, resolved:

• architecture + quantization (e.g. Llama, Q4_K_M)
• the **true** context ceiling vs. the window actually loaded (131,072 max → only 4,096 loaded = 3.1% utilised)
• tool-calling support
• whether it's a reasoning model

Why does this matter? Because you can't govern what you can't see. Knowing the real
context budget is what lets CRP decide *when* to compress, when to halt, and how much
to trust the output.

This works across LM Studio, Ollama, llama.cpp and any OpenAI-compatible endpoint — and
it's pure standard-library code, no heavyweight SDK.

Next: what happens when the model says something it shouldn't.

#LLM #AIInfrastructure #LocalLLM #AISafety

---

## Post 3 — Enforcement, not advice (the HTTP 451 moment)

**Most guardrails *score* a bad answer. CRP *refuses* it.**

I gave a local Llama-3.1-8B model a question it had no grounding to answer, under this
one-line CRP safety policy:

`default-src context; halt-on CRITICAL; require-grounding 0.90`

CRP ran the model, scored the answer's grounding and hallucination risk, checked it
against the policy — and returned **HTTP 451** with a machine-readable halt reason
(`UNACCEPTABLE_EU_AI_ACT`) and an *oversight-required* flag.

The unsafe answer never reached the caller.

That's the difference between a dashboard and a control plane:

✅ Prompt-injection shield catches `instruction_override` / `exfil_secret` on the way in
✅ Decision Provenance Engine scores grounding, fabrications, distortions, quality tier
✅ Policy enforcement halts with a standards-aligned HTTP status
✅ Every step written to a hash-chained audit trail (exports to OCSF & SARIF)

All of it observable on the wire as `CRP-*` headers, so a gateway can enforce it even
for apps that aren't CRP-aware.

#AIGovernance #EUAIAct #AISafety #Compliance #LLMOps

---

## Post 4 — Proof, memory & availability (the close)

**If you can't prove it didn't happen, you can't prove it did. CRP makes AI tamper-evident.**

Final piece of the CRP v3 story: **provenance you can verify.**

In a multi-turn chat with a local model, CRP:

• extracted facts into a Contextual Knowledge Fabric and **recalled them on later turns**
  — the model correctly remembered "CRP for AI governance" from an earlier window,
  without replaying the whole transcript
• chained every conversation window with an **HMAC**
• and when I deliberately *tampered* with an earlier window, the chain instantly flipped
  to **BROKEN — at exactly the window I edited**

That's tamper-evidence you can hand to a security team or an auditor.

**CRP v3 is complete and enforceable today.** It's available:

📦 As a library: `pip install crprotocol`
🔌 As an open protocol: the `CRP-*` header + policy + HTTP 451 contract, implementable in any stack
🧪 As two runnable demo apps that govern a real local LLM in your browser

If you're shipping LLM features and need detection, grounding, enforcement and
tamper-evident audit in one layer — take a look. Links in the comments. 👇

#AI #AISafety #AIGovernance #LLM #OpenSource #MLOps
