# CRPv6 — Text-to-Video Generation Prompt Pack

> Purpose: feed these prompts into your video generator (Runway / Pika / Sora / Kling /
> Pictory / whatever you use) to produce launch graphics. Two truths before you generate:
> 1. **Text-to-video models cannot render a real product UI faithfully.** Generate the
>    *abstract mechanism graphics* with AI, then **overlay real screen capture** of the
>    Agent Console (`console.crprotocol.io` connected to a local backend) for authenticity.
>    The mix of motion graphics + real footage is what reads as "real product".
> 2. Keep every claim below — they are all verified functionality of 6.1.1. Do not let the
>    generator invent capabilities.

---

## MASTER PROMPT (90-second explainer, abstract motion-graphics style)

```
A premium, dark-themed technology explainer animation, clean vector motion-graphics style
with soft neon-blue and cyan accents on deep navy. No photorealistic humans; abstract
geometric forms only. Smooth 60fps easing, shallow depth of field, subtle grid backdrop
suggesting a circuit of intelligence.

SEQUENCE:
1. OPEN (0-8s): A single glowing rectangle — a "context window" — floating in dark space.
   It fills up rapidly with chaotic overlapping text shards that glow red as they collide.
   On-screen text: "Every AI call shares one window. Everything competes. Nothing is checked."
2. THE RELAY (8-20s): The chaotic window splits into many clean, separate glowing frames,
   each receiving a curated bundle of floating fact-nodes and tool-icons that flow toward
   it like a tailored delivery. A translucent "envelope" forms around each bundle.
   On-screen text: "CRP gives every call its own window — with exactly the facts,
   tools and goals it needs."
3. THE GOVERNOR (20-35s): Between sender and model, a crystalline shield scans each bundle:
   a red instruction-override shard is caught and rejected; a green check passes through.
   A small badge stamps each passing bundle: RISK LOW · GROUNDED · CHAIN VALID.
   On-screen text: "Every call is scanned, grounded and risk-scored before it runs.
   Violations halt with a machine-readable refusal."
4. MEMORY + PROOF (35-50s): Passed facts sink into a luminous 3D knowledge graph that grows
   node by node. Alongside, chain links of glowing hashes click together one after another,
   W1 → W2 → W3; one link is touched by a dark hand and the whole chain flips red: BROKEN.
   On-screen text: "Facts persist in an auditable knowledge fabric. Every window is
   HMAC-chained — tampering is detected, not deniable."
5. BEYOND THE LIMIT (50-65s): A window fills to its edge and stops; a new window opens and
   continues the same document seamlessly, the two halves stitching into one long scroll
   of text. A counter climbs: 4,096 tokens loaded → 10,000-word deliverable.
   On-screen text: "Output limits and context limits become logistics, not walls."
6. THE HUMAN (65-78s): A robot-arm icon approaches a human silhouette; a translucent
   checkpoint gate rises between them and pauses the flow, displaying a question card.
   The human silhouette taps APPROVE; the gate lowers and the flow resumes.
   On-screen text: "Safeguards and checkpoints stop the run and ask a human — in your UI,
   not in a log file."
7. CLOSE (78-90s): All elements resolve into a single console dashboard: chat panel,
   a live narrative timeline, governance cards, the hash chain. Zoom out to reveal it
   running on a laptop marked LOCAL — no cloud icon anywhere.
   On-screen text: "Context Relay Protocol. Governed agents you can watch work.
   Local-first. Open source. pip install crprotocol."
```

## SCENE-CLIP PROMPTS (5–10s each, for tools with short clip limits)

1. **The Problem** — "Chaotic overlapping glowing text shards colliding inside a single
   rectangle, red warning flickers, dark tech background, abstract vector animation."
2. **The Envelope** — "Clean glowing frames each receiving a curated bundle of light-blue
   fact-orbs and small tool icons through a translucent envelope, dark navy, elegant motion."
3. **Injection Shield** — "A crystalline shield scanning a stream of data shards; a red
   shard labeled with a warning glyph is blocked and dissolves; green shards pass, cinematic."
4. **Knowledge Fabric** — "A luminous 3D graph growing node by node as orbs of light dock
   into it, edges lighting up, deep blue palette, slow orbit camera."
5. **Provenance Chain** — "Chain links made of glowing hexadecimal hashes clicking together
   sequentially; one link touched by a shadow cracks and the chain glows red: integrity alarm."
6. **Continuation Stitch** — "A text column filling a glowing frame to its edge, freezing,
   then a second frame continuing the same sentence seamlessly, the two welding into one."
7. **Checkpoint Gate** — "A translucent gate pausing a flow of light between a robot arm and
   a human silhouette; a question card floats; the human taps approve; the gate dissolves."
8. **The Console (use REAL footage)** — screen-record `http://127.0.0.1:8000/crp/console`
   running one live question; capture the Narrative tab populating and the provenance chain
   extending. No AI generation for this shot.

## NEGATIVE PROMPT (append to every generation)

```
photorealistic humans, faces, hands with six fingers, readable fake UI text, lorem ipsum,
brand logos of other companies, cloud/server racks as hero imagery, stock-photo smiles,
watermarks, subtitles baked in, more than 5 words of on-screen text per shot
```

## VOICEOVER SCRIPT (record separately, ~140 words for 90s)

> "Every AI agent today shares one context window — everything competes for space, and
> nothing is checked on the way out. CRP — the Context Relay Protocol — changes the
> geometry. Every model call gets its own window, pre-loaded with exactly the facts, tools
> and goals that call needs. Each call is scanned for injections, grounded against sources,
> and risk-scored before it runs; violations halt with a machine-readable refusal, not a
> polite apology. Facts persist in an auditable knowledge fabric, and every window is
> HMAC-chained — tamper with history and the chain breaks, visibly. When a model hits its
> output or context limit, CRP stitches the next window and the work continues — a 7B model
> on your laptop delivers what needed a datacenter yesterday. And when a safeguard fires,
> the run stops and asks a human. All of it is visible, live, in the agent console.
> Local-first. Open source. This is CRP."

## 30-SECOND CUT

Scenes 1 → 2 → 3 → 4/5 (split screen) → 7 → 8. Voiceover trimmed to:

> "One shared window, nothing checked — that's today's agent. CRP gives every call its own
> curated window: scanned, grounded, risk-scored before it runs. Facts persist; every window
> is HMAC-chained, so tampering is visible. Limits become logistics — small local models
> deliver big. Safeguards stop and ask a human. Watch it work in the console.
> Context Relay Protocol — pip install crprotocol."

## ACCURACY CHECKLIST (verify against footage before publishing)

- [ ] No claim of cloud SaaS availability (launch = local/self-hosted)
- [ ] Console footage shows a real local backend stream (not mocked)
- [ ] HMAC chain, grounding, risk, halt/451, checkpoint, continuation — each shown matches real behavior
- [ ] Model named on screen is the model actually running
