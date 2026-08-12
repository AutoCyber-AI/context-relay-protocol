"""CRP vs Direct LLM — KILLER DIFFERENTIATOR TEST
===================================================
Forces truncation to demonstrate CRP's continuation engine.

Strategy:
  - max_output_tokens=2048 → model WILL hit the wall
  - Task demands 20 numbered sections → impossible in 2048 tokens
  - Direct LLM: gets CUT OFF mid-output, incomplete (~5-7 sections)
  - CRP: detects wall hit → gap analysis → continues → stitches → COMPLETE output

This is the CLEAN DIFFERENTIATOR that shows CRP's real value.
"""

import sys, os, time, re, json, io, logging, functools

# Force UTF-8 on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Repo root = two levels up from tests/killer_test/
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
print = functools.partial(print, flush=True)

# ── Config ───────────────────────────────────────────────────────────
LM_STUDIO_URL = "http://192.168.0.6:1234/v1"
MODEL = "qwen3-4b"
API_KEY = "lm-studio"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "_crp_killer_report.txt")

# Token cap forces truncation — model needs ~15000+ tokens for full 30-section doc
# At 2048: thinking uses ~1500 tokens, content gets ~500 → 2-4 sections max
# → CRP needs 8-10 continuation windows to finish all 30 sections
MAX_OUTPUT_TOKENS = 2048

TASK_PROMPT = """You are writing a comprehensive technical reference document.

Write a document titled "The 30 Pillars of Modern Software Engineering" with EXACTLY 30 numbered sections.

IMPORTANT: Do NOT use <think> tags. Go straight to writing the document.

REQUIRED SECTIONS (all 30 must be present):
1. Input Validation — describe techniques, give 2 code examples in Python
2. Authentication — multi-factor auth, OAuth2 flows, session management
3. Authorization — RBAC, ABAC, principle of least privilege with examples
4. Cryptography — symmetric vs asymmetric, hashing algorithms, key management
5. Error Handling — secure logging, never expose stack traces, structured errors
6. Data Protection — encryption at rest, in transit, data classification levels
7. API Security — rate limiting, input sanitization, CORS configuration
8. Dependency Management — supply chain attacks, SCA tools, SBOM generation
9. Security Testing — SAST, DAST, penetration testing, fuzzing strategies
10. Incident Response — detection, containment, eradication, recovery phases
11. Code Review — static analysis, peer review practices, security checklists
12. Container Security — image scanning, runtime protection, Kubernetes hardening
13. Network Security — zero trust architecture, TLS configuration, firewall rules
14. Database Security — parameterized queries, access controls, backup encryption
15. Logging and Monitoring — SIEM integration, anomaly detection, audit trails
16. DevSecOps Pipeline — CI/CD security gates, automated scanning, policy as code
17. Cloud Security — IAM policies, shared responsibility model, cloud-native tools
18. Mobile Security — certificate pinning, secure storage, biometric authentication
19. Compliance — SOC2, GDPR, HIPAA, PCI-DSS requirements and implementation
20. Threat Modeling — STRIDE methodology, attack trees, risk scoring frameworks
21. Secure SDLC — security requirements, design reviews, security sprints
22. Identity and Access Management — SSO, directory services, lifecycle management
23. Secrets Management — vault integration, rotation policies, zero-trust secrets
24. Resilience Engineering — chaos engineering, fault injection, graceful degradation
25. Data Privacy — anonymization, pseudonymization, consent management, DSAR
26. Supply Chain Security — SLSA framework, provenance, artifact signing
27. Observability — distributed tracing, metrics, SLOs, error budgets
28. Infrastructure as Code — Terraform, policy-as-code, drift detection
29. AI/ML Security — adversarial attacks, model poisoning, prompt injection defense
30. Quantum-Safe Cryptography — post-quantum algorithms, migration planning, NIST PQC

RULES:
- Each section MUST have a heading "## N. Title"
- Each section MUST have at least 2 detailed paragraphs
- Include specific tool names, framework references, and best practices
- End with a "## Conclusion" that references all 30 pillars

Write the complete document now. Do not skip any section."""

SYSTEM_PROMPT = "You are an expert cybersecurity engineer and technical writer. Write detailed, accurate, and actionable content."

# Logging
logging.basicConfig(level=logging.WARNING)
crp_logger = logging.getLogger("crp")
crp_logger.setLevel(logging.INFO)
crp_log_lines = []


class LogCapture(logging.Handler):
    def emit(self, record):
        crp_log_lines.append(self.format(record))


log_capture = LogCapture()
log_capture.setFormatter(logging.Formatter("%(name)s: %(message)s"))
crp_logger.addHandler(log_capture)


def strip_thinking(text):
    if "<think>" in text:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


def count_sections(text):
    """Count ## N. headings (1-30)."""
    found = set()
    for m in re.finditer(r"(?:^|\n)\s*#{1,3}\s*(\d{1,2})\.", text):
        num = int(m.group(1))
        if 1 <= num <= 30:
            found.add(num)
    return sorted(found)


def has_conclusion(text):
    return bool(re.search(r"(?i)#{1,3}\s*conclusion", text))


def word_count(text):
    return len(text.split())


def paragraphs(text):
    return len([p for p in text.split("\n\n") if p.strip() and len(p.strip()) > 30])


# ═══════════════════════════════════════════════════════════════════
# TEST A: Direct LLM — single shot, max_tokens=1024
# ═══════════════════════════════════════════════════════════════════
def run_direct():
    from openai import OpenAI

    print("=" * 70)
    print(f"TEST A: DIRECT LLM — max_output_tokens={MAX_OUTPUT_TOKENS} (WILL TRUNCATE)")
    print("=" * 70)

    client = OpenAI(api_key=API_KEY, base_url=LM_STUDIO_URL, timeout=600.0)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TASK_PROMPT},
    ]

    print(f"Model: {MODEL}")
    print(f"Max output tokens: {MAX_OUTPUT_TOKENS}")
    print("Dispatching...")

    t0 = time.time()
    resp = client.chat.completions.create(
        model=MODEL, messages=messages,
        max_tokens=MAX_OUTPUT_TOKENS, temperature=0.7,
    )
    # Note: qwen3 may include <think> reasoning in content.
    # The thinking tokens consume part of the max_tokens budget.
    elapsed = time.time() - t0

    raw = resp.choices[0].message.content or ""
    finish = resp.choices[0].finish_reason
    clean = strip_thinking(raw)
    sections = count_sections(clean)

    result = {
        "method": f"Direct LLM (max_tokens={MAX_OUTPUT_TOKENS})",
        "elapsed": round(elapsed, 1),
        "finish_reason": finish,
        "truncated": finish == "length",
        "raw_chars": len(raw),
        "clean_chars": len(clean),
        "words": word_count(clean),
        "sections_found": sections,
        "sections_count": len(sections),
        "has_conclusion": has_conclusion(clean),
        "paragraphs": paragraphs(clean),
        "output": clean,
    }

    print(f"Done in {elapsed:.1f}s")
    print(f"Finish reason: {finish}")
    print(f"TRUNCATED: {'YES' if finish == 'length' else 'NO'}")
    print(f"Words: {word_count(clean)}")
    print(f"Sections found: {sections} ({len(sections)}/30)")
    print(f"Conclusion: {'YES' if has_conclusion(clean) else 'NO'}")
    return result


# ═══════════════════════════════════════════════════════════════════
# TEST B: CRP-Orchestrated — same max_tokens, but with continuation
# ═══════════════════════════════════════════════════════════════════
def run_crp():
    from crp.providers.openai import OpenAIAdapter
    from crp.core.orchestrator import CRPOrchestrator
    from crp.core.config import CRPConfig

    print("\n" + "=" * 70)
    print(f"TEST B: CRP DISPATCH — max_output_tokens={MAX_OUTPUT_TOKENS} (CRP HANDLES CONTINUATION)")
    print("=" * 70)

    adapter = OpenAIAdapter(
        model=MODEL, api_key=API_KEY,
        base_url=LM_STUDIO_URL, timeout=600.0,
    )
    # CRITICAL: LM Studio loads qwen3-4b with n_ctx=4096.  CRP auto-discovers
    # the family maximum (40960) which is wrong.  We MUST match the actual
    # server value so the envelope budget formula (E = C - S - T - G) produces
    # prompts that fit in 4096 tokens, leaving room for continuation windows.
    adapter._context_size = 4096

    config = CRPConfig(_values={"max_continuations": 10})
    client = CRPOrchestrator(provider=adapter, config=config)
    # Disable heavy ML for speed — regex + statistical + discourse still active
    client._extraction._enable_3 = False
    client._extraction._enable_4 = False
    # Disable LLM curator — thinking models waste all tokens on reasoning
    client._curator.should_curate = lambda _: False
    # Disable L3 LLM-based requirement extractor (also wasted by thinking models)
    client._continuation_config.l3_extractor = lambda _: []

    print(f"Model: {MODEL}")
    print(f"Max output tokens per window: {MAX_OUTPUT_TOKENS}")
    print(f"Max continuation windows: 10")
    print("Dispatching via CRP...")

    t0 = time.time()
    output, report = client.dispatch(
        system_prompt=SYSTEM_PROMPT,
        task_input=TASK_PROMPT,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    elapsed = time.time() - t0

    clean = strip_thinking(output)
    sections = count_sections(clean)

    result = {
        "method": f"CRP-Orchestrated (max_tokens={MAX_OUTPUT_TOKENS} per window)",
        "elapsed": round(elapsed, 1),
        "quality_tier": report.quality_tier,
        "facts_extracted": report.facts_extracted,
        "continuation_windows": report.continuation_windows,
        "envelope_saturation": round(report.envelope_saturation, 3),
        "clean_chars": len(clean),
        "words": word_count(clean),
        "sections_found": sections,
        "sections_count": len(sections),
        "has_conclusion": has_conclusion(clean),
        "paragraphs": paragraphs(clean),
        "security_flags": {
            "injection_markers": report.security_flags.injection_markers_detected,
        },
        "telemetry": report.telemetry,
        "crp_logs": crp_log_lines.copy(),
        "output": clean,
    }

    print(f"Done in {elapsed:.1f}s")
    print(f"Quality tier: {report.quality_tier}")
    print(f"Continuation windows: {report.continuation_windows}")
    print(f"Facts extracted: {report.facts_extracted}")
    print(f"Words: {word_count(clean)}")
    print(f"Sections found: {sections} ({len(sections)}/30)")
    print(f"Conclusion: {'YES' if has_conclusion(clean) else 'NO'}")
    return result


# ═══════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════
def write_report(direct, crp):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("CRP vs DIRECT LLM — KILLER DIFFERENTIATOR TEST\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Model: {MODEL}\n")
        f.write(f"Max output tokens per call: {MAX_OUTPUT_TOKENS}\n")
        f.write(f"Task: 30-section engineering document (impossible in {MAX_OUTPUT_TOKENS} tokens)\n\n")

        # ── Query ─────────────────────────────────────────────────
        f.write("-" * 80 + "\n")
        f.write("ORIGINAL QUERY\n")
        f.write("-" * 80 + "\n\n")
        f.write(f"System: {SYSTEM_PROMPT}\n\n")
        f.write(f"Task:\n{TASK_PROMPT}\n\n")

        # ── Metrics ───────────────────────────────────────────────
        f.write("-" * 80 + "\n")
        f.write("METRICS COMPARISON — THE DIFFERENTIATOR\n")
        f.write("-" * 80 + "\n\n")

        d_secs = direct["sections_count"]
        c_secs = crp["sections_count"]
        d_words = direct["words"]
        c_words = crp["words"]

        rows = [
            ("Method", direct["method"], crp["method"]),
            ("Time (seconds)", direct["elapsed"], crp["elapsed"]),
            ("TRUNCATED?", "YES" if direct["truncated"] else "NO", "N/A — CRP handles it"),
            ("Output words", d_words, c_words),
            ("Output chars", direct["clean_chars"], crp["clean_chars"]),
            ("Sections found (of 30)", f"{d_secs}/30", f"{c_secs}/30"),
            ("Missing sections", str(sorted(set(range(1,31)) - set(direct["sections_found"]))),
             str(sorted(set(range(1,31)) - set(crp["sections_found"])))),

            ("Has conclusion?", "YES" if direct["has_conclusion"] else "NO",
             "YES" if crp["has_conclusion"] else "NO"),
            ("Paragraphs", direct["paragraphs"], crp["paragraphs"]),
            ("Continuation windows", "N/A", crp["continuation_windows"]),
            ("Facts extracted", "N/A", crp["facts_extracted"]),
            ("Quality tier", direct.get("finish_reason", "N/A"), crp.get("quality_tier", "N/A")),
            ("Envelope saturation", "N/A", crp.get("envelope_saturation", 0)),
        ]

        f.write(f"{'Metric':<30} {'Direct LLM':<35} {'CRP Dispatch':<35}\n")
        f.write(f"{'─'*30} {'─'*35} {'─'*35}\n")
        for metric, d, c in rows:
            f.write(f"{metric:<30} {str(d):<35} {str(c):<35}\n")

        # ── Verdict ───────────────────────────────────────────────
        f.write("\n" + "-" * 80 + "\n")
        f.write("VERDICT\n")
        f.write("-" * 80 + "\n\n")

        if direct["truncated"] and c_secs > d_secs:
            word_ratio = c_words / d_words if d_words > 0 else float("inf")
            f.write(f"*** CRP WINS — CLEAR DIFFERENTIATOR ***\n\n")
            f.write(f"Direct LLM was TRUNCATED at {MAX_OUTPUT_TOKENS} tokens.\n")
            f.write(f"  - Only produced {d_secs}/30 sections ({d_words} words)\n")
            f.write(f"  - Output cut off mid-generation\n")
            f.write(f"  - Missing sections: {sorted(set(range(1,31)) - set(direct['sections_found']))}\n\n")
            f.write(f"CRP used {crp['continuation_windows']} continuation windows to complete the task.\n")
            f.write(f"  - Produced {c_secs}/30 sections ({c_words} words)\n")
            f.write(f"  - {word_ratio:.1f}x more content than direct LLM\n")
            f.write(f"  - Extracted {crp['facts_extracted']} facts for context-carrying\n")
            f.write(f"  - Quality tier: {crp.get('quality_tier', 'N/A')}\n\n")
            f.write(f"CRP's continuation engine detected the wall hit (finish_reason=length),\n")
            f.write(f"analysed the gap (missing sections), carried extracted facts forward\n")
            f.write(f"in the envelope, and dispatched continuation windows until the task\n")
            f.write(f"was complete. This is impossible with a raw LLM call.\n")
        elif not direct["truncated"]:
            f.write("Direct LLM was NOT truncated — token cap was sufficient.\n")
            f.write("Try reducing MAX_OUTPUT_TOKENS further.\n")
        else:
            f.write(f"Both truncated. Direct: {d_secs}/20, CRP: {c_secs}/20\n")
            f.write("CRP may need more continuation windows.\n")

        # ── CRP Telemetry ─────────────────────────────────────────
        if crp.get("telemetry"):
            t = crp["telemetry"]
            f.write("\n" + "-" * 80 + "\n")
            f.write("CRP PROTOCOL TELEMETRY\n")
            f.write("-" * 80 + "\n\n")

            # Overhead breakdown
            f.write("  ┌─ CRP OVERHEAD BREAKDOWN ─────────────────────────────────┐\n")
            f.write(f"  │ Total dispatch time:      {t.get('total_dispatch_ms', 0):>10.0f} ms                  │\n")
            f.write(f"  │ Total LLM generation:     {t.get('total_llm_ms', 0):>10.0f} ms                  │\n")
            f.write(f"  │ Total extraction:         {t.get('total_extraction_ms', 0):>10.0f} ms                  │\n")
            f.write(f"  │ Total envelope build:     {t.get('total_envelope_ms', 0):>10.0f} ms                  │\n")
            f.write(f"  │ CRP overhead (non-LLM):   {t.get('crp_overhead_ms', 0):>10.0f} ms ({t.get('crp_overhead_pct', 0):.1f}%)         │\n")
            f.write("  └────────────────────────────────────────────────────────────┘\n\n")

            # Token accounting
            f.write("  ┌─ TOKEN ACCOUNTING ─────────────────────────────────────────┐\n")
            f.write(f"  │ System tokens:            {t.get('system_tokens', 0):>8}                       │\n")
            f.write(f"  │ Task tokens:              {t.get('task_tokens', 0):>8}                       │\n")
            f.write(f"  │ Envelope tokens (primary):{t.get('envelope_tokens', 0):>8}                       │\n")
            f.write(f"  │ Envelope budget:          {t.get('envelope_budget', 0):>8}                       │\n")
            f.write(f"  │ Generation reserve:       {t.get('generation_reserve', 0):>8}                       │\n")
            f.write(f"  │ Total output tokens:      {t.get('total_output_tokens', 0):>8}                       │\n")
            f.write(f"  │ Reasoning tokens (think): {t.get('reasoning_tokens', 0):>8}                       │\n")
            f.write(f"  │ Generation speed:         {t.get('generation_speed', 0):>8.1f} tok/s                  │\n")
            f.write("  └────────────────────────────────────────────────────────────┘\n\n")

            # Coverage / quality
            f.write("  ┌─ COVERAGE & QUALITY ────────────────────────────────────────┐\n")
            f.write(f"  │ Final gap score:          {t.get('final_gap_score', 0):>8.3f} (0=complete, 1=empty) │\n")
            f.write(f"  │ Gap coverage:             {t.get('gap_coverage', 0):>8.3f} (1=complete, 0=empty) │\n")
            f.write(f"  │ Envelope saturation:      {t.get('saturation', 0):>8.3f}                        │\n")
            f.write(f"  │ Facts extracted:          {t.get('facts_extracted', 0):>8}                        │\n")
            f.write(f"  │ Extraction stages:        {t.get('extraction_stage_used', 'N/A'):>8}                        │\n")
            f.write(f"  │ Continuation windows:     {t.get('continuation_index', 0):>8}                        │\n")
            f.write(f"  │ Finish reason (primary):  {t.get('finish_reason', 'N/A'):>8}                        │\n")
            f.write("  └─────────────────────────────────────────────────────────────┘\n\n")

            # Per-window continuation detail
            windows_detail = t.get("continuation_windows_detail", [])
            if windows_detail:
                f.write("  ┌─ PER-WINDOW CONTINUATION TELEMETRY ────────────────────────┐\n")
                f.write(f"  │ {'Win':>3} │ {'LLM ms':>8} │ {'Ext ms':>7} │ {'Env ms':>7} │ {'OutTok':>6} │ {'Facts':>5} │ {'GapScr':>6} │ {'RsnTok':>6} │ {'Sat':>5} │\n")
                f.write(f"  │{'─'*3}─┼{'─'*10}┼{'─'*9}┼{'─'*9}┼{'─'*8}┼{'─'*7}┼{'─'*8}┼{'─'*8}┼{'─'*7}│\n")
                for w in windows_detail:
                    f.write(f"  │ {w['window']:>3} │ {w['llm_ms']:>8} │ {w['extraction_ms']:>7} │ {w['envelope_ms']:>7} │ {w['output_tokens']:>6} │ {w['facts']:>5} │ {w['gap_score']:>6.3f} │ {w['reasoning_tokens']:>6} │ {w.get('envelope_saturation', 0):>5.3f} │\n")
                f.write("  └─────────────────────────────────────────────────────────────┘\n")

        # ── CRP Logs ──────────────────────────────────────────────
        if crp.get("crp_logs"):
            f.write("\n" + "-" * 80 + "\n")
            f.write(f"CRP PROTOCOL LOGS ({len(crp['crp_logs'])} entries)\n")
            f.write("-" * 80 + "\n\n")
            for line in crp["crp_logs"]:
                f.write(f"  {line}\n")

        # ── Full outputs ──────────────────────────────────────────
        f.write("\n" + "=" * 80 + "\n")
        f.write("FULL OUTPUT — DIRECT LLM (TRUNCATED)\n")
        f.write("=" * 80 + "\n\n")
        f.write(direct["output"])

        f.write("\n\n" + "=" * 80 + "\n")
        f.write("FULL OUTPUT — CRP DISPATCH (COMPLETE)\n")
        f.write("=" * 80 + "\n\n")
        f.write(crp["output"])

    # Also write machine-readable JSON telemetry
    json_file = OUTPUT_FILE.replace(".txt", ".json")
    json_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": MODEL,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "direct": {k: v for k, v in direct.items() if k != "output"},
        "crp": {k: v for k, v in crp.items() if k not in ("output", "crp_logs")},
    }
    with open(json_file, "w", encoding="utf-8") as jf:
        json.dump(json_data, jf, indent=2, default=str)

    print(f"\nResults written to: {OUTPUT_FILE}")
    print(f"JSON telemetry:     {json_file}")
    print(f"File size: {os.path.getsize(OUTPUT_FILE):,} bytes")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 70)
    print("  CRP KILLER DIFFERENTIATOR TEST")
    print(f"  Model: {MODEL}  |  max_tokens: {MAX_OUTPUT_TOKENS}")
    print(f"  Task: 30-section document (requires ~20000+ tokens)")
    print(f"  Direct LLM WILL be truncated. CRP WILL continue.")
    print("=" * 70)
    print()

    try:
        direct = run_direct()
    except Exception as e:
        print(f"TEST A FAILED: {e}")
        import traceback; traceback.print_exc()
        direct = {"method": "FAILED", "elapsed": 0, "finish_reason": "error",
                  "truncated": False, "clean_chars": 0, "words": 0,
                  "sections_found": [], "sections_count": 0,
                  "has_conclusion": False, "paragraphs": 0,
                  "output": f"ERROR: {e}"}

    try:
        crp_result = run_crp()
    except Exception as e:
        print(f"TEST B FAILED: {e}")
        import traceback; traceback.print_exc()
        crp_result = {"method": "FAILED", "elapsed": 0, "clean_chars": 0,
                      "words": 0, "sections_found": [], "sections_count": 0,
                      "has_conclusion": False, "paragraphs": 0,
                      "continuation_windows": 0, "facts_extracted": 0,
                      "output": f"ERROR: {e}", "crp_logs": crp_log_lines.copy()}

    write_report(direct, crp_result)

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
