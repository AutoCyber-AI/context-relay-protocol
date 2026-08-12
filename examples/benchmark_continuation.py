"""CRP Continuation Benchmark
===============================
Demonstrates CRP's continuation engine by forcing an LLM to hit its
output-token wall and measuring how CRP overcomes it.

Usage:
    python examples/benchmark_continuation.py
    python examples/benchmark_continuation.py --base-url http://localhost:1234/v1 --model qwen3-4b
    python examples/benchmark_continuation.py --max-tokens 1024 --sections 20

See BENCHMARKS.md for full documentation and expected results.
"""

import argparse
import functools
import io
import json
import logging
import os
import re
import sys
import time

# Force UTF-8 on Windows
if sys.platform == "win32" and getattr(sys.stdout, "encoding", "") != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

print = functools.partial(print, flush=True)

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING)
crp_logger = logging.getLogger("crp")
crp_logger.setLevel(logging.INFO)
crp_log_lines: list[str] = []


class _LogCapture(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        crp_log_lines.append(self.format(record))


_handler = _LogCapture()
_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
crp_logger.addHandler(_handler)


# ── Helpers ──────────────────────────────────────────────────────────
def _strip_thinking(text: str) -> str:
    """Remove <think>…</think> blocks from thinking-model output."""
    if "<think>" in text:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


def _count_sections(text: str, max_section: int = 30) -> list[int]:
    """Find unique ## N. headings."""
    found: set[int] = set()
    for m in re.finditer(r"(?:^|\n)\s*#{1,3}\s*(\d{1,2})\.", text):
        num = int(m.group(1))
        if 1 <= num <= max_section:
            found.add(num)
    return sorted(found)


def _has_conclusion(text: str) -> bool:
    return bool(re.search(r"(?i)#{1,3}\s*conclusion", text))


def _word_count(text: str) -> int:
    return len(text.split())


def _paragraphs(text: str) -> int:
    return len([p for p in text.split("\n\n") if p.strip() and len(p.strip()) > 30])


def _build_task(sections: int) -> tuple[str, str]:
    """Generate system prompt and task prompt for N sections."""
    system = (
        "You are an expert cybersecurity engineer and technical writer. "
        "Write detailed, accurate, and actionable content."
    )

    section_list = [
        "Input Validation — describe techniques, give 2 code examples in Python",
        "Authentication — multi-factor auth, OAuth2 flows, session management",
        "Authorization — RBAC, ABAC, principle of least privilege with examples",
        "Cryptography — symmetric vs asymmetric, hashing algorithms, key management",
        "Error Handling — secure logging, never expose stack traces, structured errors",
        "Data Protection — encryption at rest, in transit, data classification levels",
        "API Security — rate limiting, input sanitization, CORS configuration",
        "Dependency Management — supply chain attacks, SCA tools, SBOM generation",
        "Security Testing — SAST, DAST, penetration testing, fuzzing strategies",
        "Incident Response — detection, containment, eradication, recovery phases",
        "Code Review — static analysis, peer review practices, security checklists",
        "Container Security — image scanning, runtime protection, Kubernetes hardening",
        "Network Security — zero trust architecture, TLS configuration, firewall rules",
        "Database Security — parameterized queries, access controls, backup encryption",
        "Logging and Monitoring — SIEM integration, anomaly detection, audit trails",
        "DevSecOps Pipeline — CI/CD security gates, automated scanning, policy as code",
        "Cloud Security — IAM policies, shared responsibility model, cloud-native tools",
        "Mobile Security — certificate pinning, secure storage, biometric authentication",
        "Compliance — SOC2, GDPR, HIPAA, PCI-DSS requirements and implementation",
        "Threat Modeling — STRIDE methodology, attack trees, risk scoring frameworks",
        "Secure SDLC — security requirements, design reviews, security sprints",
        "Identity and Access Management — SSO, directory services, lifecycle management",
        "Secrets Management — vault integration, rotation policies, zero-trust secrets",
        "Resilience Engineering — chaos engineering, fault injection, graceful degradation",
        "Data Privacy — anonymization, pseudonymization, consent management, DSAR",
        "Supply Chain Security — SLSA framework, provenance, artifact signing",
        "Observability — distributed tracing, metrics, SLOs, error budgets",
        "Infrastructure as Code — Terraform, policy-as-code, drift detection",
        "AI/ML Security — adversarial attacks, model poisoning, prompt injection defense",
        "Quantum-Safe Cryptography — post-quantum algorithms, migration planning, NIST PQC",
    ]

    used = section_list[:sections]
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(used))

    task = f"""You are writing a comprehensive technical reference document.

Write a document titled "The {sections} Pillars of Modern Software Engineering" with EXACTLY {sections} numbered sections.

IMPORTANT: Do NOT use <think> tags. Go straight to writing the document.

REQUIRED SECTIONS (all {sections} must be present):
{numbered}

RULES:
- Each section MUST have a heading "## N. Title"
- Each section MUST have at least 2 detailed paragraphs
- Include specific tool names, framework references, and best practices
- End with a "## Conclusion" that references all {sections} pillars

Write the complete document now. Do not skip any section."""
    return system, task


# ── Test A: Direct LLM ──────────────────────────────────────────────
def run_direct(args: argparse.Namespace, system: str, task: str) -> dict:
    from openai import OpenAI

    print("=" * 70)
    print(f"TEST A: DIRECT LLM — max_output_tokens={args.max_tokens} (WILL TRUNCATE)")
    print("=" * 70)

    client = OpenAI(api_key=args.api_key, base_url=args.base_url, timeout=600.0)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task},
    ]

    print(f"Model: {args.model}")
    print(f"Max output tokens: {args.max_tokens}")
    print("Dispatching...")

    t0 = time.time()
    resp = client.chat.completions.create(
        model=args.model,
        messages=messages,
        max_tokens=args.max_tokens,
        temperature=0.7,
    )
    elapsed = time.time() - t0

    raw = resp.choices[0].message.content or ""
    finish = resp.choices[0].finish_reason
    clean = _strip_thinking(raw)
    sections = _count_sections(clean, args.sections)

    result = {
        "method": f"Direct LLM (max_tokens={args.max_tokens})",
        "elapsed": round(elapsed, 1),
        "finish_reason": finish,
        "truncated": finish == "length",
        "raw_chars": len(raw),
        "clean_chars": len(clean),
        "words": _word_count(clean),
        "sections_found": sections,
        "sections_count": len(sections),
        "has_conclusion": _has_conclusion(clean),
        "paragraphs": _paragraphs(clean),
        "output": clean,
    }

    print(f"Done in {elapsed:.1f}s")
    print(f"Finish reason: {finish}")
    print(f"TRUNCATED: {'YES' if finish == 'length' else 'NO'}")
    print(f"Words: {_word_count(clean)}")
    print(f"Sections found: {sections} ({len(sections)}/{args.sections})")
    print(f"Conclusion: {'YES' if _has_conclusion(clean) else 'NO'}")
    return result


# ── Test B: CRP Dispatch ────────────────────────────────────────────
def run_crp(args: argparse.Namespace, system: str, task: str) -> dict:
    from crp.core.config import CRPConfig
    from crp.core.orchestrator import CRPOrchestrator
    from crp.providers.openai import OpenAIAdapter

    print("\n" + "=" * 70)
    print(f"TEST B: CRP DISPATCH — max_output_tokens={args.max_tokens} (CRP HANDLES CONTINUATION)")
    print("=" * 70)

    adapter = OpenAIAdapter(
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        timeout=600.0,
    )

    # If the user specifies --context-size, override auto-discovery.
    # This is critical when the server's actual n_ctx differs from the
    # model family maximum that CRP auto-discovers.
    if args.context_size:
        adapter._context_size = args.context_size

    config = CRPConfig(_values={"max_continuations": args.max_continuations})
    client = CRPOrchestrator(provider=adapter, config=config)

    # Disable heavy ML extraction stages for speed.
    # Regex + statistical + discourse analysis remain active.
    client._extraction._enable_3 = False
    client._extraction._enable_4 = False

    # Disable LLM curator — thinking models waste tokens on reasoning.
    client._curator.should_curate = lambda _: False

    # Disable L3 LLM-based requirement extractor.
    client._continuation_config.l3_extractor = lambda _: []

    print(f"Model: {args.model}")
    print(f"Max output tokens per window: {args.max_tokens}")
    print(f"Max continuation windows: {args.max_continuations}")
    if args.context_size:
        print(f"Context size override: {args.context_size}")
    print("Dispatching via CRP...")

    t0 = time.time()
    output, report = client.dispatch(
        system_prompt=system,
        task_input=task,
        max_output_tokens=args.max_tokens,
    )
    elapsed = time.time() - t0

    clean = _strip_thinking(output)
    sections = _count_sections(clean, args.sections)

    result = {
        "method": f"CRP-Orchestrated (max_tokens={args.max_tokens} per window)",
        "elapsed": round(elapsed, 1),
        "quality_tier": report.quality_tier,
        "facts_extracted": report.facts_extracted,
        "continuation_windows": report.continuation_windows,
        "envelope_saturation": round(report.envelope_saturation, 3),
        "clean_chars": len(clean),
        "words": _word_count(clean),
        "sections_found": sections,
        "sections_count": len(sections),
        "has_conclusion": _has_conclusion(clean),
        "paragraphs": _paragraphs(clean),
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
    print(f"Words: {_word_count(clean)}")
    print(f"Sections found: {sections} ({len(sections)}/{args.sections})")
    print(f"Conclusion: {'YES' if _has_conclusion(clean) else 'NO'}")
    return result


# ── Report ───────────────────────────────────────────────────────────
def write_report(direct: dict, crp: dict, args: argparse.Namespace) -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    txt_path = os.path.join(out_dir, "_crp_benchmark_report.txt")
    json_path = os.path.join(out_dir, "_crp_benchmark_report.json")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("CRP vs DIRECT LLM — CONTINUATION BENCHMARK\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Model: {args.model}\n")
        f.write(f"Max output tokens per call: {args.max_tokens}\n")
        f.write(f"Sections requested: {args.sections}\n")
        if args.context_size:
            f.write(f"Context size override: {args.context_size}\n")
        f.write(f"Max continuations: {args.max_continuations}\n\n")

        # Metrics table
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
            (f"Sections (of {args.sections})", f"{d_secs}/{args.sections}", f"{c_secs}/{args.sections}"),
            ("Missing sections",
             str(sorted(set(range(1, args.sections + 1)) - set(direct["sections_found"]))),
             str(sorted(set(range(1, args.sections + 1)) - set(crp["sections_found"])))),
            ("Has conclusion?",
             "YES" if direct["has_conclusion"] else "NO",
             "YES" if crp["has_conclusion"] else "NO"),
            ("Paragraphs", direct["paragraphs"], crp["paragraphs"]),
            ("Continuation windows", "N/A", crp["continuation_windows"]),
            ("Facts extracted", "N/A", crp["facts_extracted"]),
            ("Quality tier", direct.get("finish_reason", "N/A"), crp.get("quality_tier", "N/A")),
            ("Envelope saturation", "N/A", crp.get("envelope_saturation", 0)),
        ]

        f.write("-" * 80 + "\n")
        f.write("METRICS COMPARISON\n")
        f.write("-" * 80 + "\n\n")
        f.write(f"{'Metric':<30} {'Direct LLM':<35} {'CRP Dispatch':<35}\n")
        f.write(f"{'─' * 30} {'─' * 35} {'─' * 35}\n")
        for metric, d, c in rows:
            f.write(f"{metric:<30} {str(d):<35} {str(c):<35}\n")

        # Verdict
        f.write("\n" + "-" * 80 + "\n")
        f.write("VERDICT\n")
        f.write("-" * 80 + "\n\n")

        if direct["truncated"] and c_secs > d_secs:
            ratio = c_words / d_words if d_words > 0 else float("inf")
            f.write("*** CRP WINS — CLEAR DIFFERENTIATOR ***\n\n")
            f.write(f"Direct LLM was TRUNCATED at {args.max_tokens} tokens.\n")
            f.write(f"  - Only produced {d_secs}/{args.sections} sections ({d_words} words)\n")
            f.write(f"  - Output cut off mid-generation\n\n")
            f.write(f"CRP used {crp['continuation_windows']} continuation windows to complete the task.\n")
            f.write(f"  - Produced {c_secs}/{args.sections} sections ({c_words} words)\n")
            f.write(f"  - {ratio:.1f}x more content than direct LLM\n")
            f.write(f"  - Extracted {crp['facts_extracted']} facts for context-carrying\n")
            f.write(f"  - Quality tier: {crp.get('quality_tier', 'N/A')}\n")
        elif not direct["truncated"]:
            f.write("Direct LLM was NOT truncated — token cap was sufficient for this task.\n")
            f.write("Try reducing --max-tokens or increasing --sections to force truncation.\n")
        else:
            f.write(f"Both truncated. Direct: {d_secs}/{args.sections}, CRP: {c_secs}/{args.sections}\n")

        # Telemetry
        if crp.get("telemetry"):
            t = crp["telemetry"]
            f.write("\n" + "-" * 80 + "\n")
            f.write("CRP PROTOCOL TELEMETRY\n")
            f.write("-" * 80 + "\n\n")

            f.write("  OVERHEAD BREAKDOWN\n")
            f.write(f"    Total dispatch:     {t.get('total_dispatch_ms', 0):>10.0f} ms\n")
            f.write(f"    LLM generation:     {t.get('total_llm_ms', 0):>10.0f} ms\n")
            f.write(f"    Extraction:         {t.get('total_extraction_ms', 0):>10.0f} ms\n")
            f.write(f"    Envelope build:     {t.get('total_envelope_ms', 0):>10.0f} ms\n")
            f.write(f"    CRP overhead:       {t.get('crp_overhead_ms', 0):>10.0f} ms ({t.get('crp_overhead_pct', 0):.1f}%)\n\n")

            f.write("  TOKEN ACCOUNTING\n")
            f.write(f"    System tokens:      {t.get('system_tokens', 0):>8}\n")
            f.write(f"    Task tokens:        {t.get('task_tokens', 0):>8}\n")
            f.write(f"    Envelope budget:    {t.get('envelope_budget', 0):>8}\n")
            f.write(f"    Generation reserve: {t.get('generation_reserve', 0):>8}\n")
            f.write(f"    Total output:       {t.get('total_output_tokens', 0):>8}\n")
            f.write(f"    Reasoning tokens:   {t.get('reasoning_tokens', 0):>8}\n")
            f.write(f"    Speed:              {t.get('generation_speed', 0):>8.1f} tok/s\n\n")

            windows = t.get("continuation_windows_detail", [])
            if windows:
                f.write("  PER-WINDOW TELEMETRY\n")
                f.write(f"    {'Win':>3}  {'LLM(s)':>7}  {'Ext(ms)':>7}  {'Env(s)':>7}  {'OutTok':>6}  {'RsnTok':>6}  {'Facts':>5}  {'Sat':>5}\n")
                for w in windows:
                    f.write(
                        f"    {w['window']:>3}  "
                        f"{w['llm_ms']/1000:>7.1f}  "
                        f"{w['extraction_ms']:>7}  "
                        f"{w['envelope_ms']/1000:>7.1f}  "
                        f"{w['output_tokens']:>6}  "
                        f"{w.get('reasoning_tokens', 0):>6}  "
                        f"{w['facts']:>5}  "
                        f"{w.get('envelope_saturation', 0):>5.3f}\n"
                    )

        # CRP logs
        if crp.get("crp_logs"):
            f.write("\n" + "-" * 80 + "\n")
            f.write(f"CRP PROTOCOL LOGS ({len(crp['crp_logs'])} entries)\n")
            f.write("-" * 80 + "\n\n")
            for line in crp["crp_logs"]:
                f.write(f"  {line}\n")

        # Full outputs
        f.write("\n" + "=" * 80 + "\n")
        f.write("FULL OUTPUT — DIRECT LLM\n")
        f.write("=" * 80 + "\n\n")
        f.write(direct["output"])

        f.write("\n\n" + "=" * 80 + "\n")
        f.write("FULL OUTPUT — CRP DISPATCH\n")
        f.write("=" * 80 + "\n\n")
        f.write(crp["output"])

    # JSON telemetry
    json_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": args.model,
        "max_output_tokens": args.max_tokens,
        "sections_requested": args.sections,
        "context_size_override": args.context_size,
        "max_continuations": args.max_continuations,
        "direct": {k: v for k, v in direct.items() if k != "output"},
        "crp": {k: v for k, v in crp.items() if k not in ("output", "crp_logs")},
    }
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(json_data, jf, indent=2, default=str)

    print(f"\nResults written to: {txt_path}")
    print(f"JSON telemetry:     {json_path}")
    print(f"Report size: {os.path.getsize(txt_path):,} bytes")


# ── CLI ──────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="CRP Continuation Benchmark — compare Direct LLM vs CRP dispatch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="See BENCHMARKS.md for documentation and expected results.",
    )
    parser.add_argument("--base-url", default="http://localhost:1234/v1",
                        help="OpenAI-compatible API base URL (default: http://localhost:1234/v1)")
    parser.add_argument("--model", default="qwen3-4b",
                        help="Model name (default: qwen3-4b)")
    parser.add_argument("--api-key", default="lm-studio",
                        help="API key (default: lm-studio)")
    parser.add_argument("--max-tokens", type=int, default=2048,
                        help="Max output tokens per call (default: 2048)")
    parser.add_argument("--max-continuations", type=int, default=10,
                        help="Max CRP continuation windows (default: 10)")
    parser.add_argument("--context-size", type=int, default=None,
                        help="Override model context size (use when server n_ctx differs from model max)")
    parser.add_argument("--sections", type=int, default=30,
                        help="Number of document sections to request (default: 30)")
    args = parser.parse_args()

    system, task = _build_task(args.sections)

    print("=" * 70)
    print("  CRP CONTINUATION BENCHMARK")
    print(f"  Model: {args.model}  |  max_tokens: {args.max_tokens}")
    print(f"  Task: {args.sections}-section document (requires ~{args.sections * 600}+ tokens)")
    print(f"  Direct LLM WILL be truncated. CRP WILL continue.")
    print("=" * 70)
    print()

    try:
        direct = run_direct(args, system, task)
    except Exception as e:
        print(f"TEST A FAILED: {e}")
        import traceback
        traceback.print_exc()
        direct = {
            "method": "FAILED", "elapsed": 0, "finish_reason": "error",
            "truncated": False, "clean_chars": 0, "words": 0,
            "sections_found": [], "sections_count": 0,
            "has_conclusion": False, "paragraphs": 0,
            "output": f"ERROR: {e}",
        }

    try:
        crp_result = run_crp(args, system, task)
    except Exception as e:
        print(f"TEST B FAILED: {e}")
        import traceback
        traceback.print_exc()
        crp_result = {
            "method": "FAILED", "elapsed": 0, "clean_chars": 0,
            "words": 0, "sections_found": [], "sections_count": 0,
            "has_conclusion": False, "paragraphs": 0,
            "continuation_windows": 0, "facts_extracted": 0,
            "output": f"ERROR: {e}", "crp_logs": crp_log_lines.copy(),
        }

    write_report(direct, crp_result, args)

    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
