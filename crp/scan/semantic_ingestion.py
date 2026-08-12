# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Scan — Semantic Code Ingestion (SPEC-039).

Uses CRP's own Contextual Knowledge Fabric to understand large repositories
with high accuracy and specificity — detecting AI calls hidden behind
wrappers, factory functions, and dependency injection that simple pattern
matching misses.

The codebase is ingested as a knowledge graph where files, functions, calls,
and data flows are facts and graph edges.  CDGR multi-hop retrieval then
traces an AI call from its wrapper definition to every call site.

See SPEC-039 §1–§4 for full specification.

Usage (zero-dependency mode — no tree-sitter required)::

    ingestion = SemanticCodeIngestion()
    graph = ingestion.ingest_repo("/path/to/repo")
    findings = ingestion.find_ai_calls(graph)
    for finding in findings:
        chain = ingestion.trace_through_wrappers(finding, graph)
        governed = ingestion.is_governed(finding)
"""

from __future__ import annotations

import ast
import dataclasses
import logging
import os
import pathlib
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AI client / call patterns (CRP001–CRP005 from SPEC-013)
# ---------------------------------------------------------------------------

#: Known AI provider class / function names whose instantiation or call
#: indicates an AI call site.
_AI_CLIENT_PATTERNS: frozenset[str] = frozenset(
    {
        # OpenAI
        "OpenAI",
        "AsyncOpenAI",
        "AzureOpenAI",
        "AsyncAzureOpenAI",
        # Anthropic
        "Anthropic",
        "AsyncAnthropic",
        # LangChain
        "ChatOpenAI",
        "ChatAnthropic",
        "ChatGoogleGenerativeAI",
        "ChatBedrock",
        "OpenAIEmbeddings",
        "LLMChain",
        # Hugging Face
        "pipeline",
        "AutoModelForCausalLM",
        "transformers.pipeline",
        # Ollama
        "OllamaClient",
        "ollama.chat",
        "ollama.generate",
        # LlamaIndex
        "OpenAI",  # duplicate intentional — in llama_index namespace
    }
)

#: Import paths from known AI provider packages.
_AI_PROVIDER_IMPORTS: frozenset[str] = frozenset(
    {
        "openai",
        "anthropic",
        "langchain",
        "langchain_openai",
        "langchain_anthropic",
        "langchain_community",
        "llama_index",
        "llama_cpp",
        "transformers",
        "ollama",
        "google.generativeai",
        "google.cloud.aiplatform",
        "boto3",  # Bedrock
        "cohere",
        "mistralai",
        "together",
        "groq",
    }
)

#: CRP governance indicator patterns (if present → governed).
_CRP_GOVERNANCE_PATTERNS: frozenset[str] = frozenset(
    {
        "crprotocol",
        "crp.Client",
        "crp.client",
        "gateway.crprotocol.io",
        "CRP-Session-Token",
        "crp_session",
        "CRPOrchestrator",
    }
)


# ---------------------------------------------------------------------------
# Code entity data models
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class CodeFact:
    """A single code entity — a fact in the code knowledge graph (SPEC-039 §2.1)."""

    fact_id: str
    file_path: str
    line: int
    entity_type: str  # "file" | "function" | "class" | "call" | "import" | "return_type"
    name: str
    content: str  # snippet of code for context
    # Optional semantic enrichment
    calls: list[str] = dataclasses.field(default_factory=list)  # function names this calls
    called_by: list[str] = dataclasses.field(default_factory=list)  # callers of this function
    imports: list[str] = dataclasses.field(default_factory=list)  # imports in scope
    return_type: str | None = None
    is_ai_provider_call: bool = False
    is_governed: bool = False
    # Cross-file resolution
    resolved_definition: str | None = None  # fact_id of the definition if this is a call

    @property
    def display(self) -> str:
        """Return the display."""
        return f"{self.file_path}:{self.line} [{self.entity_type}] {self.name}"


@dataclasses.dataclass
class AICallSite:
    """A detected ungoverned (or governed) AI call site."""

    fact_id: str
    file_path: str
    line: int
    call_expression: str  # the code that makes the AI call
    provider: str  # "openai" | "anthropic" | "langchain" | etc.
    is_governed: bool
    governance_evidence: str  # why we say it is/isn't governed
    call_chain: list[str] = dataclasses.field(default_factory=list)  # full call path to root
    wrapper_function: str | None = None  # if wrapped, the wrapping function name
    # CDGR trace result
    traced_sites: list["AICallSite"] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class CodeGraph:
    """Knowledge graph of a codebase (SPEC-039 §2)."""

    repo_path: str
    facts: dict[str, CodeFact] = dataclasses.field(default_factory=dict)
    # Graph edges: fact_id → list of (related_fact_id, edge_type)
    edges: dict[str, list[tuple[str, str]]] = dataclasses.field(default_factory=dict)
    # Index: name → list of fact_ids defining that name
    name_index: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    # AI import facts per file
    ai_imports: dict[str, list[str]] = dataclasses.field(default_factory=dict)

    def add_fact(self, fact: CodeFact) -> None:
        """Add a code fact to the graph and update the name index."""
        self.facts[fact.fact_id] = fact
        if fact.name:
            self.name_index.setdefault(fact.name, []).append(fact.fact_id)

    def add_edge(self, from_id: str, to_id: str, edge_type: str) -> None:
        """Add a directed edge between two facts, plus an inverse edge.

        Args:
            from_id: Source fact ID.
            to_id: Target fact ID.
            edge_type: Relationship type (e.g. ``CALLS``, ``CONTAINS``).
        """
        self.edges.setdefault(from_id, []).append((to_id, edge_type))
        # Bidirectional for traversal
        self.edges.setdefault(to_id, []).append((from_id, f"INV_{edge_type}"))

    def get_neighbours(self, fact_id: str) -> list[tuple[str, str]]:
        """Return all neighbours of *fact_id* as (neighbour_id, edge_type) pairs."""
        return self.edges.get(fact_id, [])

    def lookup_name(self, name: str) -> list[CodeFact]:
        """Return all facts that define the given symbol name."""
        return [self.facts[fid] for fid in self.name_index.get(name, []) if fid in self.facts]

    @property
    def file_count(self) -> int:
        """Return the current file count."""
        return len({f.file_path for f in self.facts.values()})

    @property
    def function_count(self) -> int:
        """Return the current function count."""
        return sum(1 for f in self.facts.values() if f.entity_type == "function")


# ---------------------------------------------------------------------------
# Semantic ingestion engine
# ---------------------------------------------------------------------------


class SemanticCodeIngestion:
    """Ingest a repository into a code-aware knowledge graph.

    Zero external dependency — uses Python's stdlib ``ast`` module for Python
    files.  TypeScript/Go parsing uses regex fallback when tree-sitter is not
    installed.

    Args:
        max_file_size_kb: Skip files larger than this.  Default 512 KB.
        include_extensions: File extensions to parse.  Default Python + TS + Go.
        exclude_dirs: Directory names to skip.
    """

    def __init__(
        self,
        max_file_size_kb: int = 512,
        include_extensions: tuple[str, ...] = (".py", ".ts", ".tsx", ".js", ".go"),
        exclude_dirs: tuple[str, ...] = (
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            "dist",
            "build",
            ".tox",
            ".mypy_cache",
        ),
    ) -> None:
        self.max_file_size_kb = max_file_size_kb
        self.include_extensions = include_extensions
        self.exclude_dirs = frozenset(exclude_dirs)
        self._fact_counter = 0

    # ------------------------------------------------------------------
    # Public API (SPEC-039 §3)
    # ------------------------------------------------------------------

    def ingest_repo(self, repo_path: str) -> CodeGraph:
        """Ingest an entire repository into a CodeGraph.

        Traverses all eligible source files, parses each to extract code
        facts, and builds graph edges for cross-file relationships.

        Args:
            repo_path: Absolute or relative path to the repository root.

        Returns:
            CodeGraph populated with facts and edges.
        """
        path = pathlib.Path(repo_path).resolve()
        if not path.is_dir():
            raise ValueError(f"Repository path not found: {repo_path}")

        graph = CodeGraph(repo_path=str(path))
        logger.info("Semantic ingestion starting: %s", path)

        source_files = self._collect_source_files(path)
        for src_file in source_files:
            try:
                self._ingest_file(src_file, path, graph)
            except Exception as exc:
                logger.warning("Skipped %s: %s", src_file, exc)

        # Second pass: resolve cross-file call targets
        self._resolve_cross_file_calls(graph)

        logger.info(
            "Semantic ingestion complete: files=%d functions=%d facts=%d",
            graph.file_count,
            graph.function_count,
            len(graph.facts),
        )
        return graph

    def find_ai_calls(self, graph: CodeGraph) -> list[AICallSite]:
        """Identify AI call sites in the code graph.

        Finds both:
        - Direct calls: ``OpenAI()``, ``client.chat.completions.create()``, etc.
        - Indirect calls: functions that call AI helpers which are themselves
          wrappers (requires CDGR tracing, step 2 of SPEC-039 §3.2).

        Returns:
            List of AICallSite, each describing one ungoverned or governed AI call.
        """
        sites: list[AICallSite] = []

        for fact_id, fact in graph.facts.items():
            if not fact.is_ai_provider_call:
                continue
            provider = self._classify_provider(fact.name, fact.content, fact.imports)
            governed = self._check_governance(fact, graph)
            site = AICallSite(
                fact_id=fact_id,
                file_path=fact.file_path,
                line=fact.line,
                call_expression=fact.content,
                provider=provider,
                is_governed=governed,
                governance_evidence=(
                    "CRP governance detected" if governed else "No CRP governance found"
                ),
            )
            # Trace through wrappers for this site
            traced = self.trace_through_wrappers(site, graph)
            site.traced_sites = traced
            sites.append(site)

        return sites

    def trace_through_wrappers(
        self, call_site: AICallSite, graph: CodeGraph, max_hops: int = 4
    ) -> list[AICallSite]:
        """CDGR-style multi-hop trace: find all call sites that eventually call this AI call.

        Starting from *call_site* (the direct AI call), walks the CALLS edges
        in reverse (INV_CALLS) to find every function that transitively invokes
        this AI call — even through N layers of wrapping.

        Returns a list of additional AICallSite objects for each discovered
        transitive call site.

        Example (from SPEC-039 §1.2)::

            make_client() → returns OpenAI()     # direct call (already found)
            handle_ticket() → calls make_client() # this function is discovered here
        """
        visited: set[str] = {call_site.fact_id}
        frontier: list[str] = [call_site.fact_id]
        traced_sites: list[AICallSite] = []

        for _ in range(max_hops):
            next_frontier: list[str] = []
            for fid in frontier:
                for neighbour_id, edge_type in graph.get_neighbours(fid):
                    if neighbour_id in visited:
                        continue
                    visited.add(neighbour_id)
                    # INV_CALLS edge = this fact is called by neighbour
                    if edge_type == "INV_CALLS":
                        neighbour = graph.facts.get(neighbour_id)
                        if neighbour and neighbour.entity_type == "function":
                            governed = self._check_governance(neighbour, graph)
                            traced_sites.append(
                                AICallSite(
                                    fact_id=neighbour_id,
                                    file_path=neighbour.file_path,
                                    line=neighbour.line,
                                    call_expression=neighbour.content,
                                    provider=call_site.provider,
                                    is_governed=governed,
                                    governance_evidence=(
                                        "CRP governance detected"
                                        if governed
                                        else "Transitive call — no governance at this level"
                                    ),
                                    wrapper_function=neighbour.name,
                                )
                            )
                            next_frontier.append(neighbour_id)
            frontier = next_frontier
            if not frontier:
                break

        return traced_sites

    def is_governed(self, call_site: AICallSite) -> bool:
        """Return True if *call_site* already has CRP governance applied."""
        return call_site.is_governed

    # ------------------------------------------------------------------
    # Internal: file collection + parsing
    # ------------------------------------------------------------------

    def _collect_source_files(self, root: pathlib.Path) -> list[pathlib.Path]:
        files: list[pathlib.Path] = []
        for entry in root.rglob("*"):
            if any(part in self.exclude_dirs for part in entry.parts):
                continue
            if not entry.is_file():
                continue
            if entry.suffix not in self.include_extensions:
                continue
            size_kb = entry.stat().st_size / 1024
            if size_kb > self.max_file_size_kb:
                logger.debug("Skipping large file: %s (%.0f KB)", entry, size_kb)
                continue
            files.append(entry)
        return sorted(files)

    def _ingest_file(
        self, src_file: pathlib.Path, repo_root: pathlib.Path, graph: CodeGraph
    ) -> None:
        rel_path = str(src_file.relative_to(repo_root))
        source = src_file.read_text(encoding="utf-8", errors="replace")

        if src_file.suffix == ".py":
            self._parse_python(source, rel_path, graph)
        else:
            # TypeScript / Go / JS — regex-based extraction
            self._parse_generic(source, rel_path, src_file.suffix, graph)

    def _parse_python(self, source: str, rel_path: str, graph: CodeGraph) -> None:
        """Parse a Python file using ast, extract facts and edges."""
        try:
            tree = ast.parse(source, filename=rel_path)
        except SyntaxError as exc:
            logger.debug("AST parse error in %s: %s", rel_path, exc)
            return

        file_imports: list[str] = []
        ai_imports: list[str] = []

        # Walk import statements
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in (getattr(node, "names", [])):
                    pkg = getattr(node, "module", None) or alias.name
                    file_imports.append(pkg)
                    if any(pkg.startswith(ai_pkg) for ai_pkg in _AI_PROVIDER_IMPORTS):
                        ai_imports.append(pkg)
                        fact = CodeFact(
                            fact_id=self._next_fact_id(),
                            file_path=rel_path,
                            line=node.lineno,
                            entity_type="import",
                            name=pkg,
                            content=f"import {pkg}",
                            imports=[],
                            is_ai_provider_call=False,
                        )
                        graph.add_fact(fact)

        if ai_imports:
            graph.ai_imports[rel_path] = ai_imports

        # Scan module-level statements for top-level AI client instantiations.
        # e.g. `client = OpenAI(api_key=...)` at module scope — not inside any function.
        file_has_governance = any(g in source for g in _CRP_GOVERNANCE_PATTERNS)
        for stmt in tree.body:
            # Assignment: x = SomeCall(...)
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
                called_name = _extract_call_name(stmt.value)
                if called_name and called_name in _AI_CLIENT_PATTERNS:
                    fact = CodeFact(
                        fact_id=self._next_fact_id(),
                        file_path=rel_path,
                        line=stmt.lineno,
                        entity_type="call",
                        name=called_name,
                        content=f"{called_name}(...) [module-level]",
                        imports=file_imports,
                        is_ai_provider_call=True,
                        is_governed=file_has_governance,
                    )
                    graph.add_fact(fact)
            # Bare expression: SomeCall(...)
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                called_name = _extract_call_name(stmt.value)
                if called_name and called_name in _AI_CLIENT_PATTERNS:
                    fact = CodeFact(
                        fact_id=self._next_fact_id(),
                        file_path=rel_path,
                        line=stmt.lineno,
                        entity_type="call",
                        name=called_name,
                        content=f"{called_name}(...) [module-level]",
                        imports=file_imports,
                        is_ai_provider_call=True,
                        is_governed=file_has_governance,
                    )
                    graph.add_fact(fact)

        # Walk function definitions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_facts = self._extract_python_function(node, rel_path, file_imports, graph, source)
                for ff in func_facts:
                    graph.add_fact(ff)

    def _extract_python_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        rel_path: str,
        file_imports: list[str],
        graph: CodeGraph,
        source: str = "",
    ) -> list[CodeFact]:
        """Extract a function fact and its call facts from an AST FunctionDef."""
        facts: list[CodeFact] = []
        func_id = self._next_fact_id()

        # Snippet: use source segment when available, otherwise construct safe fallback
        snippet: str
        if source:
            seg = ast.get_source_segment(source, node)
            snippet = seg[:200] if seg else f"def {node.name}(...)"
        else:
            snippet = f"def {node.name}(...)"

        calls_made: list[str] = []
        is_ai_call = False
        has_governance = False

        # Scan function body for calls
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                called_name = _extract_call_name(child)
                if called_name:
                    calls_made.append(called_name)
                    if called_name in _AI_CLIENT_PATTERNS:
                        is_ai_call = True
                    if any(g in called_name for g in _CRP_GOVERNANCE_PATTERNS):
                        has_governance = True

            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                if any(g in child.value for g in _CRP_GOVERNANCE_PATTERNS):
                    has_governance = True

        func_fact = CodeFact(
            fact_id=func_id,
            file_path=rel_path,
            line=node.lineno,
            entity_type="function",
            name=node.name,
            content=snippet,
            calls=calls_made,
            imports=file_imports,
            is_ai_provider_call=is_ai_call,
            is_governed=has_governance,
        )
        facts.append(func_fact)

        # Individual AI call-site facts for each AI call within function
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                called_name = _extract_call_name(child)
                if called_name and called_name in _AI_CLIENT_PATTERNS:
                    call_id = self._next_fact_id()
                    call_fact = CodeFact(
                        fact_id=call_id,
                        file_path=rel_path,
                        line=child.lineno if hasattr(child, "lineno") else node.lineno,
                        entity_type="call",
                        name=called_name,
                        content=f"{called_name}(...) in {node.name}",
                        imports=file_imports,
                        is_ai_provider_call=True,
                        is_governed=has_governance,
                    )
                    facts.append(call_fact)
                    # Edge: function CONTAINS call
                    graph.add_edge(func_id, call_id, "CONTAINS")

        return facts

    def _parse_generic(
        self, source: str, rel_path: str, ext: str, graph: CodeGraph
    ) -> None:
        """Regex-based fallback parser for TypeScript, Go, JS."""
        lines = source.splitlines()
        ai_import_pattern = re.compile(
            r"""(import|require|from)\s+['"]?(\w[\w./]*openai[\w./]*|[\w./]*anthropic[\w./]*)"""
        )
        fn_pattern = re.compile(r"""(?:function|const|def)\s+(\w+)\s*[\(=]""")
        call_pattern = re.compile(
            r"""\b(""" + "|".join(re.escape(p) for p in _AI_CLIENT_PATTERNS) + r""")\s*[.(]"""
        )

        has_ai_imports = any(
            ai_import_pattern.search(line) for line in lines
        )

        if has_ai_imports:
            graph.ai_imports.setdefault(rel_path, []).append(ext)

        for lineno, line in enumerate(lines, start=1):
            fn_match = fn_pattern.search(line)
            call_match = call_pattern.search(line)

            if call_match:
                is_governed = any(g in source for g in _CRP_GOVERNANCE_PATTERNS)
                fact = CodeFact(
                    fact_id=self._next_fact_id(),
                    file_path=rel_path,
                    line=lineno,
                    entity_type="call",
                    name=call_match.group(1),
                    content=line.strip()[:120],
                    is_ai_provider_call=True,
                    is_governed=is_governed,
                )
                graph.add_fact(fact)

    def _resolve_cross_file_calls(self, graph: CodeGraph) -> None:
        """Second pass: wire CALLS edges between functions across files.

        For each function fact, check if any of its ``calls`` names are defined
        elsewhere in the graph, and add a directed CALLS edge.
        """
        for fact_id, fact in list(graph.facts.items()):
            if fact.entity_type != "function" or not fact.calls:
                continue
            for called_name in fact.calls:
                target_facts = graph.lookup_name(called_name)
                for target in target_facts:
                    if target.fact_id != fact_id:
                        graph.add_edge(fact_id, target.fact_id, "CALLS")

    # ------------------------------------------------------------------
    # Internal: governance + provider classification
    # ------------------------------------------------------------------

    def _check_governance(self, fact: CodeFact, graph: CodeGraph) -> bool:
        """Check if a fact is under CRP governance."""
        if fact.is_governed:
            return True
        # Check if any import in the same file is a CRP governance import
        for imp in fact.imports:
            if any(g in imp for g in _CRP_GOVERNANCE_PATTERNS):
                return True
        return False

    def _classify_provider(
        self, name: str, content: str, imports: list[str]
    ) -> str:
        """Classify which AI provider a call site belongs to."""
        combined = f"{name} {content} {' '.join(imports)}".lower()
        if "openai" in combined or "gpt" in combined:
            return "openai"
        if "anthropic" in combined or "claude" in combined:
            return "anthropic"
        if "langchain" in combined:
            return "langchain"
        if "llama" in combined or "ollama" in combined:
            return "local"
        if "transformers" in combined or "huggingface" in combined:
            return "huggingface"
        if "gemini" in combined or "google" in combined:
            return "gemini"
        return "unknown"

    def _next_fact_id(self) -> str:
        self._fact_counter += 1
        return f"code_fact_{self._fact_counter:06d}"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _extract_call_name(node: ast.Call) -> str | None:
    """Extract a simple name from an ast.Call node."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        # e.g. client.chat.completions.create → "create" is the method
        # We want the top-level attribute chain to detect known SDK calls.
        parts: list[str] = []
        obj: Any = func
        while isinstance(obj, ast.Attribute):
            parts.append(obj.attr)
            obj = obj.value
        if isinstance(obj, ast.Name):
            parts.append(obj.id)
        parts.reverse()
        # Return the last component that matches known patterns
        for part in reversed(parts):
            if part in _AI_CLIENT_PATTERNS:
                return part
        # Return last two components as "obj.method" form
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return parts[0] if parts else None
    return None
