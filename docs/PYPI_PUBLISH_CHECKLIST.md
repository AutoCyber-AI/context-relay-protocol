# PyPI Publish Checklist — crprotocol 6.0.1

## Pre-publish checks

- [x] Version bumped in `crp/_version.py` to `6.0.1`.
- [x] `CHANGELOG.md` updated with v6.0.1 entries.
- [x] README updated (auto-detect claims, Output Guarantee disclosure).
- [x] Full non-live test suite passes: 3232 passed, 2 skipped, 1 pre-existing
      environment-flaky failure unrelated to this release (see
      `docs/CRP_SDK_HARDENING_STATUS_2026-08-26.md` §6).
- [x] Build artifacts generated and verified: `.whl` and `.tar.gz` in `dist/`,
      installed into a throwaway venv and confirmed `import crp` +
      `crp.__version__ == "6.0.1"`.
- [ ] `ruff check` — pre-existing, unrelated lint debt remains in
      `crp/providers/openai.py` (see AGENTS.md Quality gates); not
      introduced by this release.

## Build

**Use `python -m build`, not `hatch build` directly** — this release fixed a
real packaging bug (`site-docs/spec`/`site-docs/topics` missing from the
sdist `include` list, which the wheel's `force-include` depends on) that only
surfaces when building the wheel FROM the sdist, which is what `python -m
build` does and `hatch build` (direct from source tree) does not catch.

```bash
python -m build
```

Verify the artifacts:

```bash
dir dist
# expect crprotocol-6.0.1-py3-none-any.whl
# expect crprotocol-6.0.1.tar.gz
```

## Publish

### Option A: twine (recommended)

```bash
pip install twine
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<your-pypi-api-token>
twine upload dist/crprotocol-6.0.1-*
```

### Option B: hatch publish

```bash
export HATCH_INDEX_USER=__token__
export HATCH_INDEX_AUTH=<your-pypi-api-token>
python -m hatch publish
```

## Post-publish verification

```bash
pip install --upgrade crprotocol
python -c "import crp; print(crp.__version__)"  # should print 6.0.1
```

## GitHub release

- [ ] Tag `v6.0.1` and push to origin.
- [ ] Create GitHub release with notes from `CHANGELOG.md`.
- [ ] Attach `dist/*.whl` and `dist/*.tar.gz` to the release.

## What I need from you

Your **PyPI API token** (or permission to use the existing one in the environment).
I can run the build; only you should handle the token.
