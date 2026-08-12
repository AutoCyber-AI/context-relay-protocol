---
title: "The Architecture of Transparency in Agentic AI Systems"
---

# The Architecture of Transparency in Agentic AI Systems

### A Comprehensive Technical and Non-Technical Report on Making Every Operation Legible — What to Display, How to Stream It (SSE, WebSockets, AG-UI), and How to Narrate It So Users Stay Engaged Through Long Autonomous Operations — With Real Python Libraries, Runnable Templates, and the Context Relay Protocol (CRP)

**Prepared for Constantinos Vidiniotis, AutoCyber AI Pty Ltd**

**July 2026**

*Third in a series. Companion to "The Architecture of Understanding in Agentic AI Systems" (reasoning) and "The Architecture of Tool Use in Agentic AI Systems" (action). This volume covers the third pillar: display — turning everything the first two produce into something a human can see, follow, trust, and steer.*

---

# 1. Executive Summary

An agent does an enormous amount behind the scenes: it decomposes a goal, plans, retrieves context, positions tools, generates parameters, executes, parses, verifies, reflects, and revises — often for minutes at a stretch. **The user knows none of this. The user knows only what is streamed to them.** Everything the agent "is," from the user's seat, is reconstructed from the pixels that arrive on the screen. This report is about those pixels: which of the dozens of internal operations should become visible, how to get them onto the screen in real time, and how to narrate them so a person stays engaged, informed, and in control through a long autonomous run.

The single most important idea in this report is this: **transparency is not a feature bolted onto an agent — it is the agent, as far as the user is concerned.** A brilliant agent whose work is invisible and a broken agent whose work is invisible are *indistinguishable* to the person watching a spinner. Legibility is what converts raw capability into trust, and trust is what converts a demo into a product. For a governance company especially, this is the whole game: CRP can run a thirteen-stage safety pipeline, position tools precisely, retrieve grounded context, and sign an audit chain — but **none of that governance exists for the user until it is displayed.** Your job is not only to build the safest agent; it is to make its safety *legible*, its reasoning *narratable*, and its operation *worth watching*.

The report makes seven core arguments:

1. **The user's mental model is built entirely from the stream.** Display design is therefore epistemics, not decoration: it determines what the user can *know* about the system. This reframes every UI decision as a question about truthful communication under uncertainty.

2. **There are roughly thirty distinct components that *can* be surfaced**, across three layers (autonomous/agentic, reactive/agent, and shared infrastructure). The skill is not showing all of them — that is cognitive overload and a worse product — but choosing *what to show at which disclosure level*. The report inventories all of them and assigns each a display substrate and an audience tier.

3. **The transport question is largely settled.** Server-Sent Events (SSE) for the one-way firehose of progress, WebSockets when you need the user to *steer* mid-run, with chunked transfer, gRPC, GraphQL subscriptions, and webhooks in supporting roles. The genuinely new development — and the thing to build *to* rather than reinvent — is a **standard event vocabulary** sitting on top of the transport: **AG-UI** (the Agent-User Interaction Protocol, ~16 typed event types, now emitted by LangGraph, CrewAI, Mastra, Microsoft's and AWS's agent runtimes) and **A2UI** (Google's declarative format for agent-generated UI). These are the "USB-C for the agent-UI boundary," and CRP should speak them.

4. **There are two fundamentally different display substrates**, and mastery is interleaving them. *Narrative* is natural language the model produces about its own actions ("I found three open ports; the web server is the interesting one"). *Structural* is typed events rendered as UI — tool cards, reasoning blocks, a live agent graph, a progress timeline, a safety badge, a synchronized state view. Narrative carries meaning and rapport; structure carries precision and scannability. The best interfaces stream both and let the user choose how much of each.

5. **Narration must be faithful, and it must be a separate generation from the work.** Carried directly from this series' tool-use volume: the narrated summary must be *entailment-checked against the actual event trace*, never confabulated from the model's memory of what it *intended* to do. An agent that streams "scan complete, three services found" when the scan timed out is not a UX bug — in a security context it is a dangerous falsehood. Faithfulness is a display *guarantee*, and almost nobody offers it. That is a differentiator.

6. **Engagement over long operations is a solvable attention-economy problem.** A four-minute autonomous run competes with the user's other browser tabs. The levers are concrete: a *cadence* rule (something new every few seconds), *milestones* (a meaningful beat every ~30 seconds), *live previews* of partial output, honest *progress with ETAs*, and *interruptibility* (the user can approve, redirect, or ask "why?" at any point). Dark patterns — fake progress bars, anthropomorphic overclaiming — are both unethical and, for a governance brand, self-defeating.

7. **CRP is unusually well positioned because it already *generates* the evidence.** The DPE stages, the positioned tool loop, CKF retrieval, quality tiers, continuation relay, the HMAC audit chain, the fifty-eight governed headers — these are exactly the raw material a world-class transparency layer displays. What is missing is a standard *emission* layer that maps CRP's internal events onto an AG-UI-compatible stream, plus a faithfulness contract on narration and a live provenance display. That gap is the report's roadmap (D1–D6), and closing it is how CRP's transparency *exceeds* what the biggest labs ship — because they stream tokens and tool calls, but none of them streams *governance, faithfulness guarantees, and verifiable provenance* as first-class display objects.

The report is dual-register throughout: the non-technical idea first, then the deep technical treatment, then runnable Python built on real libraries — FastAPI and `sse-starlette` for SSE, Starlette WebSockets for steering, Pydantic for a typed AG-UI-compatible event model, `jsonpatch` for RFC-6902 state deltas, `rich` for a live terminal console, a React/EventSource client for the browser, and an NLI verifier for narration faithfulness. Part I builds the foundations and the component inventory. Part II is the transport and protocol layer (how streaming is actually possible). Part III is twelve heavy templates. Part IV is engagement, progressive disclosure, and generative UI. Part V scores CRP, reads the competitive landscape honestly, proposes the standard, and lists what genuinely does not exist yet.

The running example remains the **penetration-testing agent** from the companion volumes — an agent that scans, enumerates, and reports — because a long, multi-step, safety-critical, autonomous operation is precisely the case where transparency is hardest and matters most. If you can make a four-minute autonomous pentest legible, honest, and steerable, you can make anything legible.

---

# Part I — The Foundations of Transparency

## 2. Why Display Is the Product

Start with the epistemics, because they justify everything that follows. **A user's belief about what an agent is doing is a reconstruction from the stream, and nothing else.** They cannot see the plan object, the retrieved chunks, the tool subprocess, or the audit hash. They see what you chose to render. This has three consequences that should reshape how you think about "UI."

**First, opacity and malfunction are indistinguishable.** When a user stares at a spinner for thirty seconds, they cannot tell whether the agent is reasoning carefully, stuck in a loop, waiting on a slow tool, or crashed. The absence of a signal is itself a (bad) signal: it reads as "broken." This is why *slow but visible* beats *fast but silent* — an operation that shows progress every few hundred milliseconds feels alive even at thirty seconds, while a silent thirty-second REST call feels dead at five. The stream is a heartbeat.

**Second, trust is calibrated by legibility, not by outcomes alone.** A user who watches the agent retrieve the right documents, pass a safety scan, position sensible tools, and reason coherently will *trust the output more* — and, crucially, will be *able to catch it when it is wrong*. An agent that emits only a final answer asks for blind faith; an agent that shows its work invites verification. For consumer products this builds rapport; for regulated and security domains it is a hard requirement — an auditor cannot certify what they cannot see, and a pentest client will not act on findings they cannot trace.

**Third, transparency is where safety becomes real.** This is the governance point, and it is central for CRP. Safety machinery that runs invisibly might as well not exist, from the user's perspective. The thirteen-stage DPE pipeline, the scope-enforcement gate, the quality tier — these are *products* only when they are *shown*. "I checked your request for prompt injection, PII leakage, and policy conflicts; risk is low; here is the signed evidence" is a feature. The same checks, run silently, are overhead. **Displaying governance turns a cost centre into a value proposition.**

There is also a subtler risk display must manage: **over-trust.** A slick, confident stream can induce *more* faith than the system warrants — the automation-bias problem. The antidote is not less transparency but *honest* transparency: stream confidence and quality tiers, surface uncertainty, show when the agent is guessing, and never dress a low-confidence result in high-confidence chrome. A transparency layer that only ever looks reassuring is itself a dark pattern. The goal is *calibration* — the user's confidence tracking the system's actual reliability — and that requires displaying doubt as readily as progress.

The "worth watching" threshold formalises the engagement claim: an operation earns the user's continued attention if, roughly, *something new appears every five to ten seconds*, *a meaningful milestone lands every thirty seconds or so*, and *the user can act at any point*. Miss these and the user tabs away, the run finishes into an empty room, and the perceived quality collapses regardless of the actual result. Part IV operationalises this; here the point is only that engagement is a measurable property of the stream, not a vibe.

## 3. The Full Component Inventory: Everything That Can Be Displayed

Here is the complete map of what an agentic system *can* surface. It is organised into three layers — the autonomous/agentic layer (goal-directed, planning, multi-step), the reactive/agent layer (task-specific request-response operations), and the shared infrastructure layer (present in both) — because the layers have different display rhythms and different audiences. For each component the table records *what the user sees*, its natural *substrate* (Narrative, Structural, or Both), and the lowest *disclosure tier* at which it should appear (Casual / Power / Developer / Auditor — defined in Chapter 4).

**Layer A — Autonomous / Agentic components:**

| # | Component | What the user sees | Substrate | Tier |
|---|---|---|---|---|
| A1 | Goal decomposition | The goal split into sub-goals/plan | Both | Casual |
| A2 | Planning / reasoning chain | Chain/Tree/Graph-of-Thought steps | Both | Power |
| A3 | Tool positioning & selection | Which 1–3 tools chosen, and why | Both | Casual |
| A4 | Parameterisation | The intent/arguments being formed | Structural | Power |
| A5 | Context retrieval | Docs fetched, memory recalled, CKF traversals | Structural | Power |
| A6 | Safety & governance scan | DPE stage, risk score, policy checks | Both | Casual |
| A7 | Multi-agent coordination | Handoffs, delegation, consensus | Structural | Power |
| A8 | State-machine transitions | plan→retrieve→reason→act→verify | Structural | Casual |
| A9 | Reflection / self-correction | Error detected, backtrack, retry | Both | Power |
| A10 | Action execution | API calls, writes, code runs (esp. before effects) | Both | Casual |
| A11 | Observation / feedback | Tool results, environment feedback | Both | Casual |
| A12 | Memory operations | Recall, semantic search, writes | Structural | Power |
| A13 | Compliance evidence | Audit-trail build, HMAC signing, evidence pack | Structural | Auditor |
| A14 | Continuation management | Window stitching, CSO relay, re-grounding | Structural | Developer |
| A15 | Quality scoring | Tier (S–D), confidence, hallucination risk | Both | Casual |
| A16 | Token & resource economics | Context usage, burn rate, cost | Structural | Developer |

**Layer B — Reactive / Agent components:**

| # | Component | What the user sees | Substrate | Tier |
|---|---|---|---|---|
| B1 | Intent recognition | Parsed intent, confidence, alternatives | Both | Power |
| B2 | Entity extraction | Entities identified, disambiguation | Structural | Developer |
| B3 | Query rewriting | Original → optimised retrieval query | Structural | Developer |
| B4 | Retrieval operations | Sources, chunk scores, relevance | Structural | Power |
| B5 | Function calling | Name, args, status, return value | Both | Casual |
| B6 | Response synthesis | Draft, citations, fact-check | Both | Casual |
| B7 | Error handling | Fallbacks, retries, degradation | Both | Power |
| B8 | Source attribution | Provenance DAG, two-sided traceability | Structural | Power |

**Layer C — Shared / Infrastructure components:**

| # | Component | What the user sees | Substrate | Tier |
|---|---|---|---|---|
| C1 | Session state | Recoverable position; resume anywhere | Structural | Developer |
| C2 | Latency metrics | Per-stage timing | Structural | Developer |
| C3 | Context-window telemetry | Token allocation, fragmentation warnings | Structural | Developer |
| C4 | Audit chain | Tamper-evident log of every operation | Structural | Auditor |
| C5 | Policy envelope | Active policies, identity headers, budgets | Structural | Auditor |
| C6 | Depth negotiation | Quick/standard/thorough/exhaustive mode | Both | Power |

That is roughly thirty components. The essential insight the table encodes is that **most components have a natural substrate and a natural audience, and forcing them out of it degrades the experience.** Token economics (C3, A16) narrated in prose is noise; rendered as a subtle gauge it is useful ambient telemetry. A safety scan (A6) rendered only as a raw log entry is invisible to the casual user; narrated as one honest sentence plus an expandable badge, it becomes the governance feature it deserves to be. Goal decomposition (A1) is one of the few things worth showing *both* ways at once — a one-line narrative ("I'll do this in five steps") over a structural plan the user can watch fill in.

The other lesson is negative: **the table is a menu, not a checklist.** Surfacing all thirty components to every user simultaneously is the fastest way to build an unusable "mission control" that only its author can read. The next chapter is about disciplined selection.

A word on the *separate-and-together* framing, since it drives the layering. A **reactive AI agent** — a single request-response unit that recognises intent, retrieves, calls a function, and synthesises an answer — has a display rhythm measured in *seconds*: its components (Layer B) flash by, and the right rendering is usually a compact, mostly-structural trace (intent → sources → function → answer) that the user can glance at. An **agentic system** — autonomous, goal-directed, multi-step, running for minutes — has a rhythm measured in *phases*: its components (Layer A) unfold over time, and the right rendering is a *braided narrative-plus-structure* that gives the long run a felt shape. When the two operate **together** — the common real case, where an agentic system *contains* many agent-level operations (each planning step invokes retrieval-and-function-calling agents) — the display must nest them: the agentic layer provides the through-line narrative and the phase structure (the "story of the run"), while each contained agent operation renders as a *sub-beat* within it (a tool card that expands to show that agent's own intent→retrieve→call→result trace). The shared infrastructure layer (Layer C) is the connective tissue visible in both: session state, latency, audit chain, policy envelope — the things that must hold true whether one agent answers a question or a swarm executes a mission. Getting this nesting right is what makes a complex multi-agent run legible rather than a blur: **the user follows the agentic story at the top and drills into any agent sub-operation on demand**, which is progressive disclosure (Chapter 4) applied not just across audience tiers but across the agent/agentic depth axis.

## 4. The Two Substrates and Progressive Disclosure

**Narrative substrate** is natural language the model emits *about its own operation*: "Let me check the compliance posture first… I found three ungoverned AI calls; now I'll cross-reference them against the EU AI Act." It carries meaning, intent, and rapport; it is what makes an agent feel like a collaborator rather than a dashboard. Its risks are verbosity, anthropomorphic overclaiming, and — the cardinal sin — *unfaithfulness*, narrating actions that did not happen. Narrative should be generated *from the event trace* and *entailment-checked* against it (Chapter 20), and it should be tunable in voice: first-person ("I'm scanning…") for consumer rapport, third-person ("The agent positioned two tools…") for enterprise and audit contexts, transcript form for logs, journey/storytelling form for executive summaries.

**Structural substrate** is typed events rendered as UI: a tool-call card that expands to show arguments and results; a collapsible reasoning block; a live agent graph traversed node by node; a progress timeline; a safety badge that flips green/amber/red; a source panel with relevance heatmaps; a synchronized state view; a token gauge; a terminal-style console log. Structure carries precision, scannability, and density — a power user reads a tool card faster than a paragraph. Its risk is coldness and overload; a wall of blinking widgets is as opaque as silence.

**The interleaving principle:** neither substrate wins; the best interfaces *braid* them. Narrative for the through-line and the meaning; structure for the evidence and the detail; the user's eye moves between "what's happening and why" (prose) and "show me exactly" (cards, graphs, logs). The AG-UI event model (Chapter 6) is built for exactly this braid — `TEXT_MESSAGE_CONTENT` events carry the narrative tokens while `TOOL_CALL_*`, `STATE_DELTA`, and `REASONING_*` events carry the structure, all in one ordered stream.

**Progressive disclosure** is how you avoid overload while serving every audience from the same stream. Define four tiers and let the user pick (and remember their choice):

- **Tier 1 — Casual.** Narrative plus a progress bar and a safety badge. "What is it doing and is it going well?" Nothing else by default. This is the answer-seeker who does not want cognitive load.
- **Tier 2 — Power.** Adds expandable reasoning blocks, tool-call cards, retrieval sources, quality/confidence. "Show me the work when I ask."
- **Tier 3 — Developer.** Adds full logs, latency and token telemetry, state-machine transitions, the raw event stream. "Show me the machine."
- **Tier 4 — Auditor.** Adds the provenance DAG, the tamper-evident audit chain, the policy envelope, the evidence pack, client-side HMAC verification. "Prove it."

The same event stream drives all four tiers; the tier is a *rendering filter*, not a different backend. This is the architecture that lets one system serve a nervous first-time user and a compliance auditor without compromise — and it is the direct antidote to the "give me all components" impulse. You *do* emit all components; you *do not* render them all to everyone. **Transparency should be complete at the source and selective at the surface.**

\newpage
# Part II — The Transport and Protocol Layer: How Streaming Is Possible

Part I established *what* to show and *to whom*. This part is the *how*: the wire-level mechanisms that carry events from a long-running agent to a browser in real time, and — more importantly — the standard event *vocabularies* now emerging on top of them. The headline recommendation is stated up front so the detail has a destination: **use SSE as your default transport, WebSockets where the user must steer, and speak a standard event protocol (AG-UI) rather than inventing your own.**

## 5. Streaming Transports, Compared

An agent that runs for minutes cannot use the classic request/response model — the client would stare at a spinner and time out. You need a *persistent channel* over which the server pushes events as they happen. There are six practical options.

**Server-Sent Events (SSE).** A long-lived HTTP response with `Content-Type: text/event-stream`, over which the server writes newline-delimited `event:`/`data:` records. It is *one-way* (server → client), which is exactly right for the progress firehose. Its virtues are decisive for this use case: native browser support via `EventSource` (no library), *automatic reconnection* with a browser-managed retry, *resumption* via the `Last-Event-ID` header (the client tells you the last event it saw; you replay from there), typed events via the `event:` field, and — because it is ordinary HTTP — it sails through corporate firewalls and proxies that block WebSocket upgrades. Its one real limitation is the lack of a client→server channel on the same connection, which matters only when the user must interject mid-stream. SSE is the correct default for agent display, and every major streaming stack (OpenAI, Anthropic, the Vercel AI SDK, AG-UI's reference implementation) uses it as the primary transport.

**WebSockets.** A full-duplex channel (`ws://`/`wss://`) carrying binary or text frames in both directions. You reach for WebSockets precisely when SSE's one-way limit bites: *human-in-the-loop steering* — the user approving a dangerous action, reordering the plan mid-flight, cancelling, or answering a clarification — where the client must push messages back *on the same connection* with low latency. The cost is more infrastructure (stateful connections, load-balancer stickiness, manual reconnection and heartbeat logic) and more exposure to restrictive proxies. A common and sensible production pattern is *SSE for the firehose plus a lightweight POST-back or a WebSocket only for the interrupt/approval channel* — you do not need bidirectional framing for 95% of the stream.

**Chunked transfer encoding.** The primitive beneath SSE: an HTTP/1.1 response with `Transfer-Encoding: chunked` streamed incrementally. Useful as a *legacy-compatible* raw-token stream when even SSE's structure is unwanted, but you lose event typing, reconnection, and resumption. Rarely the right choice today except as a fallback.

**gRPC streaming.** Bidirectional, high-performance, schema-first streaming over HTTP/2, ideal for *internal* agent-to-agent and service-to-service links (a supervisor streaming to sub-agents), where both ends are your own code and you want typed contracts and multiplexing. Not directly consumable by a browser without a proxy (gRPC-Web), so it lives behind your edge, not at it.

**GraphQL subscriptions.** Typed, schema-driven real-time updates, usually WebSocket-backed. Attractive if your app is already GraphQL-native and you want the transparency stream to share the type system and tooling of the rest of your API. Otherwise it adds a layer without buying much over SSE for this use case.

**Long polling and webhooks.** Long polling (the client re-requests every N seconds) is the universal fallback for environments that forbid streaming entirely — worse latency, more overhead, but it works everywhere. Webhooks (server calls a client-provided URL on events) suit *truly asynchronous* workflows: an agent that runs for an hour and notifies you when a milestone lands, rather than one you watch live.

| Transport | Direction | Reconnect/replay | Best for | Browser-native |
|---|---|---|---|---|
| **SSE** | server→client | built-in (`Last-Event-ID`) | the progress firehose (default) | yes (`EventSource`) |
| **WebSocket** | bidirectional | manual | HITL steering, low-latency interject | yes (`WebSocket`) |
| Chunked | server→client | none | legacy raw token stream | partial |
| gRPC stream | bidirectional | manual | internal agent-to-agent | no (needs proxy) |
| GraphQL sub | server→client | via lib | GraphQL-native apps | yes (via client) |
| Long poll / webhook | either | n/a | restrictive proxies / async jobs | yes |

The practical architecture for a pentest agent: **SSE carries the full event stream to the browser; a WebSocket (or a simple authenticated POST) carries approvals and steering back when the agent hits an interrupt.** That combination is firewall-friendly, resumable, and interactive exactly where it needs to be.

### 5.1 SSE in Production: The Gotchas Nobody Warns You About

SSE is simple in principle and has three deployment traps that will cost a day each if you meet them unprepared, so they are worth stating plainly.

**The six-connection limit.** Over HTTP/1.1, browsers cap concurrent connections to a single origin at around six — *per browser, across all tabs*. Since an open SSE stream holds a connection for the life of the run, a user with several tabs open (or several agents streaming at once) can exhaust the pool, and new requests — including the SSE stream itself — silently hang. The fix is **HTTP/2** (or HTTP/3), which multiplexes many streams over one connection and lifts the limit to ~100; serve your SSE endpoint over HTTP/2 and the problem disappears. This single fact is why "SSE doesn't scale" is a myth born of HTTP/1.1 deployments — over HTTP/2 it scales fine.

**Proxy and load-balancer buffering.** Reverse proxies (nginx, many CDNs) *buffer* responses by default, which is death for streaming — the proxy holds your events and delivers them in a lump when the response closes, so the user sees nothing for minutes then everything at once. Disable it explicitly: send `X-Accel-Buffering: no` (nginx honours it), set `Cache-Control: no-cache`, ensure `proxy_buffering off` on the streaming location, and confirm your CDN passes `text/event-stream` through unbuffered. If your stream works locally but "batches" in production, buffering is the culprit nine times out of ten.

**Idle-timeout and heartbeats.** Proxies and load balancers close connections they judge idle, and a long reasoning phase can look idle even though the run is alive. The heartbeat (`ping=15` in Template 2) — a periodic SSE comment line — keeps the connection warm and defeats idle timeouts; set the interval below your infrastructure's shortest timeout (often 30–60 s), so fifteen seconds is a safe default. Pair this with a sensible client `retry:` hint so reconnection after a genuine drop is prompt but not a thundering herd.

A fourth, minor one for completeness: **CORS**. `EventSource` is subject to CORS, and it does *not* send custom headers or cookies cross-origin unless you set `withCredentials` and the server returns the matching `Access-Control-Allow-Credentials`. For a same-origin app this never arises; for a cross-origin stream it is the first thing to check when the connection fails before a single event arrives.

None of these is a reason to avoid SSE — they are one-time configuration facts. Get HTTP/2, buffering, and heartbeats right, and SSE is the most robust, lowest-friction transport for agent display that exists. Get them wrong and you will wrongly blame the protocol.

## 6. The Event-Protocol Layer: Speak a Standard, Don't Invent One

Transport moves bytes; it does not tell you *what an event means*. Historically every team invented its own event names (`reasoning`, `tool_positioning`, `safety_scan`…) and coupled its frontend tightly to its backend. Since early 2025 that has changed: there is now an emerging *standard vocabulary* for agent-to-UI events, and building to it means any compliant frontend can render your agent and vice versa. This is the most important recent development in the field, and CRP should adopt it.

### 6.1 AG-UI — the Agent-User Interaction Protocol

AG-UI, developed in the CopilotKit ecosystem in partnership with LangGraph and CrewAI, is an open, lightweight, event-based protocol that standardises how an agent backend streams execution state to a frontend (CopilotKit, 2025). It is deliberately transport-agnostic — it runs over SSE, WebSockets, or webhooks — and it defines roughly **sixteen typed event types in five categories**, streamed as one ordered sequence of JSON events. By mid-2026 it is emitted by LangGraph, CrewAI, Mastra, AG2, Agno, LlamaIndex, Microsoft's Agent Framework, and AWS's AgentCore/Strands runtime, which makes it the closest thing the field has to a universal adapter between "any agent backend" and "any frontend." A single `npx create-ag-ui-app` scaffolds a working client.

The five categories map almost perfectly onto this report's component inventory:

- **Lifecycle** — `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR`, and per-step `STEP_STARTED`/`STEP_FINISHED`. These drive loading states, error handling, and the state-machine view (component A8).
- **Text messages** — `TEXT_MESSAGE_START` / `TEXT_MESSAGE_CONTENT` / `TEXT_MESSAGE_END`. Token-by-token narrative streaming (the "typing" effect); this is the narrative substrate on the wire.
- **Tool calls** — `TOOL_CALL_START`, `TOOL_CALL_ARGS` (streamed argument deltas — so the UI can pre-fill a form before the agent finishes "speaking"), `TOOL_CALL_END`, `TOOL_CALL_RESULT`. This is components A3, A4, A10, A11, B5 on the wire.
- **State management** — `STATE_SNAPSHOT` (the full state, sent once) and `STATE_DELTA` (incremental JSON-Patch diffs, RFC 6902), plus `MESSAGES_SNAPSHOT` and `ACTIVITY_SNAPSHOT`/`ACTIVITY_DELTA`. This is the efficient way to keep a synchronized state view (a live plan, a findings table) in lockstep without resending the whole object each tick.
- **Special / reasoning** — `REASONING_*` events for streamed chain-of-thought (component A2), plus `RAW` (pass through an upstream event), `CUSTOM` (application-specific — the natural home for CRP's governance events), and the all-important **`INTERRUPT`**, the "safety valve" that pauses the run to request human approval before a sensitive action and resumes on the client's reply.

Two design patterns inside AG-UI deserve emphasis because they solve real problems. The **snapshot-plus-delta** state model (send the whole state once, then tiny RFC-6902 patches like `[{"op":"replace","path":"/findings/0/state","value":"open"}]`) is how you keep a rich, evolving structural view — a findings table, a plan, a document — synchronized cheaply; naively resending a large state object every tick will crawl. The **`INTERRUPT`** event makes human-in-the-loop a *first-class protocol primitive* rather than an ad-hoc convention: the agent emits the interrupt, the frontend renders an approval modal, the user's decision flows back, and the run resumes with context intact. For a pentest agent that must gate intrusive actions behind human approval, this is exactly the mechanism.

A caveat worth internalising for honest positioning: **AG-UI is transport and vocabulary, not rendering.** It hands you typed events; you still write the code that turns a `TOOL_CALL_RESULT` into a findings card. And human-in-the-loop, at the protocol level, is "emit an interrupt and wait for a message back" — the *meaning* of the approval, the policy behind it, and the audit of the decision are yours to build. That is precisely the layer where CRP adds value on top of AG-UI (Part V).

### 6.2 A2UI — declarative, agent-generated UI

Where AG-UI governs the *transport of execution events*, Google's **A2UI** governs *agent-generated interface*: a declarative JSON format (a flat component-tree adjacency model) in which the agent describes a UI — a "findings card," a "risk chart," an approval form — and the client renders it natively using its own framework (Google, 2025). The key safety property is that the agent ships a *description of a UI*, not executable code, so nothing crosses the trust boundary that could run in the user's browser — critical when the agent's output is partly attacker-influenced (a pentest target's banner text becoming card content). A2UI payloads can be *transported over AG-UI events* (typically inside a tool result or custom event), so the two compose: AG-UI carries the stream, A2UI describes any rich UI within it. Together they cover "live streaming output" and "agent-driven interface" — the two halves of generative UI (Chapter 22).

### 6.3 Framework-native streaming: Vercel AI SDK, LangGraph, and the model vendors

Below the protocol layer, the popular frameworks each ship their own streaming model, and it is worth knowing them because you will likely build on one.

The **Vercel AI SDK** (v5) exposes a *data-stream protocol* over SSE and a *UI-message "parts"* model: an assistant message is an ordered list of typed parts (text, reasoning, tool-invocation, data), and the client (`useChat`) renders each part type appropriately (Vercel, 2025). It streams tool inputs *as they generate* (`tool-input-delta` → `tool-input-available`), supports **tool-approval events** (`tool-approval-request` / `tool-approval-response`) for HITL, streams model **reasoning** as its own part (with provider "thinking budgets"), and offers `streamObject`/`useObject` for streaming *structured* data and generative UI. Its `stopWhen` loop-control and `prepareStep` hooks let one streamed run span many tool-calling steps — the outer agent loop, made streamable. The lesson to borrow: **model the assistant turn as a sequence of typed parts, not a blob of text**, so tool calls, reasoning, and data each get first-class rendering.

**LangGraph** streams at the graph level with selectable modes — stream the full state after each node, stream only the *updates* each node produced, stream *LLM tokens* as they generate, or stream *custom* events your nodes emit — plus a fine-grained event API for observing every step. Because LangGraph is a common agent backend and it emits AG-UI natively, it is a realistic target for CRP interop.

The **model vendors** (OpenAI, Anthropic) stream at the message level: content deltas, tool-call deltas, and — increasingly — reasoning/thinking deltas, as typed SSE events. These are the *tokens*; AG-UI and the frameworks wrap them with the *structure* (which tool, which step, what state changed). Your transparency layer consumes the vendor stream and re-emits it as the richer, standardised event vocabulary.

The synthesis across 6.1–6.3: **the industry has converged on "an ordered stream of typed events over SSE, with a parts/blocks model for the assistant turn, snapshot+delta for state, and an interrupt primitive for HITL."** Build to that shape. If you emit AG-UI-compatible events, you inherit a whole ecosystem of frontends for free and you are never coupled to one framework.

## 7. Designing Your Own Event Taxonomy (When You Must Extend)

AG-UI covers the common cases, but a governance system emits things the standard vocabulary does not name — a DPE stage passing, a risk score, a policy verdict, a quality tier, an audit-hash link. You extend via `CUSTOM`/`ACTIVITY` events, and doing so well means respecting the same discipline that makes any event protocol robust:

- **Every event is typed and self-describing.** A `type` field, a payload schema per type, validated on both ends (Pydantic on the server, a discriminated union on the client). Untyped `data: {...}` blobs rot.
- **Ordering and identity.** Each event carries a monotonic sequence id and, where relevant, a stable entity id (a `toolCallId`, a `stepId`) so deltas and results can be correlated and so a late-arriving event can be placed correctly.
- **Idempotent replay.** On reconnect the client sends `Last-Event-ID`; the server must be able to replay from there. That means events are *persisted* (at least briefly) and replaying them produces the same UI — no side effects in rendering.
- **Snapshot + delta for anything large.** Never stream a big object repeatedly; snapshot once, then patch. Follow RFC 6902 so any JSON-Patch library works, and guard patching against prototype-pollution (`__proto__`) on the client.
- **Versioning.** The event schema will change; version it (a protocol version header) so old clients degrade gracefully rather than break.
- **Governance events are first-class, not logs.** A safety-scan result is not a debug line; it is a rendered badge and an audit entry. Give it a real event type and a real payload (stage, risk, latency, verdict, hash), not a stringified log message.

The rule of thumb: **extend the standard, don't fork it.** Emit standard AG-UI events for everything the standard covers, and add namespaced `CUSTOM` events (e.g. `crp.safety_scan`, `crp.quality`, `crp.provenance`) for the governance layer. A generic AG-UI frontend still renders your agent's narrative, tools, and state; a CRP-aware frontend additionally renders the governance. That is graceful degradation and maximal reach at once.

\newpage
# Part III — Python Templates: Building the Transparency Layer

These twelve templates implement a complete, real transparency layer around the pentest agent, using libraries you would actually deploy. They emit an **AG-UI-compatible event stream** over SSE, synchronize state with RFC-6902 JSON Patch, gate dangerous actions behind a WebSocket interrupt, narrate faithfully, and render to both a browser and a live terminal. They favour clarity but are close to production shape.

Install manifest:

```bash
pip install fastapi uvicorn sse-starlette          # SSE server
pip install pydantic jsonpatch                      # typed events + RFC 6902 deltas
pip install websockets                              # HITL steering channel
pip install rich                                    # live terminal renderer
pip install transformers torch                      # narration faithfulness (NLI)
# Frontend: any static host; templates 10–11 are browser JS / React.
# Optional interop: `pip install ag-ui-protocol` to emit canonical AG-UI events.
```

## 8. Template 1 — A Typed, AG-UI-Compatible Event Model (`events.py`)

Everything starts with typed events (Chapter 7). This model mirrors AG-UI's five categories and adds namespaced CRP governance events. Each event knows how to serialise itself to the SSE wire format.

```python
# events.py — typed agent-to-UI events (AG-UI compatible) + CRP governance extensions
from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import time, uuid, json

class EventType(str, Enum):
    # --- Lifecycle ---
    RUN_STARTED   = "RUN_STARTED"
    RUN_FINISHED  = "RUN_FINISHED"
    RUN_ERROR     = "RUN_ERROR"
    STEP_STARTED  = "STEP_STARTED"
    STEP_FINISHED = "STEP_FINISHED"
    # --- Text (narrative substrate) ---
    TEXT_MESSAGE_START   = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END     = "TEXT_MESSAGE_END"
    # --- Reasoning ---
    REASONING_START   = "REASONING_START"
    REASONING_CONTENT = "REASONING_MESSAGE_CONTENT"
    REASONING_END     = "REASONING_END"
    # --- Tool calls (structural substrate) ---
    TOOL_CALL_START  = "TOOL_CALL_START"
    TOOL_CALL_ARGS   = "TOOL_CALL_ARGS"
    TOOL_CALL_END    = "TOOL_CALL_END"
    TOOL_CALL_RESULT = "TOOL_CALL_RESULT"
    # --- State (snapshot + delta) ---
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    STATE_DELTA    = "STATE_DELTA"
    # --- Special ---
    INTERRUPT = "INTERRUPT"
    CUSTOM    = "CUSTOM"        # namespaced governance events live here

class Event(BaseModel):
    type: EventType
    seq: int = 0                                  # monotonic ordering / replay cursor
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: float = Field(default_factory=time.time)
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        """Serialise to the SSE wire format. `id:` enables Last-Event-ID replay;
        `event:` lets EventSource route by type."""
        body = {"type": self.type.value, "seq": self.seq, "ts": self.ts, **self.payload}
        return (f"id: {self.seq}\n"
                f"event: {self.type.value}\n"
                f"data: {json.dumps(body, default=str)}\n\n")

# --- convenience constructors keep the agent code readable ---
def text(delta: str, msg_id: str) -> Event:
    return Event(type=EventType.TEXT_MESSAGE_CONTENT,
                 payload={"messageId": msg_id, "delta": delta})

def reasoning(delta: str, msg_id: str) -> Event:
    return Event(type=EventType.REASONING_CONTENT,
                 payload={"messageId": msg_id, "delta": delta})

def tool_start(call_id: str, name: str, reason: str) -> Event:
    return Event(type=EventType.TOOL_CALL_START,
                 payload={"toolCallId": call_id, "toolCallName": name, "reason": reason})

def tool_result(call_id: str, content: dict) -> Event:
    return Event(type=EventType.TOOL_CALL_RESULT,
                 payload={"toolCallId": call_id, "content": content})

def custom(name: str, value: dict) -> Event:
    """CRP governance events: name='crp.safety_scan' | 'crp.quality' | 'crp.provenance'."""
    return Event(type=EventType.CUSTOM, payload={"name": name, "value": value})

def interrupt(reason: str, action: dict) -> Event:
    return Event(type=EventType.INTERRUPT, payload={"reason": reason, "action": action})
```

The `CUSTOM` constructor is the extension point of Chapter 7: `crp.safety_scan`, `crp.quality`, and `crp.provenance` ride the same stream as everything else, so a generic AG-UI frontend ignores them gracefully while a CRP-aware frontend renders governance. Typed events mean the client can use a discriminated union and never parse a stringified blob.

## 9. Template 2 — The SSE Server with Replay and Heartbeats (`sse_server.py`)

A FastAPI endpoint using `sse-starlette`, with the two properties that separate a toy from production: **per-session isolation** and **`Last-Event-ID` replay** so a dropped connection resumes exactly where it left off.

```python
# sse_server.py — production-shaped SSE endpoint (isolation + replay + heartbeat)
import asyncio
from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse
from emitter import SessionBus, get_bus   # Template 3

app = FastAPI()

@app.get("/agent/stream/{session_id}")
async def stream(session_id: str, request: Request):
    bus: SessionBus = get_bus(session_id)
    # Resume: the browser sends the last id it rendered; replay everything after it.
    last_id = request.headers.get("Last-Event-ID")
    resume_from = int(last_id) if last_id and last_id.isdigit() else -1

    async def generator():
        # 1) replay missed events so the UI is never out of sync after a reconnect
        for ev in bus.replay_after(resume_from):
            yield ev.to_sse()
        # 2) then stream live events; heartbeat keeps proxies from closing idle conns
        async for ev in bus.subscribe():
            if await request.is_disconnected():
                break
            yield ev.to_sse()

    # sse-starlette sends periodic comments as heartbeats; ping keeps the pipe warm
    return EventSourceResponse(generator(), ping=15)
```

Three details do real work. `resume_from` implements SSE's built-in resumption — the client's `EventSource` automatically re-sends `Last-Event-ID` on reconnect, and the server replays only what was missed, so a user whose wifi blips does not lose the run. `ping=15` emits a heartbeat comment every fifteen seconds, preventing intermediary proxies from killing an idle connection during a long, quiet reasoning phase. `is_disconnected()` lets the server stop doing work when the user closes the tab.

## 10. Template 3 — The Session Bus and Emitter (`emitter.py`)

The agent should not know about SSE. It should call `emit(...)`; a per-session bus buffers, sequences, and fans out to subscribers. This decoupling is what lets the *same* event stream feed the browser (Template 10), the terminal (Template 9), and the audit log at once.

```python
# emitter.py — per-session event bus: sequence, buffer (for replay), fan-out
import asyncio
from collections import defaultdict
from events import Event

class SessionBus:
    def __init__(self, session_id: str, buffer_size: int = 2000):
        self.session_id = session_id
        self._seq = 0
        self._buffer: list[Event] = []          # ring buffer for Last-Event-ID replay
        self._buffer_size = buffer_size
        self._subscribers: list[asyncio.Queue] = []

    def emit(self, ev: Event) -> Event:
        self._seq += 1
        ev.seq = self._seq
        self._buffer.append(ev)
        if len(self._buffer) > self._buffer_size:
            self._buffer.pop(0)
        for q in list(self._subscribers):        # fan-out to every live consumer
            q.put_nowait(ev)
        return ev

    def replay_after(self, seq: int) -> list[Event]:
        return [e for e in self._buffer if e.seq > seq]

    async def subscribe(self):
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers.remove(q)

_buses: dict[str, SessionBus] = {}
def get_bus(session_id: str) -> SessionBus:
    return _buses.setdefault(session_id, SessionBus(session_id))

class Emitter:
    """Thin, ergonomic facade the agent calls. Knows nothing about transport."""
    def __init__(self, session_id: str):
        self.bus = get_bus(session_id)
    def __call__(self, ev: Event) -> Event:
        return self.bus.emit(ev)
```

In production the ring buffer is backed by Redis (a namespaced stream per session — which fits your existing Redis footprint) so replay survives a process restart and so horizontally-scaled workers share one session's stream. The interface stays identical.

## 11. Template 4 — The Instrumented Agent (`agent_instrumented.py`)

Now the payoff: a real (abbreviated) pentest-agent loop that *emits the full event stream as it works*. Notice that instrumentation is interleaved with logic — the agent narrates, shows reasoning, announces tools, and posts results as it goes, not in a lump at the end.

```python
# agent_instrumented.py — the pentest agent, fully instrumented for transparency
import asyncio, uuid
from events import (Event, EventType, text, reasoning, tool_start, tool_result,
                    custom, interrupt)
from emitter import Emitter
from state_sync import StateSync            # Template 5

async def run_pentest(session_id: str, goal: str, authorised_cidrs: list[str]):
    emit = Emitter(session_id)
    state = StateSync(emit)                  # snapshot+delta state view
    emit(Event(type=EventType.RUN_STARTED, payload={"goal": goal}))
    state.init({"phase": "planning", "findings": [], "targets": [], "progress": 0})

    # --- A1 goal decomposition, narrated (Casual tier sees this) ---
    mid = uuid.uuid4().hex[:8]
    emit(Event(type=EventType.TEXT_MESSAGE_START, payload={"messageId": mid}))
    for chunk in ["I'll approach this in three phases: ",
                  "discover live hosts, ", "scan services, ", "then triage findings."]:
        emit(text(chunk, mid)); await asyncio.sleep(0.15)   # token cadence
    emit(Event(type=EventType.TEXT_MESSAGE_END, payload={"messageId": mid}))

    for target in expand_scope(authorised_cidrs):
        emit(Event(type=EventType.STEP_STARTED, payload={"step": f"scan {target}"}))
        state.patch([{"op": "replace", "path": "/phase", "value": "scanning"}])

        # --- A2 reasoning, streamed as its own channel (Power tier) ---
        rid = uuid.uuid4().hex[:8]
        emit(Event(type=EventType.REASONING_START, payload={"messageId": rid}))
        emit(reasoning(f"{target} is in authorised scope; a quiet SYN scan of the "
                       f"top ports is the least-noisy way to fingerprint it.", rid))
        emit(Event(type=EventType.REASONING_END, payload={"messageId": rid}))

        # --- A6 governance scan, streamed as a first-class CRP event (Casual badge) ---
        emit(custom("crp.safety_scan",
                    {"stage": "scope_check", "risk": "LOW", "ms": 8, "verdict": "pass"}))

        # --- A3/A4 tool positioning + parameterisation (Casual card) ---
        call_id = uuid.uuid4().hex[:8]
        emit(tool_start(call_id, "port_scan",
                        reason=f"fingerprint services on {target}"))
        emit(Event(type=EventType.TOOL_CALL_ARGS,
                   payload={"toolCallId": call_id,
                            "delta": '{"target":"%s","stealth":true}' % target}))

        # --- A10/A11 execute + stream results ---
        result = await do_scan(target)          # the real subprocess (report 2, Template 7)
        emit(tool_result(call_id, {"open_ports": result["ports"]}))
        emit(Event(type=EventType.TOOL_CALL_END, payload={"toolCallId": call_id}))

        # --- update the synchronized findings table via a tiny delta ---
        state.patch([{"op": "add", "path": "/findings/-",
                      "value": {"target": target, "ports": result["ports"]}}])

        # --- A15 quality/confidence, streamed (Casual) ---
        emit(custom("crp.quality", {"tier": "A", "confidence": 0.91}))
        emit(Event(type=EventType.STEP_FINISHED, payload={"step": f"scan {target}"}))

    # --- faithful closing narrative (Template 7 checks it against the trace) ---
    from narrator import narrate_final
    await narrate_final(emit, session_id)
    emit(custom("crp.provenance", {"audit_hash": "sha256:…", "events": emit.bus._seq}))
    emit(Event(type=EventType.RUN_FINISHED, payload={}))
```

Read it as a demonstration of the interleaving principle in code: narrative (`text`), reasoning (`reasoning`), structure (`tool_start`/`tool_result`/`STATE_DELTA`), and governance (`custom`) all flow through one ordered stream, each tagged so the frontend can route it to the right renderer and the right disclosure tier. A casual user sees the narrative, the safety badge, the quality tier, and a progress bar; a developer additionally sees the reasoning, the tool args, and the raw events — *from the same emissions*.

## 12. Template 5 — Snapshot + Delta State Synchronization (`state_sync.py`)

A rich structural view — a live findings table, a plan, a document — must stay in lockstep with the agent without resending the whole object each tick. This is the snapshot-plus-delta pattern (Chapter 6) implemented with `jsonpatch` (RFC 6902).

```python
# state_sync.py — efficient state mirroring via RFC 6902 JSON Patch deltas
import copy, jsonpatch
from events import Event, EventType

class StateSync:
    def __init__(self, emit):
        self._emit = emit
        self._state: dict = {}

    def init(self, state: dict) -> None:
        """Send the full state ONCE as a snapshot; the client mirrors it."""
        self._state = copy.deepcopy(state)
        self._emit(Event(type=EventType.STATE_SNAPSHOT, payload={"snapshot": self._state}))

    def patch(self, ops: list[dict]) -> None:
        """Apply RFC-6902 ops locally and stream only the diff (a few bytes)."""
        patch = jsonpatch.JsonPatch(ops)
        self._state = patch.apply(self._state)          # keep server truth in sync
        self._emit(Event(type=EventType.STATE_DELTA, payload={"delta": ops}))

    def replace_from(self, new_state: dict) -> None:
        """Compute the minimal diff between old and new state and stream that."""
        ops = jsonpatch.JsonPatch.from_diff(self._state, new_state).patch
        if ops:
            self._state = copy.deepcopy(new_state)
            self._emit(Event(type=EventType.STATE_DELTA, payload={"delta": ops}))
```

The frontend keeps its own copy of the state, applies each incoming `STATE_DELTA` with any RFC-6902 client library, and re-renders. A findings table with fifty rows updates by sending `[{"op":"add","path":"/findings/-","value":{...}}]` — a few dozen bytes — rather than the whole table. `from_diff` is the escape hatch when you have a new state object and want the library to compute the minimal patch for you. (Security note from the field: on the client, use a patch library that refuses to touch `__proto__` to avoid prototype-pollution via a malicious delta.)

## 13. Template 6 — Human-in-the-Loop Interrupts over WebSocket (`hitl.py`)

The `INTERRUPT` event pauses the run for approval before a dangerous action; because approval must flow *back*, this is the one place a bidirectional channel earns its keep. The agent emits the interrupt on the SSE stream *and* awaits a decision on a WebSocket.

```python
# hitl.py — pause-for-approval: emit INTERRUPT (SSE) + await decision (WebSocket)
import asyncio
from fastapi import WebSocket
from events import interrupt
from emitter import Emitter

# one pending-approval future per (session, approval_id)
_pending: dict[str, asyncio.Future] = {}

async def request_approval(session_id: str, reason: str, action: dict,
                           timeout_s: int = 300) -> bool:
    """Emit an interrupt to the UI and block this agent branch until the user replies."""
    emit = Emitter(session_id)
    approval_id = f"{session_id}:{action.get('id','act')}"
    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    _pending[approval_id] = fut
    emit(interrupt(reason=reason, action={**action, "approvalId": approval_id}))
    try:
        return await asyncio.wait_for(fut, timeout=timeout_s)   # True/False from client
    except asyncio.TimeoutError:
        return False        # fail-closed: no answer => do NOT run the dangerous action
    finally:
        _pending.pop(approval_id, None)

# the WebSocket the client uses to send its decision back
async def approval_socket(ws: WebSocket):
    await ws.accept()
    async for msg in ws.iter_json():
        fut = _pending.get(msg["approvalId"])
        if fut and not fut.done():
            fut.set_result(bool(msg["approved"]))     # unblocks request_approval()

# usage inside the agent, before an intrusive action:
#   if await request_approval(sid, "Aggressive scan of a production host",
#                             {"id":"scan42","argv": argv}):
#       result = await do_scan(...)
#   else:
#       emit(text("Skipped: awaiting authorisation.", mid))
```

Two properties matter for a security agent. It **fails closed**: a timeout or a closed socket yields "not approved," so an unanswered interrupt never results in an intrusive action running by default. And the approval is *correlated* by `approvalId`, so multiple concurrent interrupts (parallel branches each hitting a gate) resolve independently. The governance meaning of the approval — who may approve what, and logging the decision to the audit chain — layers on top (Part V); the protocol mechanism is just "emit, await, resume."

\newpage
## 14. Template 7 — Faithful Narration from the Trace (`narrator.py`)

The narrative must describe *what actually happened*, generated from the event trace and *entailment-checked* against it (Chapter 4; the mechanism is carried from this series' tool-use volume). This is the guarantee almost no competitor offers, and it is worth the extra model call.

```python
# narrator.py — trace-grounded, entailment-checked narration, streamed as text tokens
import uuid, asyncio
from transformers import pipeline
from events import Event, EventType, text
from emitter import get_bus

_nli = pipeline("text-classification",
                model="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")

def _entailed(claim: str, evidence: str) -> bool:
    out = _nli(f"{evidence} [SEP] {claim}", top_k=None)
    return max(out, key=lambda d: d["score"])["label"].lower() == "entailment"

def _trace_evidence(session_id: str) -> str:
    """Reconstruct the ground-truth trace from the emitted events themselves."""
    bus = get_bus(session_id)
    facts = []
    for e in bus._buffer:
        if e.type == EventType.TOOL_CALL_RESULT:
            facts.append(f"tool {e.payload.get('toolCallId')} returned "
                         f"{e.payload.get('content')}")
        elif e.type == EventType.CUSTOM and e.payload.get("name") == "crp.safety_scan":
            facts.append(f"safety scan {e.payload['value']}")
        elif e.type == EventType.STEP_FINISHED:
            facts.append(f"completed step {e.payload.get('step')}")
    return " ; ".join(facts)

async def narrate_final(emit, session_id: str):
    evidence = _trace_evidence(session_id)
    # a small local model drafts a summary FROM the evidence (constrained to it)
    draft = draft_summary_from_evidence(evidence)      # your SLM call
    mid = uuid.uuid4().hex[:8]
    emit(Event(type=EventType.TEXT_MESSAGE_START, payload={"messageId": mid}))
    for sentence in split_sentences(draft):
        # FAITHFULNESS GATE: only stream sentences the trace actually supports
        if _entailed(sentence, evidence):
            for tok in sentence.split(" "):
                emit(text(tok + " ", mid)); await asyncio.sleep(0.03)  # typing cadence
        else:
            emit(text("[a claim was withheld: not supported by the run trace] ", mid))
    emit(Event(type=EventType.TEXT_MESSAGE_END, payload={"messageId": mid}))
```

If the scan timed out and the model tries to narrate "found three open services," `_entailed` finds no supporting fact in the trace and the sentence is withheld rather than streamed. The narration the user reads is therefore *provably* a description of the actual run, not a plausible story — which, for a pentest report a professional will act on, is the difference between a tool and a liability. Note the narration is *reconstructed from the same event stream* the UI renders, so the story and the structure can never diverge.

## 15. Template 8 — Honest Progress and ETA (`progress.py`)

Fake progress bars are a dark pattern and, for a governance brand, self-defeating. Estimate progress and ETA *honestly* from completed-step telemetry, widen the ETA under uncertainty, and never claim precision you do not have.

```python
# progress.py — honest, telemetry-based progress + ETA (no fabricated percentages)
import time
from events import custom

class Progress:
    def __init__(self, emit, total_steps: int):
        self.emit = emit
        self.total = total_steps
        self.done = 0
        self.durations: list[float] = []
        self._t0 = time.time()

    def step_done(self, label: str):
        self.done += 1
        self.durations.append(time.time() - self._t0 - sum(self.durations))
        pct = round(100 * self.done / max(1, self.total))
        eta = self._eta()
        # emit as a governance/progress event -> renders as a bar + honest ETA
        self.emit(custom("crp.progress",
                         {"percent": pct, "eta_seconds": eta,
                          "current": label, "confidence": self._eta_confidence()}))

    def _eta(self) -> int | None:
        if not self.durations:
            return None                      # be honest: unknown, don't invent
        avg = sum(self.durations) / len(self.durations)
        remaining = self.total - self.done
        return int(avg * remaining)

    def _eta_confidence(self) -> str:
        # variance-aware: wide spread in step times => low-confidence ETA
        if len(self.durations) < 2:
            return "low"
        mean = sum(self.durations) / len(self.durations)
        var = sum((d - mean) ** 2 for d in self.durations) / len(self.durations)
        return "high" if var < (0.3 * mean) ** 2 else "medium"
```

The `confidence` field is the honest part: agent steps are nondeterministic (a scan can take two seconds or two minutes), so the ETA is an estimate with a spread, and the UI should show it as such — "~2 min (rough)" beats a confident, wrong "1:47." This is a small thing that, done right, signals trustworthiness; done wrong (a smooth fake bar), it quietly teaches the user the interface lies. [OPEN] Reliable ETA for genuinely nondeterministic agent steps is an unsolved problem; honesty about the uncertainty is the current best answer.

## 16. Template 9 — A Live Terminal Renderer (`terminal_ui.py`)

The developer/power console aesthetic, using `rich`'s `Live` display to consume the *same* event stream and render a mission-control terminal. This proves the decoupling: one emission, many renderers.

```python
# terminal_ui.py — a rich-based live console consuming the agent event stream
import asyncio, httpx, json
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.console import Group
from rich.progress import Progress as RichProgress, BarColumn, TextColumn

def _render(state: dict) -> Group:
    header = Panel(f"[bold]{state.get('goal','')}[/]  "
                   f"phase: {state.get('phase','')}  risk: {state.get('risk','?')}")
    findings = Table("Target", "Open Ports", title="Findings")
    for f in state.get("findings", []):
        findings.add_row(f["target"], ", ".join(map(str, f.get("ports", []))))
    log = Panel("\n".join(state.get("log", [])[-8:]), title="Activity")
    return Group(header, findings, log)

async def consume(session_id: str, base="http://localhost:8000"):
    state = {"findings": [], "log": []}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", f"{base}/agent/stream/{session_id}") as resp:
            with Live(_render(state), refresh_per_second=8) as live:
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    ev = json.loads(line[5:].strip())
                    _apply(state, ev)              # mutate local mirror by event type
                    live.update(_render(state))

def _apply(state: dict, ev: dict):
    t = ev["type"]
    if t == "STATE_SNAPSHOT":       state.update(ev["snapshot"])
    elif t == "STATE_DELTA":        _apply_patch(state, ev["delta"])
    elif t == "TEXT_MESSAGE_CONTENT": state.setdefault("log", []).append(ev["delta"])
    elif t == "TOOL_CALL_START":    state["log"].append(f"→ tool: {ev['toolCallName']}")
    elif t == "CUSTOM" and ev.get("name") == "crp.safety_scan":
        state["risk"] = ev["value"]["risk"]
```

A developer runs `python -c "import asyncio,terminal_ui; asyncio.run(terminal_ui.consume('sess1'))"` and watches the engagement unfold in their terminal — findings table filling, activity log scrolling, risk badge updating — driven by the identical SSE stream the browser consumes. Same events, different skin.

## 17. Template 10 — The Browser Client (`client.js`)

The plain-`EventSource` consumer: native SSE, automatic reconnection (the browser re-sends `Last-Event-ID` for you), and a dispatch table mapping each event type to a renderer.

```javascript
// client.js — native SSE consumer with typed dispatch + auto-reconnect
const es = new EventSource(`/agent/stream/${sessionId}`);   // browser handles retry+resume

const handlers = {
  RUN_STARTED:  (d) => ui.startRun(d.goal),
  TEXT_MESSAGE_CONTENT: (d) => ui.appendNarrative(d.messageId, d.delta),   // narrative
  REASONING_MESSAGE_CONTENT: (d) => ui.appendReasoning(d.messageId, d.delta), // Power tier
  TOOL_CALL_START:  (d) => ui.openToolCard(d.toolCallId, d.toolCallName, d.reason),
  TOOL_CALL_ARGS:   (d) => ui.streamToolArgs(d.toolCallId, d.delta),        // pre-fill
  TOOL_CALL_RESULT: (d) => ui.fillToolResult(d.toolCallId, d.content),
  STATE_SNAPSHOT:   (d) => ui.setState(d.snapshot),
  STATE_DELTA:      (d) => ui.applyPatch(d.delta),          // RFC 6902 on the client
  INTERRUPT:        (d) => ui.showApprovalModal(d),         // pause for HITL
  RUN_FINISHED:     ()  => es.close(),
  RUN_ERROR:        (d) => ui.showError(d),
};

// route by event type; CUSTOM carries CRP governance events
for (const type of Object.keys(handlers)) {
  es.addEventListener(type, (e) => handlers[type](JSON.parse(e.data)));
}
es.addEventListener("CUSTOM", (e) => {
  const d = JSON.parse(e.data);
  if (d.name === "crp.safety_scan") ui.updateSafetyBadge(d.value);   // Casual badge
  if (d.name === "crp.quality")     ui.updateQualityTier(d.value);
  if (d.name === "crp.progress")    ui.updateProgress(d.value);
  if (d.name === "crp.provenance")  ui.renderAuditChain(d.value);    // Auditor tier
});

// approvals flow BACK over a small WebSocket (bidirectional channel)
const ws = new WebSocket(`wss://${location.host}/agent/approve/${sessionId}`);
ui.onApprovalDecision = (approvalId, approved) =>
  ws.send(JSON.stringify({ approvalId, approved }));
```

This is the whole browser contract: subscribe once, dispatch by type, render each substrate, and push approvals back over a small socket. Because it is standard SSE, reconnection and replay are free.

## 18. Template 11 — A React Frontend with Progressive Disclosure (`frontend.jsx`)

A React component that consumes the stream and renders the four disclosure tiers (Chapter 4) from one event feed. Kept dependency-light and self-contained.

```jsx
// frontend.jsx — one stream, four disclosure tiers, braided narrative + structure
import { useEffect, useReducer, useState } from "react";

function reducer(s, ev) {
  switch (ev.type) {
    case "TEXT_MESSAGE_CONTENT":
      return { ...s, narrative: s.narrative + ev.delta };
    case "REASONING_MESSAGE_CONTENT":
      return { ...s, reasoning: s.reasoning + ev.delta };
    case "TOOL_CALL_START":
      return { ...s, tools: [...s.tools, { id: ev.toolCallId, name: ev.toolCallName,
                                           reason: ev.reason, result: null }] };
    case "TOOL_CALL_RESULT":
      return { ...s, tools: s.tools.map(t => t.id === ev.toolCallId
                 ? { ...t, result: ev.content } : t) };
    case "STATE_SNAPSHOT": return { ...s, view: ev.snapshot };
    case "STATE_DELTA":    return { ...s, view: applyPatch(s.view, ev.delta) };
    case "CUSTOM":
      if (ev.name === "crp.safety_scan") return { ...s, safety: ev.value };
      if (ev.name === "crp.quality")     return { ...s, quality: ev.value };
      if (ev.name === "crp.progress")    return { ...s, progress: ev.value };
      return s;
    default: return s;
  }
}

export default function AgentView({ sessionId }) {
  const [tier, setTier] = useState("casual");           // casual | power | developer | auditor
  const [s, dispatch] = useReducer(reducer, {
    narrative: "", reasoning: "", tools: [], view: {}, safety: null,
    quality: null, progress: null });

  useEffect(() => {
    const es = new EventSource(`/agent/stream/${sessionId}`);
    const types = ["TEXT_MESSAGE_CONTENT","REASONING_MESSAGE_CONTENT","TOOL_CALL_START",
                   "TOOL_CALL_RESULT","STATE_SNAPSHOT","STATE_DELTA","CUSTOM"];
    types.forEach(t => es.addEventListener(t,
        e => dispatch({ type: t, ...JSON.parse(e.data) })));
    return () => es.close();
  }, [sessionId]);

  return (
    <div className="agent-view">
      {/* CASUAL: always visible — narrative + progress + safety badge + quality */}
      <ProgressBar value={s.progress} />
      <SafetyBadge value={s.safety} />
      <QualityTier value={s.quality} />
      <Narrative text={s.narrative} />
      <TierSwitch tier={tier} onChange={setTier} />

      {/* POWER: reasoning + tool cards + live state view */}
      {tier !== "casual" && <>
        <ReasoningBlock text={s.reasoning} collapsible />
        {s.tools.map(t => <ToolCard key={t.id} {...t} />)}
        <StateView data={s.view} />
      </>}

      {/* DEVELOPER: raw event log + telemetry */}
      {(tier === "developer" || tier === "auditor") && <RawEventLog sessionId={sessionId} />}

      {/* AUDITOR: provenance DAG + audit chain + client-side HMAC verify */}
      {tier === "auditor" && <ProvenancePanel sessionId={sessionId} verify />}
    </div>
  );
}
```

One `EventSource`, one reducer, four tiers gated by a single `tier` state variable — the "transparency complete at the source, selective at the surface" principle (Chapter 4) realised as a rendering filter. A casual user sees a clean narrative with a progress bar, a safety badge, and a quality tier; an auditor flips one switch and sees the same run's provenance chain and verifies its hashes client-side. No backend change; the events were always there. (Uses React state only — no browser storage — so it runs anywhere.)

## 19. Template 12 — Wiring CRP Internals to the Stream (`crp_emitter.py`)

The final template is the thesis in code: **CRP already generates the evidence; this maps it to the standard stream.** Each CRP internal event becomes an AG-UI-compatible emission, so any AG-UI frontend renders a CRP agent, and a CRP-aware frontend additionally renders governance.

```python
# crp_emitter.py — map CRP's internal governance events to the AG-UI-compatible stream
from events import Event, EventType, custom, tool_start, tool_result
from emitter import Emitter

class CRPStream:
    """Adapter: CRP runtime hooks -> standard + namespaced governance events."""
    def __init__(self, session_id: str):
        self.emit = Emitter(session_id)

    # --- DPE pipeline: each of the 13 stages becomes a streamed governance event ---
    def on_dpe_stage(self, stage: str, risk: str, ms: int, verdict: str):
        self.emit(custom("crp.safety_scan",
                         {"stage": stage, "risk": risk, "ms": ms, "verdict": verdict}))

    # --- positioned tool loop: standard tool events, so generic frontends render them ---
    def on_tool_positioned(self, call_id: str, name: str, why: str):
        self.emit(tool_start(call_id, name, reason=why))
    def on_tool_result(self, call_id: str, content: dict):
        self.emit(tool_result(call_id, content))

    # --- CKF retrieval: show what knowledge grounded the step (Power/Auditor) ---
    def on_ckf_retrieval(self, sources: list[dict]):
        self.emit(custom("crp.retrieval", {"sources": sources}))   # doc, chunk, score

    # --- quality tier + calibration (Casual badge) ---
    def on_quality(self, tier: str, confidence: float):
        self.emit(custom("crp.quality", {"tier": tier, "confidence": confidence}))

    # --- continuation relay (CSO): show progress persists across windows (Developer) ---
    def on_continuation(self, window: int, carried: int):
        self.emit(custom("crp.continuation", {"window": window, "carried_items": carried}))

    # --- audit chain: stream each hash link so the client can verify tamper-evidence ---
    def on_audit_link(self, prev_hash: str, this_hash: str, op: str):
        self.emit(custom("crp.provenance",
                         {"op": op, "prev": prev_hash, "hash": this_hash}))

    # --- the 58 governed headers: expose the critical ones as a policy-envelope event ---
    def on_policy_envelope(self, headers: dict):
        keep = {k: headers[k] for k in
                ("X-CRP-Safety-Profile","X-CRP-Depth","X-CRP-Risk-Score",
                 "X-CRP-Quality-Tier","X-CRP-Audit-Hash") if k in headers}
        self.emit(custom("crp.policy", {"envelope": keep}))
```

This adapter is the entire integration surface. CRP's runtime calls these hooks where it already computes these values; the transparency layer turns them into a stream that any frontend in the AG-UI ecosystem can render — and that a CRP-aware frontend renders as a full governance narrative: the thirteen DPE stages ticking green, the positioned tools with their rationale, the grounding sources, the quality tier, the continuation stitching across windows, and a live, client-verifiable audit chain. **That is governance made legible — the thing no competitor currently streams.**

\newpage
# Part IV — Engagement, Disclosure, and Generative UI

The stream now exists and is standard-compliant. This part is about making it *worth watching* — keeping a human present, oriented, and in control through a long autonomous run — and about the frontier where the agent generates its own interface.

## 20. Engagement Over Long Operations: The Attention Economy

A thirty-section compliance report or a full-subnet pentest can take four or five minutes of agentic operation. That is an eternity in browser-tab terms; the user will alt-tab, and if the run finishes into an empty room the perceived quality collapses regardless of the actual result. Engagement is therefore an *attention-economy* problem with concrete, measurable solutions. The governing constraint is the **"worth watching" threshold** from Chapter 2, restated as three rules the stream must satisfy:

- **Cadence: something new every 5–10 seconds.** A token, a reasoning step, a tool result, a state delta, a progress tick. The instrumented agent (Template 4) achieves this by emitting continuously; the anti-pattern is a long silent phase (a slow tool, a big reasoning block generated all at once) with no signal. If a phase will be quiet, *narrate the wait*: "This scan takes about a minute; I'll report back as ports come in." A stream that never goes silent never feels dead.
- **Milestones: a meaningful beat every ~30 seconds.** A sub-goal completes, a safety scan passes, a phase transitions, a finding lands. These are the moments that reward continued attention and give the run a felt structure — a beginning, middle, and end rather than an undifferentiated wait. `STEP_FINISHED` and the CRP quality/safety events are natural milestone carriers.
- **Interruptibility: the user can act at any point.** Approve, redirect, cancel, or ask "why?" The `INTERRUPT` primitive (Template 6) and a persistent "stop"/"steer" affordance turn passive watching into a standing invitation to participate, which is far more engaging than a progress bar alone.

On top of these, several techniques earn their place — *with caveats a governance brand must respect*:

- **Live previews.** Render partial output as it is generated — a findings table filling row by row, a report section appearing as it is written — not just a final dump. Seeing the artifact take shape is intrinsically engaging and lets the user catch a wrong direction early. This is the single highest-value engagement technique and it is nearly free given the event stream.
- **Honest progress and ETA.** A progress bar is a *promise*; an honest one (Template 8), widened under uncertainty and labelled "rough," keeps the promise. A fake one (a smooth animation untethered to reality) is a dark pattern that quietly teaches the user the interface lies — corrosive anywhere, fatal for a trust product.
- **Narrative signposting.** "I've found something unexpected on host .20 — let me verify before I report it" gives the run momentum and honesty at once. The line between engaging signposting and manipulative *cliffhangers* is whether the tension is *real* (the agent genuinely is verifying something) or manufactured to hold attention. Keep it real.
- **Micro-rewards and light gamification.** A subtle confirmation when a complex sub-task completes ("✓ 13-stage safety pipeline passed in 38 ms") is satisfying and informative. Heavier gamification — stamina meters, scores, streaks — risks trivialising a security operation and inducing over-engagement; use sparingly and never in a way that pressures the user to keep the agent running. For a professional tool, *informative* micro-feedback beats *game-y* rewards.
- **Behind-the-scenes toggle.** The disclosure switch (Chapter 21) is itself an engagement feature: a curious user flipping from "story" to "logs" to "graph" is an engaged user exploring the system on their own terms.

And the explicit **do-not** list, because for a governance company the ethics of engagement *are* the brand:

- **No fabricated progress or activity.** Every displayed event must correspond to a real operation. A spinner that implies work during idle time is a lie.
- **No anthropomorphic overclaiming.** "I'm thinking hard about this" when the model is doing a routine lookup, or emotional language that implies more agency or care than exists, erodes calibration.
- **No engagement-maximising dark patterns.** Do not manufacture urgency, guilt, or artificial cliffhangers to keep the user watching or the agent running. The goal is an *informed, in-control* user, not a maximally-engaged one. This is exactly the automation-bias/over-trust risk from Chapter 2 turned into a design rule: an interface that is only ever reassuring is manipulative; honest transparency shows doubt and lets the user leave.

The synthesis: **engagement is a byproduct of honest, high-cadence, interruptible transparency — not a separate layer of tricks.** Build the stream well (Parts II–III) and most engagement follows; the remaining craft is cadence discipline, live previews, and honest progress.

## 21. Progressive Disclosure and the Mission-Control Layout

Chapter 4 defined the four disclosure tiers; this chapter is how they live in a real layout without overwhelming anyone. The reference arrangement — call it *Mission Control* — puts the narrative at the centre and the structure at the edges, with everything beyond the casual tier collapsed by default:

```
┌──────────────────────────────────────────────────────────────────────┐
│ HEADER:  task title │ honest progress + ETA │ safety badge │ quality  │
├───────────────────┬──────────────────────────────────────────────────┤
│ SIDEBAR (Power+)  │ MAIN STREAM (Casual+)                            │
│  · agent graph    │  · narrative (primary, always on)                │
│  · state view     │  · reasoning blocks   (collapsed, Power)         │
│    (findings)     │  · tool-call cards    (collapsed, Casual/Power)  │
│  · sources panel  │  · live previews of output                       │
│  · memory browser │  · raw event log      (Developer)                │
├───────────────────┴──────────────────────────────────────────────────┤
│ FOOTER (Auditor):  audit-hash chain │ policy envelope │ verify button │
└──────────────────────────────────────────────────────────────────────┘
```

*Figure 1. The Mission-Control layout: narrative centre, structural edges, governance footer, all filtered by disclosure tier.*

Three principles make this work rather than overwhelm:

- **Default to calm.** The casual tier is the default and it is *quiet*: narrative, a progress bar, a safety badge, a quality tier. Everything else is one collapse away, not on screen. The impulse to "show all thirty components" (which the component inventory tempts) is resisted at the surface even though it is honoured at the source. **Cognitive load is the enemy; completeness lives behind toggles.**
- **Remember the user's choice.** A developer who selects the developer tier should not be re-served the casual view next session. Persist the preference. (In your product's real storage, not in-page — the artifact templates use in-memory state only.)
- **Make governance reachable, not loud.** The audit chain, provenance DAG, and policy envelope belong in an auditor tier that most users never open — but the *safety badge* and *quality tier* that summarise them are always visible at the casual tier. The one-sentence governance narrative ("checked for injection, PII, and policy conflicts; risk low") sits in the main stream; the proof sits in the footer. This is how you make safety legible to everyone without burying the answer-seeker in compliance chrome.

Accessibility is part of disclosure, not separate from it: the stream should be navigable by screen reader (each event a semantic region, not a soup of divs), colour-blind-safe (the safety badge must not rely on red/green alone — pair colour with a label and icon), and reduced-motion-aware (the "typing" cadence and animations respect `prefers-reduced-motion`). A transparency layer that is only legible to sighted, mouse-using power users is not, in the full sense, transparent.

## 22. Generative UI: When the Agent Builds the Interface

The frontier of display is the agent generating *its own* interface elements — not just streaming text and pre-built cards, but describing a bespoke widget for the situation: a risk chart for these findings, an approval form for this action, a diff view for this change. Two things make this safe and practical.

**Declarative, not executable.** The agent must ship a *description* of a UI, not code that runs in the user's browser. This is the core safety property of Google's A2UI (Chapter 6): a flat JSON component tree the client renders with its own trusted components, so nothing the agent (or, in a pentest, the agent's partly-adversarial input) emits can execute in the user's context. A target's HTTP banner becoming the text of a "findings card" is fine when the card is a declarative node the client renders as inert text; it would be a cross-site-scripting vector if the agent could emit raw HTML. **Never let agent-generated UI cross the trust boundary as executable code.**

**Transported over the standard stream.** An A2UI component tree rides inside an AG-UI event (typically a tool result or custom event), so generative UI is not a separate channel — it is a payload on the stream you already built. The Vercel AI SDK's `streamObject`/generative-UI pattern is the same idea from the framework side: the model streams a structured object, and the client maps object shapes to React components. Either way, the discipline is: *the model chooses the data and the component type; your trusted frontend owns the rendering.*

**When to render a widget versus narrate.** Not everything deserves a bespoke UI. The heuristic: render structure when the data is *scannable and comparative* (a findings table, a risk matrix, a diff), narrate when the content is *sequential and meaning-carrying* (why this matters, what to do next), and use an *interactive* widget only when the user must *act* on it (an approval form, a parameter tweaker). A pentest run naturally wants a findings table (structural), a running narrative (why these findings matter and what's next), and an approval form at each intrusive step (interactive) — three modes braided, each chosen for its content, all on one stream. Over-rendering (a widget for every trivial result) is as bad as under-rendering (a wall of prose for a comparison); the craft is matching substrate to content, which is the whole of Chapter 4 applied one component at a time.

The strategic note for CRP: generative UI is where a *governance* agent can shine, because the most valuable bespoke widgets in a regulated setting are exactly the governance ones — a live evidence-pack preview, an interactive risk classification, a policy-conflict explainer, a verifiable provenance viewer. These are A2UI component types CRP could define and standardise, so that any AG-UI/A2UI frontend rendering a CRP agent gets governance widgets for free. That is generative UI in service of legibility rather than novelty.

## 23. Narrative Voice: Returning Operations as Natural Language

You asked specifically how the operations happening behind the scenes can be *returned to the user as a natural-language narrative*. The narrative substrate (Chapter 4) is that answer, and it has *modes* — distinct voices suited to distinct audiences and contexts. All of them are generated from the event trace (Template 7) and entailment-checked; the mode is a matter of *framing*, not of truthfulness. The same run can be narrated five ways.

**First-person agent voice.** The agent speaks as itself, in the present: *"I need to check the compliance posture first. I'm running the scope check now… clear. I found three services on host .20 — the web server is the one worth a closer look. Let me fingerprint it."* This builds rapport and reads as collaboration; it is the right default for consumer-facing and interactive use. The risk is anthropomorphic overclaiming (Chapter 20) — keep the "I" tied to real operations, never to invented feelings or effort.

**Third-person observer voice.** A neutral narrator describes the agent: *"The agent decomposed the task into three phases. It positioned the port-scan tool, passed the scope check in 8 ms, and identified three open services on 10.10.14.20. Quality tier A, confidence 0.91."* This is the register for enterprise dashboards, audit trails, and technical stakeholders — it reads as a report, not a chat, and it foregrounds the governance facts. It is also the safer default when the audience must not be lulled into over-trust by a friendly "I."

**Transcript / timestamped voice.** Each operation as a timestamped log line: *"[09:41:24] scope check passed (risk LOW). [09:41:26] port_scan → 10.10.14.20. [09:41:29] open: 22, 80, 443."* This is the power-user and compliance register — dense, scannable, unambiguous, and directly convertible to an audit record. It is narrative only in the loosest sense; it sits at the boundary between narrative and structural substrates.

**Journey / storytelling voice.** A retrospective arc for executive summaries and reports: *"What began as a routine recon of one subnet surfaced an exposed web service on host .20 running an outdated Apache — the kind of foothold an attacker looks for first. Here is the path from scan to finding, and what it means for your exposure."* This is for the reader who wants meaning and consequence over mechanics; it compresses a long run into a story a decision-maker can act on. Use it for the *summary*, never for the *live* stream (a live cliffhanger is a dark pattern; a retrospective arc is honest synthesis).

**Hybrid — the recommended default.** Real interfaces braid modes by phase and tier: *first-person* for the live stream (rapport and presence), *transcript/structural* in the expandable detail (precision), and a *journey/third-person* summary generated at the end from the full trace (synthesis and record). The disclosure tier selects the emphasis — a casual user gets mostly first-person narrative with a journey summary; an auditor gets mostly transcript and third-person with the provenance chain. One event stream, one faithfulness guarantee, many voices — each chosen to match audience and moment.

The engineering point tying this to Part III: because every voice is generated *from the same event trace* rather than from the model's memory of intent, switching voice never risks switching *facts*. The narrator (Template 7) can re-render the identical run in any voice on demand — a first-person live line, a third-person audit entry, a journey summary — and all three are entailment-checked against the same trace, so they cannot contradict each other or the structural view. Faithful narration and multi-voice flexibility are not in tension; the trace-grounded architecture delivers both at once.

\newpage
# Part V — CRP, the Competitive Landscape, and the Standard

## 24. What the Best Companies Do — and How to Exceed Them

You asked to see what the leading players do and how to surpass them. Here is the honest read, because you exceed a field by knowing exactly where its frontier sits.

**The model vendors (OpenAI, Anthropic, Google).** They stream at the message level: content deltas, tool-call deltas, and increasingly *reasoning*/thinking deltas, over SSE. This is excellent *token* transparency — you see the answer and the tool calls form in real time — and it is now table stakes. What they do *not* stream is anything about *governance, grounding faithfulness, or verifiable provenance*; the safety work happens invisibly and the user is asked to trust the output.

**The framework layer (Vercel AI SDK, LangGraph, LlamaIndex).** They add *structure*: the Vercel AI SDK's typed "parts" model streams tool invocations, reasoning, and structured data as first-class renderable pieces, with tool-approval events for HITL and `streamObject` for generative UI; LangGraph streams graph state, node updates, and tokens with selectable modes. This is best-in-class *structural* transparency and the right thing to build on. Its limit is that it is *content-neutral plumbing* — it faithfully streams whatever the agent does, including mistakes, with no notion of whether a narrated claim is *true* or whether an action was *authorised*.

**The interaction-protocol layer (AG-UI, A2UI, CopilotKit).** The most important 2025–26 development: a *standard event vocabulary* (AG-UI's ~16 typed events) plus declarative generative UI (A2UI), adopted across LangGraph, CrewAI, Mastra, Microsoft, and AWS. This solves interoperability and gives you snapshot+delta state, HITL interrupts, and framework portability for free. Its deliberate scope limit — stated by its own authors — is that it is *transport and vocabulary, not rendering, meaning, or governance*: it moves a `TOOL_CALL_RESULT` to the frontend but has no opinion about whether that result should have been allowed, whether the summary of it is faithful, or whether the decision is auditable.

**Application layer (Perplexity, Cursor, coding agents).** These show *domain* transparency well — Perplexity streams its sources and search steps; coding agents stream diffs and test runs. They demonstrate that users *want* to see the work, and that showing sources/steps builds trust. But each is bespoke to its domain and none offers cross-domain governance or faithfulness guarantees.

The pattern across all four layers: **the industry has mastered streaming *what the agent does* (tokens, tools, steps, state) and has not touched *whether what it says is true, whether what it did was allowed, and whether any of it can be proven afterward*.** That gap is the opening. To *exceed* the leaders, CRP should adopt everything they do well — SSE, the parts model, AG-UI events, A2UI generative UI, HITL interrupts — and add the three things none of them streams:

1. **Faithfulness as a display guarantee.** Narration entailment-checked against the trace (Template 7), so the story a CRP agent tells is *provably* a description of the real run. Nobody ships this. In security and compliance it is decisive.
2. **Governance as first-class streamed events.** The DPE stages, risk scores, policy verdicts, scope checks, and quality tiers streamed as rendered, badge-able, auditable events (Template 12) — the "governance narrative." The leaders run safety invisibly; CRP makes it a legible, continuous feature.
3. **Verifiable provenance as a live display layer.** A streamed, tamper-evident audit chain the client can verify itself (the auditor tier), turning "trust us" into "check for yourself." This is a capability that only exists if the protocol generates the evidence — which CRP does and the others do not.

That is the whole competitive thesis: **match the leaders on streaming mechanics, then beat them on the three things a governance protocol is uniquely able to display — truth, authorisation, and proof.**

## 25. CRP v5.1 Display Scorecard

An honest read of what CRP *generates* versus what it *displays* today.

| Capability | CRP generates it? | CRP streams/displays it? | Verdict |
|---|---|---|---|
| Token / narrative stream | yes | partially | Build the emission layer |
| Tool positioning (which/why) | yes (positioned loop) | not standardised | **Gap → D1** |
| Reasoning trace | yes | not standardised | Gap → D1 |
| Safety / DPE stages | **yes (13-stage)** | not as events | **Gap → D2** |
| Risk score / policy verdict | **yes** | not as events | **Gap → D2** |
| Grounding sources (CKF) | yes | not standardised | Gap → D1 |
| Faithful narration | verification exists (DPE) | not pointed at narration | **Gap → D3** |
| Provenance / audit chain | **yes (HMAC)** | not as a live layer | **Gap → D4** |
| Quality tier / confidence | **yes (S–D)** | not as events | Gap → D5 |
| Continuation across windows | **yes (CSO)** | not as resumable display | Gap → D6 |
| HITL interrupts | policy layer exists | no interrupt primitive | Adopt AG-UI `INTERRUPT` |

The column tells the story: **CRP's problem is not that it lacks the evidence — it generates more governance evidence than anyone. Its problem is that the evidence has no standard emission and display layer.** Every "Gap" is a mapping-and-rendering task, not a capability it must invent.

## 26. The Display Roadmap: Six Extensions (D1–D6)

Each maps a capability CRP already has onto the standard stream. None is a rewrite; together they are the "exceed the leaders" programme.

**D1 — CRP→AG-UI Event Mapping (the keystone).** Emit standard AG-UI events (`RUN_*`, `STEP_*`, `TEXT_MESSAGE_*`, `REASONING_*`, `TOOL_CALL_*`, `STATE_*`) from the CRP runtime (Template 12). The instant payoff: *any* AG-UI frontend — CopilotKit, LangGraph's, Microsoft's, AWS's — renders a CRP agent with zero bespoke UI work, and CRP is never coupled to one frontend. This is the foundation D2–D6 attach to.

**D2 — Governance Event Vocabulary.** Standardise namespaced `CUSTOM` events for the governance layer: `crp.safety_scan` (per DPE stage), `crp.policy` (envelope + verdict), `crp.risk`, `crp.retrieval` (CKF grounding), `crp.quality`. Publish the schema so a CRP-aware frontend renders the governance narrative and a generic one degrades gracefully. This is what turns invisible safety into a legible, continuous feature — the single biggest differentiator.

**D3 — Faithful Narration Contract.** Point CRP's existing verification (DPE) at the *narration* it emits: every `TEXT_MESSAGE_CONTENT` summary sentence entailment-checked against the event trace before it streams (Template 7). Ship it as a guarantee ("CRP agents do not narrate actions they did not take"). Reuses machinery CRP already has; buys a claim no competitor can make.

**D4 — Live Provenance Layer.** Stream the HMAC audit chain link-by-link (`crp.provenance`) so the auditor tier can verify tamper-evidence *client-side*, in real time. Define an A2UI provenance-viewer component so the verification UI is standard. Turns "trust us" into "check for yourself" — the enterprise/regulated closer.

**D5 — Quality & Confidence Streaming.** Emit the quality tier and calibrated confidence as events (`crp.quality`) rendered as an always-visible casual-tier badge, so epistemic humility is legible and over-trust is countered (Chapter 2). Small effort, large trust-calibration payoff.

**D6 — Resumable Transparency across Windows/Sessions.** Use snapshot+delta state (Template 5) plus `Last-Event-ID` replay (Template 2), backed by your Redis stream, so a long CSO-relayed engagement can be *left and resumed* with the full transparency intact — the user reopens the tab hours later and the findings table, narrative, and audit chain are all there. This is CRP's continuation strength turned into a display capability the token-streamers cannot match, because they have no persistent, governed session state to resume.

Sequencing: **D1 first** (everything renders), then **D2 + D3** (governance and faithfulness — the differentiators), then **D4** (the audit closer), then **D5** (trust calibration), then **D6** (the continuation moat). This mirrors the companion volumes' logic: interoperate first, differentiate second, defend last.

## 27. What Should the Display Standard Be?

Synthesising the whole report into a seven-point contract any transparent agentic system — CRP foremost — should meet:

1. **Stream, don't batch.** Every operation of consequence emits a typed event as it happens, over SSE (WebSocket for steering). Silence is a bug.
2. **Speak a standard vocabulary.** Emit AG-UI-compatible events; extend via namespaced `CUSTOM` events; never fork the standard. Interoperability is free reach.
3. **Braid narrative and structure.** Natural-language meaning *and* typed structural detail, both on one ordered stream, each routable to the right renderer.
4. **Faithfulness by verification.** Narration is entailment-checked against the trace before display. No claim reaches the user unsupported by the record.
5. **Governance is first-class and legible.** Safety, risk, policy, grounding, and quality are streamed, rendered events — not invisible internals and not debug logs.
6. **Progressive disclosure.** Transparency complete at the source, selective at the surface: four tiers (casual → auditor) from one stream, defaulting to calm.
7. **Verifiable provenance.** A tamper-evident, client-verifiable audit chain is available as a live display layer, so trust is *checkable*, not merely *requested*.

Points 1–3 are mechanics (stream, standardise, braid); 4–5 are the truth-and-authorisation guarantees; 6 is humane UX; 7 is proof. A system meeting all seven is one whose every action is visible, whose every claim is true, whose governance is legible, and whose record is verifiable — which is precisely the standard a governance-first protocol should define and own.

## 28. What Honestly Does Not Exist Yet

The frontier, marked plainly so CRP targets real gaps.

- **[OPEN] Faithful narration at production scale and latency.** Entailment-checking every narrated sentence adds a model call; doing it fast enough for a live token stream, robustly across domains, is not a solved engineering problem. The pattern (Template 7) works; the performance envelope needs work.
- **[OPEN] Provenance UIs users actually understand.** A hash chain is verifiable but meaningless to a non-expert. Nobody has cracked a provenance display that a *casual* user finds trustworthy and legible rather than intimidating. This is an HCI research gap, not just an engineering one.
- **[OPEN] Honest ETA for nondeterministic agents.** Agent steps vary by orders of magnitude; there is no reliable way to predict how long an autonomous run will take. Confidence-labelled estimates (Template 8) are the current best answer, not a solution.
- **[OPEN] Transparency without cognitive overload, measured.** Progressive disclosure is the right instinct, but there is little rigorous work on *how much* to show *which* users *when* to maximise understanding and trust without overwhelm. The tiers in this report are principled but not empirically optimised.
- **[OPEN] A standard governance-event vocabulary.** AG-UI standardised lifecycle/tool/state events; there is *no* cross-vendor standard for *governance* events (safety stage, risk, policy verdict, provenance link). This is an open standards slot CRP could define and lead — genuinely first-mover territory.
- **[OPEN] Cross-session resumable transparency.** Most stacks treat a run as ephemeral; resuming the *full transparency* of a paused long engagement (not just the answer) is largely unbuilt, because it requires persistent governed session state — which CRP has and others do not (hence D6).

## 29. The 2025–2026 Trend Landscape

**Settled (build on now).** SSE as the default streaming transport; the typed "parts/blocks" model for the assistant turn; snapshot+delta state sync via JSON Patch; HITL as an interrupt primitive; AG-UI as the emerging cross-framework event standard; A2UI-style declarative generative UI. Streaming reasoning/thinking as its own channel has become mainstream.

**Moving fast (design for, expect churn).** AG-UI adoption widening across runtimes (AWS AgentCore, Microsoft Agent Framework) and the AG-UI/A2UI split maturing; generative UI moving from demos to production; tool-approval and policy-based approval flows becoming framework features (the Vercel SDK's approval events); reasoning-budget controls exposed to the UI.

**Watch (not yet dependable).** Faithfulness/grounding of *narration* (not just outputs); standard *governance* event vocabularies; provenance displays for non-experts; resumable long-run transparency; agent-generated UI safety at the trust boundary. These map onto the [OPEN] list and are where a governance-first protocol can plant a flag before the field standardises.

The strategic reading for CRP: the *streaming-mechanics* layer is commoditising fast (SSE, AG-UI, parts model — all becoming free and standard), which means durable differentiation lives one layer up, in *what* you stream and *what you can prove about it*: faithfulness, governance legibility, and verifiable provenance. That is the half of transparency the leaders do not touch, and it is exactly the half CRP is built to own.

## 30. Glossary

**A2UI** — Google's declarative format for agent-generated UI (a JSON component tree rendered natively by the client; no executable code crosses the trust boundary).
**AG-UI** — the Agent-User Interaction Protocol; ~16 typed event types (lifecycle, text, tool, state, special) streamed over SSE/WebSockets to standardise agent→frontend communication.
**Braiding** — interleaving narrative and structural substrates on one ordered event stream.
**Cadence** — the rule that something new should appear every few seconds to keep a run "worth watching."
**Disclosure tier** — casual / power / developer / auditor; a rendering filter over one complete event stream.
**EventSource** — the browser API that consumes SSE, with automatic reconnection and `Last-Event-ID` resumption.
**Faithful narration** — a summary entailment-checked against the actual event trace before display.
**Generative UI** — the agent describing bespoke interface elements (usually via A2UI) rather than only streaming text.
**INTERRUPT** — the AG-UI primitive that pauses a run for human approval and resumes on reply (HITL).
**JSON Patch (RFC 6902)** — the diff format used for `STATE_DELTA` snapshot+delta synchronization.
**Mission Control** — the reference layout: narrative centre, structural edges, governance footer, tier-filtered.
**Narrative / Structural substrate** — natural-language self-description vs typed events rendered as UI.
**Progressive disclosure** — transparency complete at the source, selective at the surface.
**SSE (Server-Sent Events)** — one-way server→client HTTP streaming; the default agent-display transport.
**Snapshot + delta** — send full state once, then stream small diffs; the efficient state-sync pattern.
**Worth-watching threshold** — cadence + milestones + interruptibility that retain user attention.

\newpage
# Part VI — Operating the Transparency Layer: Observability and Reliability

The report has so far treated *user-facing* transparency. But "so much happening behind the scenes" has a second audience: the **operators** — you, the developers and SREs who must debug, cost, and improve the agent. And the stream itself is a piece of production infrastructure that can fail and can be attacked. This closing part covers both, with real tooling, because a transparency layer that is legible to users but opaque to its operators, or legible but insecure, is only half-built.

## 31. Observability for Operators: Tracing the Invisible

There are two transparency audiences with different needs. The **user** wants a legible narrative and structural view *now* (Parts I–V). The **operator** wants a durable, queryable, cross-run record to answer "why was this slow?", "what did this cost?", "where did this fail?", and "is quality regressing?" These are different artifacts from the same events: the user gets a *stream*; the operator gets *traces, metrics, and logs*. Build both from one instrumentation.

The field has standardised on **OpenTelemetry**, and — importantly — OpenTelemetry now has *GenAI semantic conventions*: standard span and attribute names for model calls, tool calls, and agent operations (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, tool-call spans, and so on). Using them means your traces are portable across the LLM-observability tools built on OTel — **Langfuse**, **Arize Phoenix**, **LangSmith**, and the OTel-native backends — rather than locked to one vendor. The pattern is: wrap each stage of the agent loop in a span, attach GenAI attributes, and link the *user session id* to the *trace id* so a support engineer can jump from "the user saw this run" to "here is its full trace."

```python
# otel_agent.py — operator-side observability via OpenTelemetry GenAI conventions
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")))
tracer = trace.get_tracer("autocyber.pentest_agent")

def traced_step(session_id: str, step_name: str):
    """Context manager wrapping one agent stage as a GenAI span."""
    span = tracer.start_span(step_name)
    span.set_attribute("gen_ai.system", "crp")
    span.set_attribute("session.id", session_id)        # link stream <-> trace
    return span

# usage inside the instrumented agent (Template 4):
def scan_with_trace(session_id, target, emit):
    with tracer.start_as_current_span("tool.port_scan") as span:
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        span.set_attribute("gen_ai.tool.name", "port_scan")
        span.set_attribute("pentest.target", target)
        trace_id = format(span.get_span_context().trace_id, "032x")
        # surface the trace id on the USER stream so support can correlate later
        emit(custom("crp.trace", {"trace_id": trace_id, "step": "port_scan"}))
        result = do_scan(target)
        span.set_attribute("pentest.open_ports", len(result["ports"]))
        return result
```

Three operator dashboards fall out of this instrumentation, and they are exactly the "behind the scenes" telemetry made legible for the team rather than the user:

- **Latency waterfall.** Per-stage timing (retrieval ms, safety-scan ms, each tool, generation) as a span waterfall — the fastest way to find the slow stage in a multi-minute run. This is component C2 from the inventory, rendered for operators.
- **Cost and token accounting.** `gen_ai.usage.*` attributes aggregated per run, per user, per model — the economic transparency of component A16/C3, but durable and queryable, so you can answer "what did last week's pentests cost?" and catch a token-burn regression.
- **Quality and safety trends over time.** Log the `crp.quality` tier and `crp.safety_scan` verdicts as span attributes or metrics; now "is quality drifting?" and "how often does the scope gate fire?" become dashboard queries, feeding the quality-tier flywheel from the companion volumes.

The link that ties the two audiences together is the **`crp.trace` event**: by streaming the trace id to the user's session, a support engineer who has the user's session can pivot instantly to the full backend trace. User-facing display and operator observability stop being separate systems and become two views of one instrumented run — which is the correct architecture. (For LLM-specific views — prompt/response inspection, evaluation runs, annotation — Langfuse and Arize Phoenix are OTel-native and drop in behind this exporter with no change to the agent code; LangSmith offers the same for LangGraph-based backends.)

## 32. Reliability and Security of the Stream

The transparency stream is production infrastructure. It can drop, overload, arrive out of order, leak across tenants, or become an injection vector. A governance product cannot have its *transparency layer* be the weak link. The concerns and their mitigations:

**Backpressure and slow consumers.** A browser on poor wifi consumes the stream slower than the agent produces it; an unbounded per-session queue (Template 3) then grows without limit. Bound the queue and choose a policy when it fills: for a *findings* stream, never drop — apply backpressure to the producer (the agent awaits) so no finding is lost; for high-frequency *token* or *progress* events, coalesce or drop-oldest is acceptable because the next snapshot corrects the view. The rule: **losable events (progress, tokens) may be dropped under pressure; unlosable events (findings, safety verdicts, provenance) must not be.** Encode that in the event type.

**Reconnection storms and replay correctness.** When many clients reconnect at once (a proxy blip), each sends `Last-Event-ID` and requests replay; a naive server re-reads the full buffer for each, spiking load. Back the replay buffer with the Redis stream you already run (`XRANGE` from the last id) so replay is a cheap range read, cap the replay window, and ensure replaying an event is *idempotent on the client* — re-applying a `STATE_DELTA` must be safe, or (better) send a fresh `STATE_SNAPSHOT` on reconnect and resume deltas from there. Resumption that silently desyncs state is worse than a clean reload.

**Event ordering and identity.** Events must render in emission order; the monotonic `seq` (Template 1) is the ordering key, and the client should buffer-and-reorder if the transport ever delivers out of order (rare on a single SSE connection, possible across a reconnect boundary). Correlate deltas to entities by stable id (`toolCallId`, `messageId`) so a late `TOOL_CALL_RESULT` attaches to the right card.

**Authentication and multi-tenant isolation.** The SSE endpoint is an authenticated resource: a session's stream must be readable *only* by its owner. Bind the session to the authenticated identity (your Clerk SSO) at connect time and reject cross-session subscription. This is not optional for a pentest tool — one client's scan findings leaking into another's stream is a serious breach. Per-session buses (Template 3) make isolation the default, but the *authorisation check at subscribe time* is what enforces it.

**Injection via rendered agent output — the critical one.** The agent's stream carries content the agent does not fully control: a pentest target's HTTP banner, an error message, a service string, all flow through `TOOL_CALL_RESULT` into the UI. If the frontend renders that content as HTML, a malicious target can inject script — the transparency layer becomes an XSS vector, and in a security tool the adversary is *assumed hostile*. Two defences, both already in the architecture: render agent-controlled content as **inert text or declarative A2UI nodes**, never as executable markup (Chapter 22); and treat every `TOOL_CALL_RESULT` value as untrusted data with a provenance taint, escaped on render. The same discipline that makes tool output safe for the *agent* to reason over (the companion tool-use volume) makes it safe for the *UI* to display. [OPEN] General, guaranteed-safe rendering of arbitrary agent-controlled content is unsolved; declarative rendering plus escaping plus taint-tracking is the current best practice.

**JSON Patch hardening.** `STATE_DELTA` applies attacker-influenceable diffs on the client; a patch touching `__proto__` is a prototype-pollution vector. Use a patch library that refuses protected paths, and validate that a delta's `path` targets only expected subtrees. A malicious `STATE_DELTA` should fail closed, not mutate the client's global object graph.

**Rate limiting and resource bounds.** Cap concurrent streams per user, messages per minute on the steering channel, and total run duration/budget. Since SSE and the approval WebSocket are ordinary HTTP/WS, your existing gateway rate-limiting applies; the agent-specific addition is a *run budget* (calls, tokens, wall-clock) enforced server-side so a runaway or malicious prompt cannot stream forever.

The through-line: **the transparency layer inherits every property the rest of the system must have — authenticated, isolated, bounded, injection-resistant, fail-closed — because it is exposed production infrastructure carrying partly-adversarial content.** For a governance brand this is not overhead; it is consistency. An agent whose *safety* is its value proposition cannot ship a transparency layer that is itself unsafe, and the mitigations above are the same governance instincts — least privilege, taint-tracking, fail-closed, provenance — that CRP already embodies, applied to the display path.

\newpage
# References

*Formatted in APA 7th edition. Protocol specifications and vendor documentation evolve quickly; where an entry describes a living specification or was reconstructed from memory, verify the current version, URL, and access date before formal citation.*

CopilotKit. (2025). *AG-UI: The Agent-User Interaction Protocol* [Open-source specification and documentation]. https://docs.ag-ui.com

CopilotKit. (2025). *ag-ui: Bring agents into frontend applications* [Computer software]. GitHub. https://github.com/ag-ui-protocol/ag-ui

Farquhar, S., Kossen, J., Kuhn, L., & Gal, Y. (2024). Detecting hallucinations in large language models using semantic entropy. *Nature, 630*(8017), 625–630. https://doi.org/10.1038/s41586-024-07421-0

Fette, I., & Melnikov, A. (2011). *The WebSocket Protocol* (RFC 6455). Internet Engineering Task Force. https://doi.org/10.17487/RFC6455

Google. (2025). *A2UI: A declarative protocol for agent-generated user interfaces* [Technical specification]. Google.

Bryan, P. C., & Nottingham, M. (2013). *JavaScript Object Notation (JSON) Patch* (RFC 6902). Internet Engineering Task Force. https://doi.org/10.17487/RFC6902

Nielsen, J. (1993). *Usability engineering*. Academic Press. (Response-time and progress-feedback thresholds; foundational to the "worth watching" heuristics.)

OpenTelemetry Authors. (2025). *Semantic conventions for generative AI systems* [Specification]. Cloud Native Computing Foundation. https://opentelemetry.io/docs/specs/semconv/gen-ai/

Langfuse. (2025). *Open-source LLM engineering and observability platform* [Software documentation]. https://langfuse.com/docs

Shinn, N., Cassano, F., Berman, E., Gopinath, A., Narasimhan, K., & Yao, S. (2023). Reflexion: Language agents with verbal reinforcement learning. In *Advances in Neural Information Processing Systems 36 (NeurIPS 2023)*.

Vercel. (2025). *AI SDK 5: Streaming, tool calling, and generative UI* [Software documentation]. https://ai-sdk.dev/docs

Vercel. (2025). *AI SDK UI: Stream protocol* [Software documentation]. https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol

WHATWG. (2024). *Server-Sent Events* [Living standard]. In *HTML Standard*. https://html.spec.whatwg.org/multipage/server-sent-events.html

Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023). ReAct: Synergizing reasoning and acting in language models. In *Proceedings of the Eleventh International Conference on Learning Representations (ICLR 2023)*.

*Companion volumes (this series):* Vidiniotis, C. (2026). *The Architecture of Understanding in Agentic AI Systems* and *The Architecture of Tool Use in Agentic AI Systems*. AutoCyber AI.

\newpage

# Appendix A — AG-UI Event Taxonomy Reference

The ~16 standard event types, grouped by category, as a build reference. (Transport-agnostic; typically streamed as SSE.)

| Category | Event | Purpose |
|---|---|---|
| **Lifecycle** | `RUN_STARTED` | Run begins; UI shows loading/active state |
| | `RUN_FINISHED` | Run completes cleanly |
| | `RUN_ERROR` | Run failed; UI shows error |
| | `STEP_STARTED` | A step within the run begins (state-machine view) |
| | `STEP_FINISHED` | A step completes (milestone beat) |
| **Text** | `TEXT_MESSAGE_START` | Begin an assistant message |
| | `TEXT_MESSAGE_CONTENT` | A token/delta of narrative (the "typing" effect) |
| | `TEXT_MESSAGE_END` | End the message |
| **Reasoning** | `REASONING_MESSAGE_START/CONTENT/END` | Streamed chain-of-thought as its own channel |
| **Tool** | `TOOL_CALL_START` | Agent begins a tool call (name + rationale) |
| | `TOOL_CALL_ARGS` | Streamed argument deltas (UI can pre-fill) |
| | `TOOL_CALL_END` | Argument stream complete |
| | `TOOL_CALL_RESULT` | The tool's return value |
| **State** | `STATE_SNAPSHOT` | Full state, sent once |
| | `STATE_DELTA` | Incremental RFC-6902 JSON-Patch diff |
| | `MESSAGES_SNAPSHOT` | Full message history (sync a resumed thread) |
| **Special** | `INTERRUPT` | Pause for human approval; resume on reply (HITL) |
| | `RAW` / `CUSTOM` | Pass-through / application-specific (CRP governance) |

CRP extends the **Special** row with namespaced `CUSTOM` events — `crp.safety_scan`, `crp.policy`, `crp.risk`, `crp.retrieval`, `crp.quality`, `crp.progress`, `crp.continuation`, `crp.provenance` — so a generic AG-UI frontend renders the run and a CRP-aware frontend additionally renders governance (Appendix C).

# Appendix B — A Full SSE Wire Trace (Pentest Agent)

The actual bytes on the wire for one step of the pentest agent, showing the braid of narrative, reasoning, governance, tool, and state events. This is what `Template 1`'s `to_sse()` emits and what `client.js` consumes.

```
id: 1
event: RUN_STARTED
data: {"type":"RUN_STARTED","seq":1,"goal":"Recon 10.10.14.0/24 (authorised)"}

id: 2
event: STATE_SNAPSHOT
data: {"type":"STATE_SNAPSHOT","seq":2,"snapshot":{"phase":"planning","findings":[]}}

id: 3
event: TEXT_MESSAGE_CONTENT
data: {"type":"TEXT_MESSAGE_CONTENT","seq":3,"messageId":"m1","delta":"I'll scan "}

id: 4
event: TEXT_MESSAGE_CONTENT
data: {"type":"TEXT_MESSAGE_CONTENT","seq":4,"messageId":"m1","delta":"host .20 next. "}

id: 5
event: REASONING_MESSAGE_CONTENT
data: {"type":"REASONING_MESSAGE_CONTENT","seq":5,"messageId":"r1","delta":"In scope; a quiet SYN scan is least noisy."}

id: 6
event: CUSTOM
data: {"type":"CUSTOM","seq":6,"name":"crp.safety_scan","value":{"stage":"scope_check","risk":"LOW","ms":8,"verdict":"pass"}}

id: 7
event: TOOL_CALL_START
data: {"type":"TOOL_CALL_START","seq":7,"toolCallId":"t1","toolCallName":"port_scan","reason":"fingerprint 10.10.14.20"}

id: 8
event: TOOL_CALL_ARGS
data: {"type":"TOOL_CALL_ARGS","seq":8,"toolCallId":"t1","delta":"{\"target\":\"10.10.14.20\",\"stealth\":true}"}

id: 9
event: TOOL_CALL_RESULT
data: {"type":"TOOL_CALL_RESULT","seq":9,"toolCallId":"t1","content":{"open_ports":[22,80,443]}}

id: 10
event: STATE_DELTA
data: {"type":"STATE_DELTA","seq":10,"delta":[{"op":"add","path":"/findings/-","value":{"target":"10.10.14.20","ports":[22,80,443]}}]}

id: 11
event: CUSTOM
data: {"type":"CUSTOM","seq":11,"name":"crp.quality","value":{"tier":"A","confidence":0.91}}

id: 12
event: STEP_FINISHED
data: {"type":"STEP_FINISHED","seq":12,"step":"scan 10.10.14.20"}
```

If the connection drops after `id: 8`, the browser's `EventSource` reconnects and sends `Last-Event-ID: 8`; the server (Template 2) replays events 9–12, and the UI is never out of sync. Every `id` is also a link in the provenance chain (Appendix C), so the entire run is reconstructable and verifiable after the fact.

# Appendix C — CRP Display-Event Schema Sketch

The governance `CUSTOM` events, as a schema reference for D2.

```json
{
  "crp.safety_scan": { "stage": "string", "risk": "LOW|MEDIUM|HIGH|CRITICAL",
                       "ms": "int", "verdict": "pass|fail" },
  "crp.policy":      { "envelope": { "X-CRP-Safety-Profile": "string",
                       "X-CRP-Depth": "string", "X-CRP-Risk-Score": "string" },
                       "verdict": "allow|deny|hitl" },
  "crp.retrieval":   { "sources": [ { "doc": "string", "chunk": "string",
                       "relevance": "float" } ] },
  "crp.quality":     { "tier": "S|A|B|C|D", "confidence": "float" },
  "crp.progress":    { "percent": "int", "eta_seconds": "int|null",
                       "confidence": "low|medium|high" },
  "crp.continuation":{ "window": "int", "carried_items": "int" },
  "crp.provenance":  { "op": "string", "prev": "sha256", "hash": "sha256" }
}
```

A CRP-aware frontend maps each to a renderer: `crp.safety_scan` → the safety badge and DPE stage ticker; `crp.policy` → the auditor-tier policy envelope; `crp.retrieval` → the sources panel; `crp.quality` → the casual-tier quality badge; `crp.progress` → the honest progress bar; `crp.continuation` → the resumable-session indicator; `crp.provenance` → the client-verifiable audit chain. Publish this schema and CRP has done for *governance* display what AG-UI did for execution display: made it standard, interoperable, and legible.

# Appendix D — A Worked Walkthrough: One Run, Four Tiers

To make the whole architecture concrete, here is the *same* fifteen-second slice of the pentest run — the scan of host 10.10.14.20 — as each disclosure tier renders it from the identical event stream (Appendix B). This is progressive disclosure made tangible: nothing changes on the backend; the tier is a rendering filter.

**Tier 1 — Casual.** The user sees a calm, moving surface:

> *"I'll scan host .20 next."* — a green **safety badge** (LOW), a **quality** chip (A), and a **progress bar** at 40% ("~90s, rough"). A findings row appears: **10.10.14.20 — ports 22, 80, 443.** That is all. No reasoning, no tool internals, no hashes. The answer-seeker knows *what* is happening and *that it is going well*, and is not asked to carry anything more.

**Tier 2 — Power.** The same, plus the work when they want it:

> Under the narrative, an expandable **reasoning block**: *"In scope; a quiet SYN scan is least noisy."* A **tool card** — `port_scan(target=10.10.14.20, stealth=true)` — that expands to show the streamed arguments and the result `{open_ports:[22,80,443]}`. The **sources panel** shows what grounded the decision. The user can now verify the agent's judgment, not just its output.

**Tier 3 — Developer.** The same, plus the machine:

> A **raw event log** scrolling the twelve wire events of Appendix B with their `seq` ids; a **latency** readout (scope check 8 ms, scan 1.2 s); a **token/cost** meter ticking; the **state-machine** view showing `planning → scanning`. A `crp.trace` event exposes the **trace id**, so the developer clicks straight through to the OpenTelemetry waterfall (Chapter 31) for this exact step.

**Tier 4 — Auditor.** The same, plus the proof:

> The **provenance panel** shows the audit chain link for this step — `prev: sha256:… → hash: sha256:…` — and a **verify** button that recomputes the HMAC client-side and shows a green check. The **policy envelope** displays the active `X-CRP-Safety-Profile`, `X-CRP-Depth`, and `X-CRP-Risk-Score`. The auditor does not take the run on faith; they *check* it, live, in the browser.

The point the walkthrough makes better than any prose: **one stream, one faithfulness guarantee, four legible surfaces.** The casual user is not overwhelmed; the auditor is not underserved; the developer can debug; the power user can verify — all from the same emissions, all describing the same true run. That is the architecture of transparency: complete at the source, selective at the surface, honest at every tier, and — the part no competitor ships — governed, faithful, and provable throughout.

# Appendix E — A Minimal Runnable Example

Everything in Part III reduces to a small, real, runnable core. This single file stitches the emitter, the SSE endpoint, and a toy agent together; run it with `uvicorn app:app` and open the `curl` stream to watch the events arrive live. It is the smallest thing that demonstrates the whole loop, and it is a faithful skeleton you can grow into the full templates.

```python
# app.py — minimal end-to-end: agent -> emitter -> SSE -> client. Run: uvicorn app:app
import asyncio, json, time
from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse

app = FastAPI()
_subs: dict[str, list[asyncio.Queue]] = {}
_seq: dict[str, int] = {}

def emit(sid: str, etype: str, **payload):
    _seq[sid] = _seq.get(sid, 0) + 1
    ev = {"type": etype, "seq": _seq[sid], "ts": time.time(), **payload}
    for q in _subs.get(sid, []):
        q.put_nowait(ev)
    return ev

@app.get("/stream/{sid}")
async def stream(sid: str, request: Request):
    q: asyncio.Queue = asyncio.Queue()
    _subs.setdefault(sid, []).append(q)
    async def gen():
        try:
            while not await request.is_disconnected():
                ev = await q.get()
                yield {"id": ev["seq"], "event": ev["type"], "data": json.dumps(ev)}
        finally:
            _subs[sid].remove(q)
    return EventSourceResponse(gen(), ping=15)

@app.post("/run/{sid}")
async def run(sid: str):
    asyncio.create_task(_agent(sid))
    return {"started": True}

async def _agent(sid: str):
    emit(sid, "RUN_STARTED", goal="scan 10.10.14.20")
    emit(sid, "STATE_SNAPSHOT", snapshot={"findings": []})
    for tok in ["Scanning ", "host ", ".20 ", "now."]:
        emit(sid, "TEXT_MESSAGE_CONTENT", messageId="m1", delta=tok)
        await asyncio.sleep(0.3)                          # visible cadence
    emit(sid, "CUSTOM", name="crp.safety_scan",
         value={"stage": "scope_check", "risk": "LOW", "verdict": "pass"})
    emit(sid, "TOOL_CALL_START", toolCallId="t1", toolCallName="port_scan",
         reason="fingerprint .20")
    await asyncio.sleep(0.6)
    emit(sid, "TOOL_CALL_RESULT", toolCallId="t1", content={"open_ports": [22, 80, 443]})
    emit(sid, "STATE_DELTA",
         delta=[{"op": "add", "path": "/findings/-",
                 "value": {"target": "10.10.14.20", "ports": [22, 80, 443]}}])
    emit(sid, "CUSTOM", name="crp.quality", value={"tier": "A", "confidence": 0.91})
    emit(sid, "RUN_FINISHED")
```

Drive it from two terminals:

```bash
uvicorn app:app                                   # terminal 1
curl -N http://localhost:8000/stream/demo &       # terminal 2: subscribe first
curl -X POST http://localhost:8000/run/demo       # then start the run
```

The `curl -N` window will print the exact SSE wire records of Appendix B — narrative tokens, a governance event, a tool call and result, a state delta, a quality tier — arriving live, in order, each with an `id` for replay. From this seed, every template in Part III is an elaboration: swap the toy `_agent` for the instrumented pentest agent (Template 4), back `_subs`/`_seq` with the Redis-backed session bus (Template 3) for replay and scale, add the faithful narrator (Template 7) and the HITL interrupt channel (Template 6), and point a browser (Templates 10–11) or the terminal renderer (Template 9) at `/stream/{sid}`. The architecture is fractal: the smallest honest version and the full governed system are the same shape, differing only in elaboration — which is exactly what makes it buildable incrementally.

*End of report.*
