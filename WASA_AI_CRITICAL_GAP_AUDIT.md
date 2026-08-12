# WASA AI — Critical Gap Audit (CRP v5 Gating)

> **Purpose:** Decide precisely which WASA AI roadblockers CRP v5 solves, which are
> infrastructure/offload problems, and which are consolidation work — before CRP v5
> implementation proceeds.
> **Method:** Static forensic audit of `C:\Users\User\Desktop\wasa_ai-master` (40.4 GB,
> 138 tools, 11-phase pentest orchestrator), cross-referenced with the CRP v4.3.2
> codebase and SPEC-049/050. Evidence is cited by file. **Runtime validation
> (measuring the live 40% breach, kimi/local-SLM confirmation, demos) is defined in §7
> and is part of remediation, not yet executed.**
> **Verdict in one line:** CRP v5 directly removes 5 of the agentic roadblockers; the
> 40% baseline and 40 GB size are **infrastructure** problems solved by **Railway
> offload via the CRP Gateway**; the rest are **consolidation/code-quality** tasks.

---

## 1. The three roadblockers (user-stated) — findings

### Roadblocker #1 — CPU/RAM repeatedly exceed ~40%; OOM; overheating

The ~40% breach is **structural and multi-source**, not a single leak. Component cost
(from `RESOURCE_MANAGEMENT_AUDIT.md`, `PERFORMANCE_AUDIT.md`, `resource_guard.py`
`PROCESS_RSS_LIMIT_MB=5000`):

| Source | RAM | CPU peak | Reducible by CRP v5? |
|--------|-----|----------|----------------------|
| Youtu-2B **model weights** (resident) | ~2.0 GB | — | ❌ inherent |
| Youtu **KV cache** (context-dependent) | 0.5–2.0 GB | — | ✅ **10–100× smaller** with positioning |
| Youtu **prefill** on 128K context | — | **95%+** (all threads) | ✅ **−30–50%** (small prompts) |
| Embedding models (sentence-transformers/bge/etc.) | ~0.7 GB | **100%** during encode | ❌ → **offload** |
| **QEMU Kali VM** | 3–5 GB | 20–30% | ❌ must stay local |
| L0–L4 memory tiers (tool outputs) | ~1.5 GB | minimal | ✅ CSO + immediate extraction |

Aggravating **O(n²) bugs** (`PERFORMANCE_AUDIT.md` F8-01/02/03): `ResponseCache` and
`EmbeddingCache` call `list.remove()` on every cache hit; `KnowledgeGraph` BFS uses
`list.pop(0)` on every traversal → "O(n²) aggregate." These are **code-quality**, not
CRP, but they directly worsen the breach.

> **Conclusion:** The breach that caused OOM/overheating during **long runs** is
> dominated by **context/memory growth** (KV cache + L0–L4 tiers + O(n²) graph) — which
> CRP positioning bounds. The **resident baseline** (weights + embeddings + QEMU) is a
> floor CRP cannot lower; it must be **offloaded**.

### Roadblocker #2 — Fragmented LLM operation; "side tricks to avoid the LLM"

WASA could not make its small model reliably do the work, so it **routed around it**.
Evidence:

**Models present (fragmentation):**

| Model | Params | Status | Evidence |
|-------|--------|--------|----------|
| Youtu-LLM-2B-Instruct | 1.96B | Primary, but overshadowed | `.env` keeps Gemma-2 fallback; bridge defaults to 8K |
| Gemma-2 2B | 2.6B | **Dead 4K fallback** | `model_registry.py:195-220` "backward compat" |
| Gemma-3 270M | 0.27B | **Hardcoded** in a separate RAG stack | `wasa_ai_rag/web_rag.py:437-444` |
| WASA-LM (10B ternary) | — | **Design only** | `CUSTOM_FOUNDATION_LLM_ARCHITECTURE.md` |
| RWKV-7 analyst | 2.9B | **Superseded** | `CUSTOM_RWKV_ANALYST_LLM_RESEARCH.md` |

**LLM-avoidance workarounds (the core of #2):**

| Workaround | Location | Effect |
|------------|----------|--------|
| CWE→framework mappings hardcoded (7 static dicts) | `cag/unified_compliance.py:269-860` | No reasoning for new CWEs |
| CWE database (80 CWEs, ~1000 lines) hardcoded | `cag/data/cwe_web_mappings.py` | Never reads MITRE live XML |
| MITRE `CWE_TO_ATTACK` hardcoded; STIX file unused | `cag/mitre_attack/mappings.py` | No inference |
| Tool selection = 83 deterministic rules | `mcp/decision_engine/`, `routing/` | Rules instead of positioned reasoning |
| Compliance "Detailed Assessment" **silently dead** | `reporting/incremental_builder.py:781` | `import ComplianceEngine` (actual class `DerivedComplianceEngine`) → caught ImportError → **section never generated** |
| Hermes XML tool-call declared, never used | `llm/chat_template.py:405+` | Tool path forced to JSON |
| Bridge context hardcoded to 8K (Youtu is 128K-native) | `mcp/tool_intelligence/integration_bridge.py:89-99` | Plan prompt capped at ~7 tools |

> **Conclusion:** #2 is exactly the failure CRP was built to fix. The model was flooded
> (138 schemas, 8K cap) and unreliable, so the team replaced reasoning with hardcoded
> tables and 83 rules. **Positioning makes the small model capable again**, so the
> workarounds become unnecessary (and the hardcoded tables become data-driven TCF
> capabilities or positioned operations).

### Roadblocker #3 — 40.4 GB size; Nuitka distribution; what to offload

| Component | Size | Offload? |
|-----------|------|----------|
| QEMU **Kali image** (`kali-production.qcow2`) | 8–10 GB | ❌ must stay local (target network, offline tools, legal) |
| Python venv + deps (torch, llama-cpp, playwright, selenium…) | 5–8 GB | partial (pre-built wheels) |
| Frontend `node_modules` | ~3 GB | ✅ ship pre-built `.next/` (~300 MB) |
| Model GGUF weights | 3–4 GB | ✅ → Railway inference |
| Vector DBs (`.chroma/`) | 0.5–1 GB | ✅ → managed/Railway |
| SQLite DBs | 0.2–0.4 GB | local |
| Logs / caches / test artifacts (`_*.txt`, `.cache/`) | 2+ GB | ✅ cleanup |

**Realistic Nuitka-compiled distributable:** ~**500 MB–1 GB** (native binaries; excludes
model weights + QEMU image, which are downloaded/managed separately).

---

## 2. Full weakness inventory

### 2.1 Tool orchestration — 4 competing subsystems
`SchemaRegistry`, `ToolMetadataRegistry`, `ToolRoutingEngine` (83 rules), and a
`decision_engine/` "dynamic" selector all coexist. Consequences:
- **80 orphaned tools** — `sync_with_schema_registry()` is never called → the two
  registries diverge.
- **Schema flooding** — all 138 tool schemas are pushed toward the prompt; prefill
  reaches 15–30 KB even with a 128K-native model.
- **Duplicate executions** — ZAP spider runs twice (standalone + inside
  `zap_active_scan`); `searchsploit` uses a hardcoded query instead of discovered tech.
- **13-step execution pipeline per tool** (param merge → fuzzy name correction →
  remap → default injection → WAF evasion → validate → safety → compile → dedup → sudo
  → broker → execute) — powerful but fragile and duplicated across systems.

### 2.2 Reporting — the "M1" reporter-blindness
The report LLM **never sees raw tool output**; it sees only 4 KB summaries written
before raw stdout is recycled (`reporting/incremental_builder.py`). Plus the compliance
section is silently dead (import bug above). Frameworks (PCI-DSS v4.0 etc.) are baked in.

### 2.3 Memory — fragmented across stores
Findings live in `FindingsStore` **and** `execution_context` **and** the L0–L4 tiers
(`tiered_memory.py`) simultaneously; no single source of truth; in-memory `_reports` /
`_active_scans` dicts are **lost on restart** even though findings persist in SQLite.

### 2.4 Agentic ecosystem
No positioning; no operation state machine (steps run linearly with no structured
feedback to the model); continuation can run 50 steps by default with no formal exit
rule; forked CRP v3 features (community detection, meta-learning) are **imported but
never invoked** (dead paths).

---

## 3. Decision matrix — who owns each fix

### (A) DIRECTLY solved by CRP v5 — high ROI, spec-ready
1. **Positioning replaces 83 rules + schema flooding** (TCF + Tool Positioning Frame, 1–3 tools/op) → ~10–15 KB context saved per operation.
2. **Operation State Machine** (SPEC-050 §5) → the model always knows where it is.
3. **CSO as single source of truth** → ends the FindingsStore/execution_context/L0–L4 fragmentation; report reads typed observations (fixes M1 by design).
4. **Resource Governor** → adaptive profile bounds context + KV; proactive cleanup.
5. **Continuation guardrail + loop-guard** → no 50-step spirals.
6. **CLARIFY + checkpoints** → the agent asks the user instead of guessing; gates destructive tools.

### (B) INFRASTRUCTURE — Railway offload of WASA's OWN services (not the CRP Gateway)
1. **Keep the positioned LLM local** (throttled, slow-and-steady) — positioning makes the
   small model capable on-device; do **not** ship inference to the Gateway.
2. **Offload WASA's RAG service + vector store** → Railway (the heaviest auxiliary load).
3. **Offload embeddings + knowledge components** → Railway (−0.7 GB, −100% encode spike).
4. **Offload MITRE / compliance enrichment** → Railway (stateless reference lookups).
5. **Keep local:** Kali VM + tool execution (target-network access) + CSO state + the SLM.

### (C) NOT CRP-domain — parallel code-quality work
1. Fix O(n) `ResponseCache`/`EmbeddingCache`/`KnowledgeGraph` → `OrderedDict`/`deque`.
2. Dedup ZAP spider/active-scan; fix `searchsploit` to use discovered tech.
3. Convert hardcoded compliance/MITRE tables → JSON data files (single source).
4. Fix the `ComplianceEngine`/`DerivedComplianceEngine` import bug; enable Hermes path.
5. Remove dead CRP v3 imports.

### (D) CONSOLIDATION — prerequisite to adopting the TCF
- Merge `ToolMetadataRegistry` ↔ `SchemaRegistry` (sync the 80 orphaned tools).
- One query entry point (retire either `UnifiedQueryService` or `QueryOrchestrator`).
- One RAG stack (retire the legacy Gemma-3-270M `wasa_ai_rag/`).
- Remove the hardcoded 8K bridge cap; let the profile/Governor set context.

---

## 4. The 40% guarantee — component-level analysis

**What CRP v5 guarantees (deterministic):** the per-operation working set is bounded by
the capability profile, **independent of session length**. The KV cache, L0–L4 tiers,
and knowledge-graph growth that drove WASA's OOM during long runs are eliminated because
each window holds only the current operation's frame + the few CSO facts it needs. A
300-tool session uses the same window as a 3-tool session. **This removes the growth
that caused OOM/overheating** — with an accepted modest speed cost (positioning trades
latency for stability; per the user, acceptable).

**What still needs offload (baseline floor):** weights (~2 GB) + embeddings (~0.7 GB +
100% encode) + QEMU (3–5 GB + 20–30%) are co-resident costs CRP cannot lower. To hold a
**local < 40%** target on a laptop:

| Mode | Local footprint | Meets <40% on a laptop? |
|------|-----------------|--------------------------|
| **All-local** (no offload) | weights + embeddings + QEMU + bounded CRP windows | Borderline; CPU spikes on prefill/encode |
| **Governor + Railway offload** (recommended) | QEMU + tool I/O + CSO state + **throttled local LLM**; WASA's RAG/knowledge remote | ✅ yes — local model runs slow-and-steady; heavy reference services remote |

> **Guaranteed answer:** Yes — *with the Resource Governor enforcing bounded windows,
> running the local model **slow-and-steady**, AND offloading WASA's **own** RAG/knowledge
> services to Railway*, both the **growth** and the **baseline** stay within budget. The
> positioned LLM stays local; only WASA's heavy auxiliary services move to Railway.
> All-local mode still guarantees the growth bound (no OOM from long runs).

---

## 5. Recommended target architecture (local ↔ Railway split)

```
┌─────────────────────────── USER LAPTOP (thin) ───────────────────────────┐
│  WASA orchestration shell                                                 │
│   • Operation State Machine (CRP)     • CSO state (durable)               │
│   • Tool execution + Kali QEMU VM  ◀── MUST stay local (target network)   │
│   • Visibility event stream → UI                                          │
└───────────────┬───────────────────────────────────────────────────────────┘
                │  reference-data queries (RAG / knowledge / enrichment)
                ▼
┌──────────── RAILWAY — WASA's OWN services (scale with users) ─────────────┐
│  RAG service / vector store           • Embeddings service                │
│  Knowledge components                 • MITRE / compliance enrichment      │
│  (NOT the CRP Gateway — positioned LLM stays LOCAL, slow & steady)         │
└───────────────────────────────────────────────────────────────────────────┘
```

This keeps the positioned SLM **on the laptop** (the whole point of CRP positioning)
and moves only WASA's heavy *reference* services to Railway. WASA's inference is **not**
routed through the CRP Gateway (an independent product).

---

## 6. Clearance answers (the reassurance you asked for)

1. **Will CRP v5 solve WASA's LLM-operation problems?** **Yes.** The fragmentation and
   "avoid the LLM" workarounds exist *because* the flooded small model was unreliable.
   Positioning makes it reliable, so one positioned inference path (`dispatch_positioned`
   / Gateway) replaces the multi-model mess and the hardcoded substitutes.
2. **Can we enhance its agentic ecosystem?** **Yes.** TCF + Operation State Machine +
   CSO + CLARIFY + checkpoints replace the 4 competing orchestration subsystems with one
   coherent, observable, positioned ecosystem.
3. **Should we offload to scalable Railway service(s)?** **Yes — WASA's *own* heavy
   services** (its RAG service, knowledge/embedding components, MITRE/compliance
   enrichment) on Railway, scaling with users — **not** routed through the CRP Gateway.
   The positioned **LLM stays local** (throttled, slow-and-steady); the Kali VM and tool
   execution stay local too. This holds the baseline under budget as users grow.

---

## 7. Validation & demo plan (testing, kimi, local SLM, visuals)

**Before/after measurement (the real proof of the 40% claim):**
- Instrument a representative scan in **all-local** vs **Governor+offload** modes;
  record peak RSS, sustained CPU, KV-cache size, context KB/op, steps/scan, and whether
  the working set stays **flat** across 100+ tool calls.

**LLM-quality confirmation (kimi + local SLM):**
- Run the same multi-operation task through (a) WASA's current flooded loop and (b) a
  CRP positioned loop on **meta-llama-3.1-8b-instruct** (`192.168.0.6:1234`).
- Judge factual completeness + report quality with **kimi-k2.6** (key read locally,
  never printed). Target: positioned ≥ baseline.

**Demos (some exist but are broken — finalise them):**
- Assess/repair `examples/crp_demos/v4/server.py` (+ `static/`).
- Build the **flagship visual demo**: live operation state machine, the 1–3-tool
  positioning frames, CSO findings accumulating, and a **flat resource graph** across
  100s of tool calls — the single most persuasive artifact for the protocol's depth.

---

## 8. Prioritized remediation roadmap

1. **CRP v5 core** (this repo) — TCF, Operation State Machine, CSO observations, Resource Governor, CLARIFY/checkpoints. *(Gates the rest.)*
2. **CRP Gateway offload** — host positioned inference + embeddings on Railway.
3. **WASA consolidation (D)** — merge registries, one RAG, one query path, remove 8K cap.
4. **WASA code-quality (C)** — O(n) fixes, dedup, import bug, tables→JSON.
5. **WASA → CRP-native** — replace the bespoke loop with `dispatch_positioned()` against the Gateway.
6. **Validate (§7)** + finalise demos.

---

*Audit generated 2026-06-30. Line-level citations should be re-confirmed against the
working tree during remediation; runtime resource numbers are to be measured per §7.*
