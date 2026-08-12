---
seo_title: "Contribute to CRP — Protocol, SDK, Docs & Standards"
description: "How to contribute to the Context Relay Protocol: code, documentation, specifications, and standards feedback."
---

# Contributing

Thank you for your interest in contributing to CRP.

## Getting Started

1. **Fork** the repository
2. **Branch** from `main`
3. Make your changes
4. Update `CHANGELOG.md`
5. Submit a **Pull Request**

## Development Setup

```bash
git clone https://github.com/AutoCyber-AI/context-relay-protocol.git
cd context-relay-protocol
pip install -e ".[dev]"
```

## Pull Request Requirements

- Branch from `main`
- Update `CHANGELOG.md` with your changes
- **1 maintainer approval** required (2 for specification changes)
- All existing tests must pass

## RFC Process

Breaking changes or specification modifications require an RFC:

1. Create an RFC document in `rfcs/`
2. **14-day discussion period**
3. **Unanimous maintainer approval** required
4. Implementation follows after RFC acceptance

## Issue Templates

| Template | Use For |
|----------|---------|
| **Spec Clarification** | Ambiguous specification language |
| **Feature Request** | New capabilities or improvements |
| **Bug Report** | Implementation bugs or test failures |

## Commit Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add streaming event for extraction progress
fix: correct envelope saturation calculation
docs: update quickstart guide
rfc: propose new dispatch strategy
```

| Prefix | Use For |
|--------|---------|
| `feat:` | New features |
| `fix:` | Bug fixes |
| `docs:` | Documentation changes |
| `rfc:` | RFC proposals |
| `test:` | Test additions or fixes |
| `refactor:` | Code restructuring |

## Style Guide

- Use **RFC 2119** language for specification text (MUST, SHOULD, MAY)
- JSON Schemas follow **Draft 2020-12**
- Python code follows the project's existing style

## Updating Documentation

Documentation lives in `site-docs/` and is published with MkDocs Material. Before
editing pages:

- Review the site-publishing instructions in [`AGENTS.md`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/AGENTS.md#site-documentation--publishing),
  including the local build command and the list of pages that must stay in sync
  with SDK changes.
- Use relative `.md` links for internal cross-references.
- Run `.venv/Scripts/python -m mkdocs build --strict` locally and fix any warnings
  before pushing.
- Do **not** run `mkdocs gh-deploy` locally; deployment is handled automatically
  by GitHub Actions.

## License

- **Specification**: CC BY-SA 4.0
- **Code**: Elastic License 2.0 (ELv2)

By contributing, you grant an irrevocable license under these terms.
See [LICENSE.md](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/LICENSE.md)
for details.

## Code of Conduct

This project follows a Code of Conduct. See
[CODE_OF_CONDUCT.md](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/CODE_OF_CONDUCT.md).

## Security

Report security vulnerabilities via email or GitHub Security Advisories -
**not** via public issues. See [Security](compliance/security.md) for details.
