---
seo_title: CRP Testing & Benchmarks — Reproduce Results
description: How to run the CRP test suite and reproduce benchmark results for context management, safety, and quality.
---

# Testing & Benchmarks

> CRP ships with a comprehensive test suite covering every SDK level, protocol
> feature, and product surface - from smoke tests to live LLM verification - so
> regressions are caught before they reach users.

CRP has **60+ test files** and **1,537+ tests** covering every module from smoke
tests to live LLM verification.

## Overview

| Category | Files | What It Covers |
|----------|-------|---------------|
| [Smoke](running-tests.md#smoke-tests) | 1 | Package imports, version, basic types |
| [Unit - Core phases](running-tests.md#unit-tests-core-phases) | 9 | All 9 SDK phases |
| [Unit - Specialized](running-tests.md#unit-tests-specialized) | 14+ | Deep module-level coverage |
| [Integration](running-tests.md#integration-tests) | 1 | Cross-module E2E |
| [Production hardening](running-tests.md#production-hardening) | 1 | Circuit breakers, retries, cleanup |
| [Benchmarks](running-tests.md#performance-benchmarks) | 1 | Performance regression |
| [Live LLM](running-tests.md#live-tests) | 4+ | Real model verification |
| [v5 features](running-tests.md#v5-feature-tests) | 12+ | Safety surface, STL, horizons, scratch buffer, CSO, SDK levels, Gateway, Comply, Scan |

## Quick Start

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run smoke tests (fast, ~2 seconds)
python -m pytest tests/test_smoke.py -v

# Run a specific phase
python -m pytest tests/test_phase1.py -v --tb=short

# Run with coverage
python -m pytest tests/test_smoke.py --cov=crp --cov-report=term
```

!!! warning "Do NOT run all tests at once"
    The full suite is resource-intensive. Run one file at a time to avoid
    maxing out system resources. See [Running Tests](running-tests.md) for
    guidance on `pytest-timeout` and safe execution.

## Sections

- **[Running Tests](running-tests.md)** - How to run each test category, what
  each file covers, fixtures, and tips
- **[Benchmarks](benchmarks.md)** - Performance results: continuation engine,
  extraction pipeline, protocol overhead
- **[Reproduce Benchmarks](reproduce.md)** - Step-by-step guide to reproduce
  our benchmark results on your own hardware
