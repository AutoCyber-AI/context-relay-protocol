<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# CRP Governance

## Overview

The Context Relay Protocol (CRP) follows an open governance model inspired by the Apache Software Foundation. This document defines the roles, responsibilities, and decision-making processes for the project.

## Roles

### Maintainers

Maintainers have merge authority over the specification repository. They are responsible for:

- Reviewing and merging pull requests
- Accepting or rejecting RFCs
- Releasing new specification versions
- Enforcing the Code of Conduct
- Setting project direction

**Current Maintainers**:
- Constantinos Vidiniotis (@Constantinos-uni) — Project Creator

### Committers

Committers have review authority. They can approve PRs but cannot merge without maintainer approval. Committers are recognized contributors who have demonstrated:

- Deep understanding of the specification
- Consistent, high-quality contributions
- Constructive participation in discussions

Committers are nominated by maintainers and approved by consensus.

### Contributors

Anyone who submits a pull request, opens an issue, participates in discussions, or contributes to the ecosystem (SDKs, adapters, blog posts, talks) is a contributor.

## Decision-Making

### Lazy Consensus (Minor Changes)

For minor changes (typos, clarifications, non-breaking additions), lazy consensus applies: if no maintainer objects within 72 hours, the change is accepted.

### Formal Review (Specification Changes)

For non-trivial specification changes:

1. Submit an RFC per the [Contributing Guide](CONTRIBUTING.md)
2. Minimum 14-day discussion period
3. At least two maintainer approvals required
4. Changes to MUST/MUST NOT requirements need unanimous maintainer approval

### Formal Vote (Breaking Changes)

For breaking changes (major version bumps, removal of features, changes to Stable APIs):

1. RFC required with 30-day discussion period
2. Unanimous maintainer approval
3. 6-month deprecation notice for removed features (per §6.10.7)

## Specification Versioning

CRP uses semantic versioning (Major.Minor.Patch):

- **Major** (e.g., 2.0 → 3.0): Breaking changes to Stable APIs
- **Minor** (e.g., 2.0 → 2.1): New features, Provisional API changes
- **Patch** (e.g., 2.0.0 → 2.0.1): Bug fixes only

Each release is tagged in the repository and documented in [CHANGELOG.md](CHANGELOG.md).

## Conflict Resolution

1. Discussion on the issue/PR
2. If unresolved: maintainer call (synchronous meeting)
3. If still unresolved: project creator (Constantinos Vidiniotis) has final decision authority

## Reserved Rights of the Project Creator

The Project Creator (Constantinos Vidiniotis) retains the following permanent, non-transferable, and irrevocable rights regardless of the number of maintainers, committers, or contributors:

1. **Permanent merge authority** — The Project Creator may merge or reject any pull request at any time, overriding any other maintainer decision
2. **Veto power** — The Project Creator may veto any specification change, governance change, license change, or project direction decision. This veto is absolute and not subject to override
3. **License authority** — Only the Project Creator may modify, change, or relicense the project's code or specification. No maintainer vote, RFC, or community decision can alter the licensing terms without the Project Creator's explicit written consent
4. **Governance authority** — Only the Project Creator may modify this Reserved Rights section. This clause is immutable by any other process defined in this document
5. **Commercial authority** — All commercial licensing decisions, partnership agreements, and revenue-generating activities related to CRP are the exclusive authority of the Project Creator and AutoCyber AI

These rights exist to protect the long-term integrity of the protocol and ensure that no external entity can capture, relicense, or redirect the project against the creator's intent.

## Amendments

This governance document may be amended by unanimous maintainer approval with a 14-day discussion period. **Exception**: The "Reserved Rights of the Project Creator" section above may only be amended by the Project Creator (Constantinos Vidiniotis) and is not subject to the standard amendment process.
