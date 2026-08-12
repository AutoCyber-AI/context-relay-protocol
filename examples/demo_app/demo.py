#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Comprehensive Demo — The definitive showcase of the Context Relay Protocol.

Demonstrates ALL 9 dispatch strategies, compliance features, session management,
and the full power of CRP's context continuity engine.

Modes:
  python demo.py                            # Interactive menu
  python demo.py compare                    # Direct LLM vs CRP side-by-side
  python demo.py strategies                 # All 9 dispatch strategies
  python demo.py compliance                 # EU AI Act / GDPR compliance demo
  python demo.py full                       # Complete showcase (all demos)
  python demo.py generate                   # Generate YOUR content with a REAL LLM

Options:
  --mock                                    # Use built-in mock provider (no API key)
  --provider {openai,anthropic,ollama,lmstudio}  # LLM provider
  --model MODEL                             # Override default model
  --verbose / -v                            # Show extraction details + audit trail
  --quiet / -q                              # Minimal output

The demo works OFFLINE with --mock (default when no API key is detected).
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
import time

# ---------------------------------------------------------------------------
# Ensure CRP is importable from the repo root (development mode)
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.isfile(os.path.join(_REPO_ROOT, "pyproject.toml")):
    sys.path.insert(0, _REPO_ROOT)

import crp  # noqa: E402
from crp.providers import CustomProvider, OpenAIAdapter, OllamaAdapter  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

BANNER = r"""
 ╔═══════════════════════════════════════════════════════════════════════╗
 ║              CRP — Context Relay Protocol v{version:<22s}      ║
 ║                                                                     ║
 ║     Unbounded context · Unbounded generation · Amplified AI         ║
 ║                                                                     ║
 ║     9 Dispatch Strategies · 6-Stage Extraction · HMAC Audit Trail   ║
 ║     EU AI Act Ready · Provider Agnostic · Zero Lock-in              ║
 ╚═══════════════════════════════════════════════════════════════════════╝
"""

DOMAIN_KNOWLEDGE = (
    "Kubernetes uses etcd as its distributed key-value store for all cluster "
    "state. The API server is the only component that directly interacts with "
    "etcd. Pod scheduling is handled by kube-scheduler which considers resource "
    "requirements, affinity rules, taints, and tolerations. The Container "
    "Network Interface (CNI) provides networking between pods across nodes. "
    "Calico, Flannel, and Cilium are popular CNI plugins with different "
    "networking models. Service mesh implementations like Istio and Linkerd "
    "add observability, traffic management, and mutual TLS. Horizontal Pod "
    "Autoscaler (HPA) scales based on CPU, memory, or custom Prometheus metrics. "
    "Vertical Pod Autoscaler (VPA) adjusts resource requests automatically. "
    "Network Policies use label selectors to restrict pod-to-pod traffic. "
    "Kubernetes RBAC uses Roles, ClusterRoles, RoleBindings, and "
    "ClusterRoleBindings for access control. Pod Security Standards (PSS) "
    "define three levels: Privileged, Baseline, and Restricted. "
    "Ingress controllers like NGINX and Traefik manage external HTTP/HTTPS "
    "traffic routing. CoreDNS handles service discovery within the cluster. "
    "StatefulSets manage stateful workloads with stable network identities "
    "and persistent storage. DaemonSets ensure a pod runs on every node. "
    "CronJobs handle scheduled batch processing. ConfigMaps and Secrets "
    "externalize configuration from container images."
)

AI_GOVERNANCE_KNOWLEDGE = (
    "The EU AI Act (Regulation 2024/1689) classifies AI systems into four "
    "risk levels: unacceptable (banned), high-risk (strict requirements), "
    "limited risk (transparency), and minimal risk (unregulated). "
    "High-risk AI systems must implement: risk management systems (Art. 9), "
    "data governance (Art. 10), technical documentation (Art. 11), "
    "record-keeping with automatic event logging (Art. 12), "
    "transparency and information to deployers (Art. 13), "
    "human oversight measures (Art. 14), and accuracy, robustness and "
    "cybersecurity (Art. 15). Quality management systems are required (Art. 17). "
    "Conformity assessments must be completed before market placement. "
    "Penalties range up to 35 million EUR or 7% of global turnover. "
    "High-risk rules take effect August 2026. "
    "ISO/IEC 42001:2023 is the first international AI management system "
    "standard (AIMS). It requires risk assessment, transparency controls, "
    "traceability, and continuous improvement. "
    "NIST AI RMF provides four core functions: Govern (policies, roles), "
    "Map (context, risks), Measure (metrics, monitoring), Manage (response, "
    "mitigation). 72 subcategories across these functions. "
    "GDPR requires lawful processing basis (Art. 6), data protection by "
    "design (Art. 25), records of processing activities (Art. 30), "
    "data protection impact assessments for high-risk processing (Art. 35), "
    "and the right to erasure (Art. 17). "
    "The NIST GenAI Profile (AI 600-1) extends the RMF for generative AI "
    "with 12 additional risk categories including hallucination, CBRN, "
    "confabulation, and environmental impact."
)

SYSTEM_PROMPT = (
    "You are a senior infrastructure architect. Write detailed, practical "
    "technical documentation with clear section headers and concrete examples."
)

COMPLIANCE_SYSTEM_PROMPT = (
    "You are an AI governance and regulatory compliance expert specializing "
    "in the EU AI Act, ISO 42001, GDPR, and NIST AI RMF."
)


# ═══════════════════════════════════════════════════════════════════════════
# MOCK PROVIDER — works offline, no API key needed
# ═══════════════════════════════════════════════════════════════════════════

class _DemoMockProvider:
    """Simulates an LLM for offline CRP demos.

    Generates structured text that behaves like a real LLM:
    - Respects max_tokens limits (returns finish_reason='length' when hit)
    - Produces extractable facts with named entities
    - Generates section-by-section content for continuation demos
    """

    _SECTIONS = [
        ("## Section 1: Architecture Patterns\n\n"
         "Production AI systems require layered architecture with clear "
         "separation between data ingestion, feature engineering, model "
         "serving, and monitoring. The microservices pattern enables "
         "independent scaling of each component. API gateways handle "
         "authentication, rate limiting, and request routing. "
         "Event-driven architectures using Apache Kafka or AWS Kinesis "
         "enable real-time feature computation and model updates.\n\n"),
        ("## Section 2: Data Pipeline Design\n\n"
         "Robust data pipelines form the foundation of any AI system. "
         "Apache Airflow orchestrates complex DAG-based workflows. "
         "Data validation using Great Expectations catches schema drift "
         "and anomalies before they reach model training. Feature stores "
         "like Feast or Tecton provide consistent feature serving across "
         "training and inference. Data versioning with DVC enables "
         "reproducible experiments.\n\n"),
        ("## Section 3: Model Training Infrastructure\n\n"
         "Distributed training frameworks like PyTorch DDP and DeepSpeed "
         "enable training across multiple GPUs and nodes. Experiment "
         "tracking with MLflow or Weights & Biases captures hyperparameters, "
         "metrics, and artifacts. Automated hyperparameter optimization "
         "using Optuna or Ray Tune reduces manual effort. Training "
         "pipelines should support both scheduled retraining and "
         "triggered retraining based on data drift detection.\n\n"),
        ("## Section 4: Model Versioning and Registry\n\n"
         "A model registry serves as the single source of truth for all "
         "model artifacts, metadata, and lineage. MLflow Model Registry "
         "or Vertex AI Model Registry provide staging workflows with "
         "clear transitions between development, staging, and production. "
         "Each model version must include performance metrics, training "
         "data references, and approval status.\n\n"),
        ("## Section 5: Monitoring and Observability\n\n"
         "Production monitoring must cover model performance (accuracy, "
         "latency, throughput), data quality (feature distributions, "
         "missing values), infrastructure health (GPU utilization, memory), "
         "and business metrics (conversion rates, user satisfaction). "
         "Prometheus and Grafana provide real-time metrics dashboards. "
         "Alerting rules detect performance degradation before users "
         "notice.\n\n"),
        ("## Section 6: Drift Detection\n\n"
         "Data drift occurs when input distributions shift from training "
         "data. Concept drift occurs when the relationship between "
         "inputs and outputs changes. Statistical tests like KS-test, "
         "PSI, and Jensen-Shannon divergence quantify drift magnitude. "
         "Automated retraining triggers when drift exceeds thresholds.\n\n"),
        ("## Section 7: Security and Access Control\n\n"
         "AI system security requires defense in depth: network isolation, "
         "identity-based access (OAuth 2.0, OIDC), secret management "
         "(HashiCorp Vault), encrypted model artifacts, and audit logging. "
         "Model serving endpoints need rate limiting and input validation "
         "to prevent adversarial attacks and prompt injection.\n\n"),
        ("## Section 8: Compliance and Audit\n\n"
         "Regulatory compliance requires full traceability from training "
         "data through model decisions. The EU AI Act mandates risk "
         "management, technical documentation, and human oversight for "
         "high-risk systems. Tamper-evident audit trails with "
         "cryptographic chaining provide non-repudiation. "
         "GDPR requires data protection impact assessments.\n\n"),
        ("## Section 9: Scaling Strategies\n\n"
         "Horizontal scaling distributes inference across multiple "
         "replicas behind a load balancer. Model sharding splits large "
         "models across GPUs. Quantization (INT8, FP16) reduces memory "
         "footprint and increases throughput. Caching frequent predictions "
         "with Redis reduces latency for common queries.\n\n"),
        ("## Section 10: Conclusion and Future Outlook\n\n"
         "Building production-ready AI systems requires deep integration "
         "across data engineering, ML engineering, DevOps, and security. "
         "The future points toward automated ML pipelines, edge-cloud "
         "hybrid architectures, and regulatory-first design patterns. "
         "Organizations that invest in robust infrastructure today will "
         "have a significant competitive advantage.\n\n"),
    ]

    def __init__(self) -> None:
        self._call_count = 0

    def generate_chat(
        self, messages: list[dict], **kwargs: object
    ) -> tuple[str, str]:
        self._call_count += 1
        max_tokens = int(kwargs.get("max_tokens", 2048))

        last_msg = messages[-1].get("content", "") if messages else ""
        sys_msg = messages[0].get("content", "") if messages else ""
        is_continuation = any(
            kw in last_msg.lower()
            for kw in ["continue", "resume", "remaining", "next section"]
        )
        # Only match compliance/evaluation if the system prompt indicates
        # this is a governance task (avoids false matches on section lists)
        is_compliance = "governance" in sys_msg.lower() and any(
            kw in last_msg.lower()
            for kw in ["eu ai act", "compliance steps", "gdpr", "recruit"]
        )
        is_evaluation = "governance" in sys_msg.lower() and any(
            kw in last_msg.lower()
            for kw in ["evaluate", "assess quality", "verify output"]
        )

        if is_compliance:
            return self._compliance_response(max_tokens)
        if is_evaluation:
            return self._evaluation_response(max_tokens)

        sections = self._topic_sections(last_msg)
        start_idx = 0 if not is_continuation else min(
            self._call_count * 3, len(sections)
        )
        output_parts: list[str] = []
        token_budget = max_tokens
        for section in sections[start_idx:]:
            section_tokens = len(section) // 4
            if section_tokens > token_budget:
                chars = token_budget * 4
                output_parts.append(section[:chars])
                return "".join(output_parts), "length"
            output_parts.append(section)
            token_budget -= section_tokens

        return "".join(output_parts), "stop"

    def _topic_sections(self, prompt: str) -> list[str]:
        """Return sections tailored to the task topic."""
        lower = prompt.lower()
        if any(kw in lower for kw in ["kubernetes", "k8s", "pod", "cni",
                                       "rbac", "etcd", "autoscal"]):
            return self._K8S_SECTIONS
        return self._SECTIONS

    _K8S_SECTIONS = [
        ("## Section 1: Pod Networking Architecture\n\n"
         "Kubernetes assigns each pod a unique IP address within the cluster "
         "network. The Container Network Interface (CNI) plugin handles IP "
         "allocation and routing. Popular CNI plugins include Calico (BGP-based "
         "networking with network policy support), Flannel (simple overlay "
         "using VXLAN), and Cilium (eBPF-powered networking and observability). "
         "Pods communicate directly without NAT on the flat cluster network.\n\n"),
        ("## Section 2: Service Discovery and DNS\n\n"
         "Kubernetes Services provide stable endpoints for pod groups. "
         "CoreDNS resolves service names to ClusterIP addresses. Three "
         "service types exist: ClusterIP (internal only), NodePort (external "
         "via node ports 30000-32767), and LoadBalancer (cloud provider LB). "
         "Headless services (clusterIP: None) return individual pod IPs "
         "for stateful workloads like databases.\n\n"),
        ("## Section 3: Network Policies\n\n"
         "NetworkPolicy resources control pod-to-pod and pod-to-external "
         "traffic. By default, all pods accept all traffic. Applying a "
         "NetworkPolicy implicitly denies unmatched traffic. Policies specify "
         "ingress and egress rules using pod selectors, namespace selectors, "
         "and CIDR blocks. Calico and Cilium support extended policy features "
         "beyond the standard Kubernetes API.\n\n"),
        ("## Section 4: RBAC Implementation\n\n"
         "Role-Based Access Control in Kubernetes uses four objects: Role "
         "(namespace-scoped permissions), ClusterRole (cluster-wide), "
         "RoleBinding (grants Role to subjects), and ClusterRoleBinding. "
         "Best practice: use least-privilege Roles, avoid wildcard verbs, "
         "bind to ServiceAccounts not users, and audit RBAC regularly. "
         "The system:masters group should never appear in production "
         "bindings except for break-glass procedures.\n\n"),
        ("## Section 5: etcd and Cluster State\n\n"
         "etcd is the distributed key-value store backing all Kubernetes "
         "state. It stores objects in /registry/<resource>/<namespace>/<name>. "
         "etcd uses the Raft consensus algorithm requiring 2f+1 nodes to "
         "tolerate f failures. Production clusters run 3 or 5 etcd members. "
         "Regular snapshots, TLS encryption, and access restriction via "
         "client certificates are mandatory for production.\n\n"),
        ("## Section 6: Horizontal Pod Autoscaling\n\n"
         "HPA adjusts replica count based on observed metrics. CPU and memory "
         "metrics come from the Metrics API (metrics-server). Custom metrics "
         "from Prometheus use the custom.metrics.k8s.io API via "
         "prometheus-adapter. Scaling behavior controls stabilization windows "
         "to prevent thrashing. VPA (Vertical Pod Autoscaler) adjusts "
         "resource requests instead of replica count.\n\n"),
        ("## Section 7: Service Mesh Architecture\n\n"
         "Service meshes like Istio and Linkerd inject sidecar proxies into "
         "each pod for transparent mTLS, traffic management, and observability. "
         "Istio uses Envoy proxies with a control plane (Istiod) for config "
         "distribution. Linkerd uses a Rust-based micro-proxy (linkerd2-proxy) "
         "with lower resource overhead. Both provide circuit breaking, "
         "retries, and distributed tracing.\n\n"),
        ("## Section 8: Pod Security Standards\n\n"
         "Pod Security Admission enforces three profiles: Privileged "
         "(unrestricted), Baseline (prevents known privilege escalations), "
         "and Restricted (hardened, follows best practices). Key restrictions "
         "include: no privileged containers, no hostPath mounts, "
         "runAsNonRoot required, drop ALL capabilities, seccomp profile "
         "RuntimeDefault. Apply at namespace level using labels.\n\n"),
        ("## Section 9: Secrets Management\n\n"
         "Kubernetes Secrets store sensitive data as base64-encoded values. "
         "Enable encryption at rest via EncryptionConfiguration with AES-CBC "
         "or KMS provider. Use external secrets operators (External Secrets "
         "Operator, Vault Agent) for production. Mount secrets as files, not "
         "environment variables, to reduce exposure. Rotate secrets regularly "
         "and audit access via RBAC.\n\n"),
        ("## Section 10: Conclusion\n\n"
         "Kubernetes security requires defense in depth: network policies "
         "for traffic control, RBAC for access control, pod security standards "
         "for workload hardening, encrypted secrets, and continuous monitoring. "
         "The combination of CNI-level network policy, service mesh mTLS, "
         "and proper RBAC creates a comprehensive security posture for "
         "production clusters.\n\n"),
    ]

    def _compliance_response(self, max_tokens: int) -> tuple[str, str]:
        text = (
            "## EU AI Act Compliance Assessment\n\n"
            "### Risk Classification\n"
            "Based on the system description, this AI system is classified "
            "as **HIGH-RISK** under EU AI Act Annex III, Category 4 "
            "(Employment and worker management). This classification "
            "triggers mandatory compliance with Articles 8-17.\n\n"
            "### Required Compliance Steps\n\n"
            "1. **Risk Management System (Art. 9)**: Implement continuous "
            "risk identification, analysis, estimation, and evaluation.\n\n"
            "2. **Data Governance (Art. 10)**: Ensure training datasets are "
            "relevant, representative, and free of errors.\n\n"
            "3. **Technical Documentation (Art. 11)**: Maintain comprehensive "
            "documentation covering system design and performance metrics.\n\n"
            "4. **Record-Keeping (Art. 12)**: Implement automatic logging "
            "of all system events with tamper-evident chains.\n\n"
            "5. **Transparency (Art. 13)**: Provide clear instructions for "
            "deployers including intended purpose and limitations.\n\n"
            "6. **Human Oversight (Art. 14)**: Design the system so that "
            "qualified personnel can effectively oversee its operation.\n\n"
            "7. **Accuracy and Robustness (Art. 15)**: Achieve appropriate "
            "levels of accuracy with resilience against adversarial attacks.\n\n"
            "8. **Quality Management (Art. 17)**: Establish a quality "
            "management system covering all requirements.\n\n"
            "### Timeline\n"
            "High-risk AI rules take effect **August 2026**. Non-compliance "
            "penalties: up to EUR 35M or 7% of global annual turnover.\n"
        )
        return text, "stop"

    def _evaluation_response(self, max_tokens: int) -> tuple[str, str]:
        text = (
            "## Quality Evaluation\n\n"
            "The output demonstrates strong technical coverage with "
            "specific technologies named (Apache Kafka, Airflow, MLflow). "
            "However, the following gaps were identified:\n\n"
            "1. Missing edge deployment patterns.\n"
            "2. Limited cost analysis.\n"
            "3. No disaster recovery section.\n\n"
            "Recommendation: Expand sections on edge deployment.\n"
        )
        return text, "stop"

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def context_window_size(self) -> int:
        return 128_000

    @property
    def max_output_tokens(self) -> int:
        return 4096

    @property
    def model_name(self) -> str:
        return "crp-demo-mock-v1"

    def cost_per_1k_tokens(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def supports_tools(self) -> bool:
        return False


# ═══════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def _header(title: str, char: str = "=") -> None:
    width = 70
    print(f"\n  {char * width}")
    print(f"  {title:^{width}}")
    print(f"  {char * width}")


def _subheader(title: str) -> None:
    print(f"\n  -- {title} {'-' * max(1, 60 - len(title))}")


def _info(label: str, value: object, indent: int = 4) -> None:
    print(f"  {' ' * indent}{label:<28s}: {value}")


def _section_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip().startswith("## "))


def _word_count(text: str) -> int:
    return len(text.split())


def _show_preview(text: str, max_words: int = 50, indent: int = 6) -> None:
    """Show a short preview of the generated text."""
    words = text.split()
    preview = " ".join(words[:max_words])
    if len(words) > max_words:
        preview += " ..."
    pad = " " * indent
    print(f"\n{pad}Preview:")
    for line in textwrap.wrap(preview, width=70):
        print(f"{pad}  {line}")
    print()


def _has_conclusion(text: str) -> bool:
    lower = text.lower()
    return "conclusion" in lower or "future outlook" in lower


# ═══════════════════════════════════════════════════════════════════════════
# PROVIDER SETUP
# ═══════════════════════════════════════════════════════════════════════════

def _create_provider(args: argparse.Namespace) -> object:
    """Create the appropriate LLM provider based on CLI args."""
    if args.mock:
        print("  Provider : Mock (offline demo -- no API key required)")
        return _DemoMockProvider()

    provider_name = args.provider
    if not provider_name:
        provider_name = _detect_provider()

    model = args.model
    print(f"  Provider : {provider_name}")
    print(f"  Model    : {model or '(default)'}")

    if provider_name == "openai":
        return OpenAIAdapter(model=model or "gpt-4o-mini")
    elif provider_name == "anthropic":
        from crp.providers import AnthropicAdapter
        return AnthropicAdapter(model=model or "claude-sonnet-4-20250514")
    elif provider_name == "ollama":
        return OllamaAdapter(model=model or "llama3.1")
    elif provider_name == "lmstudio":
        return OpenAIAdapter(
            model=model or "qwen3-4b",
            base_url="http://localhost:1234/v1",
            api_key="lm-studio",
        )
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


def _detect_provider() -> str:
    """Auto-detect available provider from environment."""
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:1234/v1/models", timeout=1)
        return "lmstudio"
    except Exception:
        pass
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/version", timeout=1)
        return "ollama"
    except Exception:
        pass
    return "mock"


# ═══════════════════════════════════════════════════════════════════════════
# DEMO 1: COMPARE — Direct LLM vs CRP
# ═══════════════════════════════════════════════════════════════════════════

def demo_compare(args: argparse.Namespace) -> None:
    """Side-by-side comparison: raw LLM (truncated) vs CRP (complete)."""
    _header("DEMO: Direct LLM vs CRP-Orchestrated Dispatch")
    print(textwrap.dedent("""
      This demo shows the fundamental CRP value proposition:

        Phase 1: Call an LLM directly with a 512-token output cap
                 -> Output is TRUNCATED mid-sentence

        Phase 2: Same task through CRP's dispatch() with the SAME token cap
                 -> CRP's continuation engine detects the wall hit, extracts
                    facts from partial output, packs them into the next
                    window's envelope, and resumes generation seamlessly.
                 -> Output is COMPLETE with conclusion.

      The LLM never changes. CRP manages the context lifecycle.
    """))
    provider = _create_provider(args)

    task = (
        "Write a comprehensive technical document about 'Building "
        "Production-Ready AI Systems' covering at least 10 sections: "
        "Architecture Patterns, Data Pipelines, Model Training, Versioning, "
        "Monitoring, Drift Detection, Security, Compliance, Scaling, "
        "and Conclusion. Each section needs 2-3 detailed paragraphs."
    )

    # -- Phase 1: Direct LLM --
    _subheader("Phase 1: Direct LLM Call (capped at 512 tokens)")
    start = time.perf_counter()
    direct_output, finish_reason = provider.generate_chat(
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user", "content": task}],
        max_tokens=512,
    )
    direct_time = time.perf_counter() - start
    d_words = _word_count(direct_output)
    d_sections = _section_count(direct_output)
    d_truncated = finish_reason == "length"

    _info("Finish reason", finish_reason)
    _info("Truncated", "YES" if d_truncated else "No")
    _info("Words generated", f"{d_words:,}")
    _info("Sections complete", f"{d_sections} / 10")
    _info("Has conclusion", "No" if not _has_conclusion(direct_output) else "Yes")
    _info("Time", f"{direct_time:.1f}s")
    _info("Facts extracted", "0 (no extraction pipeline)")
    _info("Audit trail", "None")

    if d_truncated and not args.quiet:
        print(f"\n      Last 150 chars (truncated mid-sentence):")
        for line in textwrap.wrap(direct_output[-150:], width=58):
            print(f"        ...{line}")

    # -- Phase 2: CRP Dispatch --
    _subheader("Phase 2: CRP dispatch() — Continuation Engine Active")
    client = crp.Client(provider=provider, max_output_tokens=512)

    start = time.perf_counter()
    crp_output, report = client.dispatch(
        system_prompt=SYSTEM_PROMPT,
        task_input=task,
    )
    crp_time = time.perf_counter() - start
    c_words = _word_count(crp_output)
    c_sections = _section_count(crp_output)

    _info("Quality tier", report.quality_tier)
    _info("Words generated", f"{c_words:,}")
    _info("Sections complete", f"{c_sections} / 10")
    _info("Has conclusion", "Yes" if _has_conclusion(crp_output) else "No")
    _info("Facts extracted", report.facts_extracted)
    _info("Continuation windows", report.continuation_windows)
    _info("Envelope saturation", f"{report.envelope_saturation:.0%}")
    _info("Time", f"{crp_time:.1f}s")
    _info("Audit trail", "HMAC-SHA256 chained")

    if args.verbose:
        _show_session_details(client, report)

    # -- Comparison Table --
    multiplier = c_words / d_words if d_words > 0 else 0
    _subheader("Comparison Table")
    fmt = "      {:<22} {:<16} {:<16} {:<10}"
    print(fmt.format("Metric", "Direct LLM", "CRP", "Gain"))
    print(fmt.format("-" * 22, "-" * 16, "-" * 16, "-" * 10))
    rows = [
        ("Words", f"{d_words:,}", f"{c_words:,}", f"{multiplier:.1f}x"),
        ("Sections (of 10)", str(d_sections), str(c_sections), ""),
        ("Complete output", "NO" if d_truncated else "Yes", "Yes", ""),
        ("Has conclusion", "No" if not _has_conclusion(direct_output) else "Yes",
         "Yes" if _has_conclusion(crp_output) else "No", ""),
        ("Facts extracted", "0", str(report.facts_extracted), ""),
        ("Quality tier", "N/A", str(report.quality_tier), ""),
        ("Audit trail", "None", "HMAC-SHA256", ""),
    ]
    for label, d, c, g in rows:
        print(fmt.format(label, d, c, g))

    print(f"\n      CRP delivered {multiplier:.1f}x more content using "
          f"{report.continuation_windows} continuation window(s).")
    print("      The LLM is the same. The difference is context management.")

    client.close()


# ═══════════════════════════════════════════════════════════════════════════
# DEMO 2: ALL 9 DISPATCH STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════

_STRATEGY_INFO = {
    "dispatch": {
        "label": "PUSH-based (default)",
        "spec": "section 6",
        "desc": (
            "Default strategy. CRP pre-loads the context envelope with the "
            "most relevant facts from the warm store, then sends the full "
            "envelope + task to the LLM. Continuation engine handles wall hits. "
            "Best for: general tasks where CRP has domain knowledge."
        ),
    },
    "dispatch_with_tools": {
        "label": "PULL-based / Tool-Mediated",
        "spec": "section 20",
        "desc": (
            "Instead of pre-loading context, the LLM is given CRP context "
            "tools (retrieve_facts, search_by_keyword). The LLM requests "
            "context ON DEMAND via tool calls. Best for: tasks where the "
            "LLM knows what it needs better than CRP does."
        ),
    },
    "dispatch_reflexive": {
        "label": "Verify-then-Refine",
        "spec": "section 21.1",
        "desc": (
            "Pass 1: generate with NO envelope (pure parametric knowledge). "
            "CRP analyzes output against KB, finds contradictions and "
            "unsupported claims. Pass 2+: model refines with precision. "
            "Best for: fact-checking, high-accuracy requirements."
        ),
    },
    "dispatch_progressive": {
        "label": "Index-then-Detail",
        "spec": "section 21.2",
        "desc": (
            "Builds compact INDEX of available facts (~10% token cost). "
            "Sends task + index. Detects which entries were referenced. "
            "Expands referenced entries to full detail. "
            "Best for: large knowledge bases where not all context is relevant."
        ),
    },
    "dispatch_stream_augmented": {
        "label": "Real-time Context Injection",
        "spec": "section 21.3",
        "desc": (
            "Streams generation without envelope. After each sentence, CRP "
            "fact-matches against warm store. If relevant NEW facts found, "
            "injects them mid-stream. Best for: dynamic, exploration-style tasks."
        ),
    },
    "dispatch_agentic": {
        "label": "Cognitive Engine",
        "spec": "section 22",
        "desc": (
            "8-phase cognitive loop: ANALYZE task -> PLAN decomposition -> "
            "SYNTHESIZE KB -> ROUTE to optimal strategy -> GENERATE -> "
            "EVALUATE quality -> REVISE if needed -> CURATE KB. "
            "Best for: complex multi-step tasks requiring autonomous reasoning."
        ),
    },
    "dispatch_stream": {
        "label": "Streaming",
        "spec": "section 6.10.5",
        "desc": (
            "Yields StreamEvent objects in real-time: token events, "
            "extraction events, window_complete events, and done event. "
            "Token concatenation produces same string as dispatch(). "
            "Best for: real-time UIs, chatbots, interactive applications."
        ),
    },
    "dispatch_batch": {
        "label": "Batch Processing",
        "spec": "section 6.6",
        "desc": (
            "Dispatches multiple tasks sequentially through the same session. "
            "Facts accumulate across tasks — each subsequent task benefits "
            "from previously extracted knowledge. "
            "Best for: processing multiple related tasks, report generation."
        ),
    },
    "dispatch_hierarchical": {
        "label": "Map-Reduce",
        "spec": "section 14",
        "desc": (
            "Segments large input into chunks, dispatches each through the "
            "LLM, then iteratively reduces the syntheses. All facts from "
            "every segment stored in warm store + CKF. "
            "Best for: analyzing documents that exceed context windows."
        ),
    },
}


def demo_strategies(args: argparse.Namespace) -> None:
    """Demonstrate all 9 CRP dispatch strategies."""
    _header("DEMO: All 9 CRP Dispatch Strategies")
    print(textwrap.dedent("""
      CRP provides 9 dispatch strategies, each optimized for different use
      cases. Every strategy benefits from CRP's 6-stage extraction pipeline,
      quality tier assessment, and HMAC-chained audit trail.

      This demo ingests domain knowledge, then runs each strategy against a
      relevant task to show its strengths.
    """))
    provider = _create_provider(args)

    # Ingest domain knowledge
    print("\n  Ingesting domain knowledge into CRP warm store...")
    client = crp.Client(provider=provider)
    result = client.ingest(DOMAIN_KNOWLEDGE)
    print(f"  Ingested {result.facts_extracted} facts from "
          f"{_word_count(DOMAIN_KNOWLEDGE)} words of Kubernetes documentation")
    print()

    strategies = [
        ("1", "dispatch", _run_dispatch),
        ("2", "dispatch_with_tools", _run_dispatch_with_tools),
        ("3", "dispatch_reflexive", _run_reflexive),
        ("4", "dispatch_progressive", _run_progressive),
        ("5", "dispatch_stream_augmented", _run_stream_augmented),
        ("6", "dispatch_agentic", _run_agentic),
        ("7", "dispatch_stream", _run_stream),
        ("8", "dispatch_batch", _run_batch),
        ("9", "dispatch_hierarchical", _run_hierarchical),
    ]

    results = []
    total = len(strategies)
    for idx, (num, name, func) in enumerate(strategies, 1):
        info = _STRATEGY_INFO[name]
        _subheader(f"Strategy {num}/9: {info['label']} -- {name}()")
        print(f"      Spec: {info['spec']}")
        print(f"      Progress: [{idx}/{total}]")
        for line in textwrap.wrap(info["desc"], width=64):
            print(f"      {line}")
        print()

        try:
            r = func(client, args)
            results.append((num, info["label"], r))
        except Exception as e:
            print(f"      [skipped] {e}")
            results.append((num, info["label"], {"words": 0, "elapsed": 0}))

    # Summary table
    _subheader("Strategy Comparison Summary")
    fmt = "      {:<4} {:<26} {:<10} {:<10}"
    print(fmt.format("#", "Strategy", "Words", "Time"))
    print(fmt.format("-" * 4, "-" * 26, "-" * 10, "-" * 10))
    for num, label, r in results:
        w = r.get("words", 0)
        t = r.get("elapsed", 0)
        print(fmt.format(num, label, f"{w:,}", f"{t:.1f}s"))

    print("\n      All 9 strategies share the same session. Facts extracted by")
    print("      earlier strategies are available to later ones via the warm store.")

    client.close()


def _run_dispatch(client: crp.CRPOrchestrator, args: argparse.Namespace) -> dict:
    task = ("Explain Kubernetes pod networking architecture including CNI "
            "plugins, service discovery, and network policies.")
    start = time.perf_counter()
    output, report = client.dispatch(system_prompt=SYSTEM_PROMPT, task_input=task)
    elapsed = time.perf_counter() - start
    words = _word_count(output)
    _info("Words", f"{words:,}", indent=6)
    _info("Facts extracted", report.facts_extracted, indent=6)
    _info("Quality tier", report.quality_tier, indent=6)
    _info("Continuation windows", report.continuation_windows, indent=6)
    _info("Time", f"{elapsed:.1f}s", indent=6)
    _show_preview(output)
    return {"words": words, "elapsed": elapsed}


def _run_dispatch_with_tools(
    client: crp.CRPOrchestrator, args: argparse.Namespace
) -> dict:
    task = ("What CNI plugins are available for Kubernetes and how do they "
            "differ in their networking models?")
    start = time.perf_counter()
    try:
        output, report = client.dispatch_with_tools(
            system_prompt=SYSTEM_PROMPT, task_input=task, max_tool_rounds=5)
    except Exception:
        output, report = client.dispatch(
            system_prompt=SYSTEM_PROMPT, task_input=task)
        print("        (Fell back to dispatch -- provider lacks tool support)")
    elapsed = time.perf_counter() - start
    words = _word_count(output)
    _info("Words", f"{words:,}", indent=6)
    _info("Facts extracted", report.facts_extracted, indent=6)
    _info("Quality tier", report.quality_tier, indent=6)
    _info("Time", f"{elapsed:.1f}s", indent=6)
    _show_preview(output)
    return {"words": words, "elapsed": elapsed}


def _run_reflexive(
    client: crp.CRPOrchestrator, args: argparse.Namespace
) -> dict:
    task = ("Describe best practices for Kubernetes RBAC implementation "
            "including roles, bindings, and least-privilege principles.")
    start = time.perf_counter()
    output, report = client.dispatch_reflexive(
        system_prompt=SYSTEM_PROMPT, task_input=task, max_refinement_passes=2)
    elapsed = time.perf_counter() - start
    words = _word_count(output)
    _info("Words", f"{words:,}", indent=6)
    _info("Facts extracted", report.facts_extracted, indent=6)
    _info("Refinement passes", "up to 2", indent=6)
    _info("Time", f"{elapsed:.1f}s", indent=6)
    _show_preview(output)
    return {"words": words, "elapsed": elapsed}


def _run_progressive(
    client: crp.CRPOrchestrator, args: argparse.Namespace
) -> dict:
    task = ("Explain horizontal pod autoscaling in Kubernetes including "
            "metrics sources and custom metrics from Prometheus.")
    start = time.perf_counter()
    output, report = client.dispatch_progressive(
        system_prompt=SYSTEM_PROMPT, task_input=task)
    elapsed = time.perf_counter() - start
    words = _word_count(output)
    _info("Words", f"{words:,}", indent=6)
    _info("Facts extracted", report.facts_extracted, indent=6)
    _info("Time", f"{elapsed:.1f}s", indent=6)
    _show_preview(output)
    return {"words": words, "elapsed": elapsed}


def _run_stream_augmented(
    client: crp.CRPOrchestrator, args: argparse.Namespace
) -> dict:
    task = ("How does Kubernetes service mesh architecture work, specifically "
            "comparing Istio and Linkerd?")
    start = time.perf_counter()
    output, report = client.dispatch_stream_augmented(
        system_prompt=SYSTEM_PROMPT, task_input=task, max_injections=3)
    elapsed = time.perf_counter() - start
    words = _word_count(output)
    _info("Words", f"{words:,}", indent=6)
    _info("Facts extracted", report.facts_extracted, indent=6)
    _info("Context injections", "up to 3", indent=6)
    _info("Time", f"{elapsed:.1f}s", indent=6)
    _show_preview(output)
    return {"words": words, "elapsed": elapsed}


def _run_agentic(
    client: crp.CRPOrchestrator, args: argparse.Namespace
) -> dict:
    task = ("Design a complete Kubernetes security hardening strategy "
            "covering network policies, RBAC, pod security, and secrets.")
    start = time.perf_counter()
    output, report = client.dispatch_agentic(
        system_prompt=SYSTEM_PROMPT, task_input=task,
        max_revision_rounds=1, enable_planning=True)
    elapsed = time.perf_counter() - start
    words = _word_count(output)
    _info("Words", f"{words:,}", indent=6)
    _info("Facts extracted", report.facts_extracted, indent=6)
    _info("Cognitive phases", "8 (analyze/plan/synthesize/route/generate/evaluate/revise/curate)", indent=6)
    _info("Time", f"{elapsed:.1f}s", indent=6)
    _show_preview(output)
    return {"words": words, "elapsed": elapsed}


def _run_stream(
    client: crp.CRPOrchestrator, args: argparse.Namespace
) -> dict:
    task = "Explain the role of etcd in Kubernetes cluster state management."
    start = time.perf_counter()
    token_count = 0
    extraction_events = 0
    full_text: list[str] = []
    for event in client.dispatch_stream(
        system_prompt=SYSTEM_PROMPT, task_input=task
    ):
        if event.event_type == "token":
            token_count += 1
            full_text.append(event.data)
        elif event.event_type == "extraction":
            extraction_events += 1
        elif event.event_type == "done":
            break
    elapsed = time.perf_counter() - start
    words = _word_count("".join(full_text))
    _info("Words", f"{words:,}", indent=6)
    _info("Token events yielded", token_count, indent=6)
    _info("Extraction events", extraction_events, indent=6)
    _info("Time", f"{elapsed:.1f}s", indent=6)
    _show_preview("".join(full_text))
    return {"words": words, "elapsed": elapsed}


def _run_batch(
    client: crp.CRPOrchestrator, args: argparse.Namespace
) -> dict:
    intents = [
        {"system_prompt": SYSTEM_PROMPT,
         "task_input": "Explain Kubernetes ConfigMaps and when to use them."},
        {"system_prompt": SYSTEM_PROMPT,
         "task_input": "Explain Kubernetes Secrets and best practices."},
        {"system_prompt": SYSTEM_PROMPT,
         "task_input": "Compare ConfigMaps vs Secrets -- when to use each."},
    ]
    start = time.perf_counter()
    results = client.dispatch_batch(intents)
    elapsed = time.perf_counter() - start
    total_words = sum(_word_count(out) for out, _ in results)
    _info("Tasks dispatched", len(intents), indent=6)
    _info("Total words", f"{total_words:,}", indent=6)
    _info("Knowledge accumulation", "facts carry forward across tasks", indent=6)
    _info("Time", f"{elapsed:.1f}s", indent=6)
    if results:
        _show_preview(results[0][0])
    return {"words": total_words, "elapsed": elapsed}


def _run_hierarchical(
    client: crp.CRPOrchestrator, args: argparse.Namespace
) -> dict:
    large_input = DOMAIN_KNOWLEDGE + " " + AI_GOVERNANCE_KNOWLEDGE
    start = time.perf_counter()
    syntheses, report = client.dispatch_hierarchical(
        system_prompt=SYSTEM_PROMPT,
        large_input=large_input,
        task_intent="Summarize the key infrastructure and governance concepts",
    )
    elapsed = time.perf_counter() - start
    total_words = sum(_word_count(s) for s in syntheses)
    _info("Input words", f"{_word_count(large_input):,}", indent=6)
    _info("Output syntheses", len(syntheses), indent=6)
    _info("Total output words", f"{total_words:,}", indent=6)
    _info("Facts extracted", report.facts_extracted, indent=6)
    _info("Time", f"{elapsed:.1f}s", indent=6)
    if syntheses:
        _show_preview(syntheses[0])
    return {"words": total_words, "elapsed": elapsed}


# ═══════════════════════════════════════════════════════════════════════════
# DEMO 3: COMPLIANCE — EU AI Act, GDPR, ISO 42001, NIST AI RMF
# ═══════════════════════════════════════════════════════════════════════════

def demo_compliance(args: argparse.Namespace) -> None:
    """Demonstrate CRP's built-in AI governance and compliance features."""
    _header("DEMO: AI Governance & Regulatory Compliance")
    print(textwrap.dedent("""
      CRP implements 33/35 EU AI Act + ISO 42001 controls natively.
      Every dispatch automatically runs through:

        1. Consent verification (GDPR Art. 6)
        2. RBAC + rate limiting (Art. 15 cybersecurity)
        3. Input validation + PII scan (Art. 10 data governance)
        4. Injection detection (3 layers) (OWASP LLM01)
        5. HMAC audit logging (Art. 12 record-keeping)
        6. Human oversight check (Art. 14)
        7. Risk classification (Art. 6 / Art. 9)
        8. Quality assessment (Art. 17 quality management)
        9. Decision provenance (Art. 13 transparency)

      This demo shows each of these controls in action.
    """))
    provider = _create_provider(args)
    client = crp.Client(provider=provider)

    # Ingest governance knowledge
    print("  Ingesting AI governance domain knowledge...")
    result = client.ingest(AI_GOVERNANCE_KNOWLEDGE)
    print(f"  Ingested {result.facts_extracted} regulatory facts\n")

    # -- 1. Risk Classification --
    _subheader("1. Risk Classification (EU AI Act Art. 6)")
    try:
        risk = client.risk_classifier.assess(
            intended_purpose="AI-powered employee performance evaluation system",
            processes_personal_data=True,
            makes_automated_decisions=True,
        )
        _info("System purpose", "Employee performance evaluation")
        _info("Risk level", risk.risk_level.value if hasattr(risk.risk_level, 'value') else risk.risk_level)
        _info("System category", risk.system_category.value if hasattr(risk.system_category, 'value') else risk.system_category)
        _info("Mitigations", len(risk.mitigations))
        _info("Residual risks", len(risk.residual_risks))
    except Exception as e:
        print(f"      Risk classification: {e}")

    # -- 2. Human Oversight --
    _subheader("2. Human Oversight (EU AI Act Art. 14)")
    try:
        oversight = client.human_oversight
        _info("Current level", oversight.level.name)
        _info("Available levels", "NONE / INFORMED / APPROVAL / CONTROL")
        _info("Requires approval", oversight.requires_approval("dispatch"))
        print()
        print("      EU AI Act Art. 14 mandates 'effective oversight by natural")
        print("      persons during the period of use.' CRP implements 4 levels:")
        print("        NONE     : No oversight required (minimal risk)")
        print("        INFORMED : User notified of AI involvement")
        print("        APPROVAL : Explicit human approval before action")
        print("        CONTROL  : Human retains full control at all times")
    except Exception as e:
        print(f"      Human oversight: {e}")

    # -- 3. Compliance-Aware Dispatch --
    _subheader("3. Compliance-Aware Dispatch")
    task = ("A company is deploying an AI system for employee recruitment in "
            "the EU. What EU AI Act compliance steps are required?")

    start = time.perf_counter()
    output, report = client.dispatch(
        system_prompt=COMPLIANCE_SYSTEM_PROMPT,
        task_input=task,
    )
    elapsed = time.perf_counter() - start

    _info("Words generated", f"{_word_count(output):,}")
    _info("Quality tier", report.quality_tier)
    _info("Facts extracted", report.facts_extracted)
    _info("Injection markers detected", report.security_flags.injection_markers_detected)
    _info("Time", f"{elapsed:.1f}s")

    # -- 4. Audit Trail --
    _subheader("4. HMAC-SHA256 Audit Trail (Art. 12 Record-Keeping)")
    try:
        audit = client.compliance_audit
        valid, broken_at = audit.verify_chain()
        _info("Audit entries", audit.entry_count)
        _info("Chain integrity", "VERIFIED" if valid else f"TAMPERED at seq {broken_at}")
        _info("Hash algorithm", "HMAC-SHA256")
        _info("Chaining", "Each entry hash includes previous entry hash")
        print()
        print("      The audit trail records every CRP operation:")
        print("      dispatches, extractions, consent checks, PII scans,")
        print("      injection scans, compliance assessments, fact")
        print("      modifications -- all cryptographically chained.")
    except Exception as e:
        print(f"      Audit trail: {e}")

    # -- 5. PII Scanning --
    _subheader("5. PII Scanning (GDPR Art. 5 Data Minimization)")
    try:
        test_text = (
            "Contact John Smith at john.smith@example.com or call "
            "555-123-4567. His SSN is 123-45-6789."
        )
        pii_result = client.pii_scanner.scan(test_text)
        _info("Input text", test_text[:60] + "...")
        _info("PII detected", pii_result.has_pii)
        _info("PII types found", ", ".join(
            pii_result.pii_types_found) if pii_result.pii_types_found else "none")
        _info("Total matches", len(pii_result.detections))
        print()
        print("      CRP scans BOTH input and output for 10 PII patterns:")
        print("      email, phone, SSN, credit card, IP address, passport,")
        print("      drivers license, date of birth, bank account, NHS number")
    except Exception as e:
        print(f"      PII scanning: {e}")

    # -- 6. GDPR Processing Records --
    _subheader("6. GDPR Processing Records (Art. 30)")
    try:
        records = client.processing_records
        _info("Processing activities logged", records.activity_count)
        _info("Record format", "GDPR Art. 30 compliant")
        print()
        print("      Every CRP operation creates a processing record with:")
        print("      purpose, legal basis, data categories, retention period,")
        print("      recipients, and safeguards.")
    except Exception as e:
        print(f"      Processing records: {e}")

    # -- 7. Compliance Report --
    _subheader("7. Compliance Report Generation")
    try:
        session_status = client.session_status()
        reporter = client.compliance_reporter
        report_data = reporter.generate_report(
            session_stats={
                "session_id": session_status.session_id,
                "windows_completed": session_status.windows_completed,
                "facts_in_warm_state": session_status.facts_in_warm_state,
            },
        )
        summary = report_data.get("summary", {})
        _info("Frameworks covered", "EU AI Act, ISO 42001, GDPR, NIST AI RMF")
        _info("Controls assessed", f"{summary.get('implemented', 'N/A')}/"
              f"{summary.get('total_controls', 'N/A')}")
        _info("Compliance score", f"{summary.get('compliance_score', 'N/A')}")
        _info("Report format", "JSON + Markdown")
    except Exception as e:
        print(f"      Compliance report: {e}")

    # -- Summary --
    _subheader("Regulatory Framework Coverage Summary")
    print()
    fmt2 = "      {:<18} {:<22} {:<20}"
    print(fmt2.format("Framework", "Articles/Controls", "CRP Coverage"))
    print(fmt2.format("-" * 18, "-" * 22, "-" * 20))
    coverage = [
        ("EU AI Act", "Art. 6-17", "9/10 fully covered"),
        ("ISO 42001", "8 AIMS controls", "8/8 mapped"),
        ("GDPR", "Art. 5-35", "11 articles covered"),
        ("NIST AI RMF", "Govern/Map/Measure/Manage", "All 4 functions"),
        ("OWASP LLM Top 10", "10 categories", "9/10 covered"),
        ("OWASP ML Top 10", "10 categories", "8/10 covered"),
    ]
    for fw, arts, cov in coverage:
        print(fmt2.format(fw, arts, cov))
    print()
    print("      Total: 33/35 controls implemented (94% coverage)")
    print()
    print("      WHY THIS MATTERS (August 2026 deadline):")
    print("      The EU AI Act's high-risk requirements take effect in")
    print("      August 2026. Businesses deploying AI in employment,")
    print("      education, healthcare, law enforcement, or critical")
    print("      infrastructure MUST comply or face penalties up to")
    print("      EUR 35M or 7% of global turnover. CRP provides the")
    print("      technical infrastructure to meet these requirements.")

    client.close()


# ═══════════════════════════════════════════════════════════════════════════
# DEMO 4: FULL — Complete Showcase
# ═══════════════════════════════════════════════════════════════════════════

def demo_full(args: argparse.Namespace) -> None:
    """Run all demos sequentially."""
    _header("FULL CRP SHOWCASE")
    print("  Running all three demo suites.\n")

    demo_compare(args)
    demo_strategies(args)
    demo_compliance(args)

    _header("SHOWCASE COMPLETE")
    print(textwrap.dedent("""
      You have seen CRP's full capability:

        Context continuity    -- no more token wall truncation
        9 dispatch strategies -- each optimized for a use case
        6-stage extraction    -- facts accumulate across windows
        HMAC-SHA256 audit     -- tamper-evident compliance trail
        EU AI Act ready       -- 33/35 controls, Art. 6-17 coverage
        GDPR compliant        -- PII scanning, processing records, erasure
        ISO 42001 aligned     -- AI management system controls
        NIST AI RMF mapped    -- Govern / Map / Measure / Manage
        Provider agnostic     -- works with any LLM
        Zero lock-in          -- open protocol, portable state

      Getting started:
        pip install crprotocol[full]
        Read the spec: specification/
        GitHub: github.com/Constantinos-uni/context-relay-protocol
    """))


# ═══════════════════════════════════════════════════════════════════════════
# DEMO 5: GENERATE — Free-form generation with a REAL LLM
# ═══════════════════════════════════════════════════════════════════════════

def _prompt_provider_choice() -> tuple[str, str | None]:
    """Interactive provider/model picker for generate mode."""
    print("  Select your LLM provider:\n")
    print("    1) LM Studio    -- local, http://localhost:1234")
    print("    2) Ollama       -- local, http://localhost:11434")
    print("    3) OpenAI       -- cloud, requires OPENAI_API_KEY")
    print("    4) Anthropic    -- cloud, requires ANTHROPIC_API_KEY")
    print()
    choice = input("  Provider [1-4]: ").strip()
    providers = {"1": "lmstudio", "2": "ollama", "3": "openai", "4": "anthropic"}
    provider = providers.get(choice)
    if not provider:
        print("  Invalid choice — defaulting to LM Studio.")
        provider = "lmstudio"

    model = input(f"  Model name (Enter for default): ").strip() or None
    return provider, model


def demo_generate(args: argparse.Namespace) -> None:
    """Free-form content generation with a real LLM via CRP continuation."""
    _header("GENERATE: Create YOUR Content with CRP + Real LLM")
    print(textwrap.dedent("""
      This mode lets YOU choose the topic and generate a comprehensive,
      multi-chapter document using CRP's continuation engine with a REAL LLM.

      CRP will:
        1. Take your topic and desired chapter count
        2. Dispatch to your chosen LLM
        3. Automatically continue across output walls
        4. Extract and carry facts between windows
        5. Produce a complete document — not a truncated fragment

      Supported providers:
        - LM Studio   (local — run LM Studio with any GGUF model)
        - Ollama       (local — run ollama serve with any model)
        - OpenAI       (cloud — set OPENAI_API_KEY)
        - Anthropic    (cloud — set ANTHROPIC_API_KEY)
    """))

    # --- Provider selection ---
    if args.mock:
        print("  [!] Generate mode is designed for REAL LLMs.")
        print("      Using mock provider for demonstration.\n")
        provider = _DemoMockProvider()
        provider_name = "mock"
    elif args.provider:
        provider_name = args.provider
        provider = _create_provider(args)
    else:
        provider_name, model_override = _prompt_provider_choice()
        if model_override:
            args.model = model_override
        args.provider = provider_name
        args.mock = False
        provider = _create_provider(args)

    # --- Topic selection ---
    print()
    print("  Enter your topic. Examples:")
    print('    - "A comprehensive guide to microservices architecture"')
    print('    - "The complete history of quantum computing"')
    print('    - "Building a REST API with FastAPI from scratch"')
    print('    - "Machine learning for cybersecurity threat detection"')
    print()
    topic = input("  Your topic: ").strip()
    if not topic:
        topic = "A comprehensive guide to building production-ready AI systems"
        print(f"  (Using default: {topic})")

    # --- Chapter count ---
    chapters_str = input("  Number of chapters/sections [10]: ").strip()
    try:
        chapters = int(chapters_str) if chapters_str else 10
        chapters = max(3, min(chapters, 50))
    except ValueError:
        chapters = 10
    print(f"  Chapters: {chapters}")

    # --- System prompt ---
    system_prompt = (
        "You are an expert technical writer. Write comprehensive, well-structured "
        "content with clear headings, detailed explanations, and practical examples. "
        "Use markdown formatting."
    )

    task = (
        f"Write a comprehensive document about '{topic}' with exactly {chapters} "
        f"chapters/sections. Each chapter should have a clear heading (## Chapter N: Title), "
        f"2-4 detailed paragraphs, and practical examples or code where appropriate. "
        f"End with a conclusion that ties all chapters together."
    )

    # --- Optional: seed knowledge ---
    seed = input("  Seed knowledge (paste text, or Enter to skip): ").strip()

    # --- Run CRP ---
    _subheader(f"Generating: {topic}")
    print(f"    Provider : {provider_name}")
    print(f"    Chapters : {chapters}")
    print(f"    Strategy : dispatch (PUSH with continuation)")
    print()

    client = crp.CRPOrchestrator(provider=provider)

    if seed:
        print("    Ingesting seed knowledge...")
        client.ingest(seed)
        _info("Seed facts extracted", client.session_status().facts_in_warm_state)

    start = time.perf_counter()

    try:
        output, report = client.dispatch(
            system_prompt=system_prompt,
            task_input=task,
        )
    except Exception as exc:
        print(f"\n  [ERROR] Generation failed: {exc}")
        print("  Check that your LLM provider is running and accessible.")
        if provider_name == "lmstudio":
            print("  LM Studio: ensure server is running at http://localhost:1234")
        elif provider_name == "ollama":
            print("  Ollama: run 'ollama serve' and pull a model")
        return

    elapsed = time.perf_counter() - start
    words = len(output.split())

    # --- Results ---
    _subheader("Generation Complete")
    _info("Words generated", f"{words:,}")
    _info("Time", f"{elapsed:.1f}s")
    _info("Throughput", f"{words / elapsed:.1f} words/sec")
    try:
        _info("Quality tier", report.quality_tier)
        _info("Continuation windows", report.continuation_windows)
        _info("Facts extracted", report.facts_extracted)
        _info("Overhead", f"{report.overhead_ratio:.1%}")
    except AttributeError:
        pass

    # --- Preview ---
    _show_preview(output, max_words=100)

    # --- Save to file ---
    print("    Would you like to save the full output?")
    save = input("    Save to file? [y/N]: ").strip().lower()
    if save in ("y", "yes"):
        safe_topic = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)
        safe_topic = safe_topic.replace(" ", "_")[:60]
        filename = f"crp_output_{safe_topic}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# {topic}\n\n")
            f.write(f"*Generated with CRP v{crp.__version__} | "
                    f"{words:,} words | {elapsed:.1f}s | "
                    f"Provider: {provider_name}*\n\n---\n\n")
            f.write(output)
        print(f"    Saved to: {filename}")

    # --- Verbose details ---
    if args.verbose:
        _show_session_details(client, report)

    print()


# ═══════════════════════════════════════════════════════════════════════════
# INTERACTIVE MENU
# ═══════════════════════════════════════════════════════════════════════════

def interactive_menu(args: argparse.Namespace) -> None:
    """Show interactive menu when no subcommand is given."""
    print(BANNER.format(version=crp.__version__))
    print("  Select a demo:\n")
    print("    1) compare     -- Direct LLM vs CRP side-by-side comparison")
    print("    2) strategies  -- All 9 dispatch strategies demonstrated")
    print("    3) compliance  -- EU AI Act / GDPR / ISO 42001 compliance")
    print("    4) full        -- Complete showcase (runs 1-3 sequentially)")
    print("    5) generate    -- Generate YOUR content with a REAL LLM")
    print("    q) quit\n")

    choice = input("  Enter choice [1-5, q]: ").strip().lower()
    dispatch = {
        "1": demo_compare, "compare": demo_compare,
        "2": demo_strategies, "strategies": demo_strategies,
        "3": demo_compliance, "compliance": demo_compliance,
        "4": demo_full, "full": demo_full,
        "5": demo_generate, "generate": demo_generate,
    }
    func = dispatch.get(choice)
    if func:
        func(args)
    elif choice not in ("q", "quit", "exit"):
        print("  Invalid choice.")


# ═══════════════════════════════════════════════════════════════════════════
# VERBOSE HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _show_session_details(
    client: crp.CRPOrchestrator, report: object
) -> None:
    """Print detailed session information in verbose mode."""
    _subheader("Session Details (verbose)")
    try:
        status = client.session_status()
        _info("Session ID", status.session_id)
        _info("Windows completed", status.windows_completed)
        _info("Input tokens", f"{status.total_input_tokens:,}")
        _info("Output tokens", f"{status.total_output_tokens:,}")
        _info("Facts in warm state", status.facts_in_warm_state)
        _info("Overhead ratio", f"{status.overhead_ratio:.1%}")
    except Exception:
        pass

    try:
        preview = client.preview_envelope(SYSTEM_PROMPT, "summary")
        _info("Total facts available", preview.facts_available)
        _info("Facts in envelope", preview.facts_included)
        _info("Envelope tokens", f"{preview.envelope_tokens:,}")
        _info("Saturation", f"{preview.saturation:.0%}")
    except Exception:
        pass

    try:
        audit = client.compliance_audit
        valid, _ = audit.verify_chain()
        _info("Audit entries", audit.entry_count)
        _info("Audit chain valid", "Yes" if valid else "TAMPERED")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CRP Demo -- Comprehensive Context Relay Protocol showcase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python demo.py                             # Interactive menu
              python demo.py compare                     # Direct LLM vs CRP
              python demo.py strategies --mock           # All 9 strategies (offline)
              python demo.py compliance --verbose        # Compliance with details
              python demo.py full --provider openai      # Full showcase with OpenAI

            If no API key is detected, --mock mode is used automatically.
            Mock mode demonstrates CRP's architecture without real LLM calls.
        """),
    )
    parser.add_argument(
        "mode", nargs="?", default=None,
        choices=["compare", "strategies", "compliance", "full", "generate"],
        help="Demo mode (default: interactive menu)",
    )
    parser.add_argument(
        "--provider", choices=["openai", "anthropic", "ollama", "lmstudio"],
        help="LLM provider (default: auto-detect from API key)",
    )
    parser.add_argument("--model", help="Model name override")
    parser.add_argument(
        "--mock", action="store_true", default=None,
        help="Use built-in mock provider (no API key needed)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show extraction details and audit trail",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Minimal output",
    )

    args = parser.parse_args()

    # Auto-detect: use mock if no provider and no API key
    if args.mock is None and args.provider is None:
        detected = _detect_provider()
        args.mock = (detected == "mock")

    if not args.mode:
        interactive_menu(args)
    else:
        print(BANNER.format(version=crp.__version__))
        dispatch = {
            "compare": demo_compare,
            "strategies": demo_strategies,
            "compliance": demo_compliance,
            "full": demo_full,
            "generate": demo_generate,
        }
        dispatch[args.mode](args)


if __name__ == "__main__":
    main()
