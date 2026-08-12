# Public Repository Protection Guide

When `AutoCyber-AI/context-relay-protocol` is made public for the launch campaign,
configure these GitHub settings to prevent unwanted changes while still allowing
read access and forks.

## What GitHub public repos allow and do not allow

- **Allowed:** anyone can read, fork, and open pull requests.
- **Not allowed on standard public repos:** disabling forks entirely.
- **What we can enforce:** who may merge to `main`, required reviews,
  signed commits, status checks, and branch protection.

## Required branch protection for `main`

In **Settings → Branches → Add rule** (or edit the existing rule):

1. Branch name pattern: `main`
2. ☑ **Require a pull request before merging**
   - ☑ **Require approvals: 1** (set to the repo owner / approved maintainers)
   - ☑ **Dismiss stale PR approvals when new commits are pushed**
   - ☑ **Require review from CODEOWNERS**
3. ☑ **Require status checks to pass before merging**
   - Add: `lint-and-test` and `build-docker` from the CI workflow.
4. ☑ **Require signed commits**
5. ☑ **Include administrators** (no one pushes directly to `main`)
6. ☑ **Allow force pushes:** Off
7. ☑ **Allow deletions:** Off

## CODEOWNERS

Create / update `.github/CODEOWNERS`:

```text
* @AutoCyber-AI/crp-maintainers
```

Only CODEOWNERS members can approve merges.

## Optional: reduce noise

- **Settings → General → Issues:** disable if you do not want public issues.
- **Settings → General → Discussions:** disable.
- **Settings → General → Wiki:** disable.
- **Settings → General → Projects:** disable.

## Contributor access

Refer to `CONTRIBUTING.md`. All contributors must contact the maintainers
and receive explicit approval before a pull request is accepted.
