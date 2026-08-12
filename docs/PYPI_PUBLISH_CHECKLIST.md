# PyPI Publish Checklist — crprotocol 6.0.0

## Pre-publish checks

- [ ] Version bumped in `crp/_version.py` to `6.0.0`.
- [ ] `CHANGELOG.md` updated with v6.0.0 entries.
- [ ] README updated with launch status and agent templates.
- [ ] All modified files pass `ruff check`.
- [ ] Non-live test suite passes: `pytest tests/ -q --tb=short`.
- [ ] Build artifacts generated: `.whl` and `.tar.gz` in `dist/`.

## Build

```bash
python -m hatchling build -t wheel
python -m hatchling build -t sdist
```

Verify the artifacts:

```bash
ls dist/
# expect crprotocol-6.0.0-py3-none-any.whl
# expect crprotocol-6.0.0.tar.gz
```

## Publish

### Option A: twine (recommended)

```bash
pip install twine
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<your-pypi-api-token>
twine upload dist/crprotocol-6.0.0-*
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
python -c "import crp; print(crp.__version__)"  # should print 6.0.0
```

## GitHub release

- [ ] Tag `v6.0.0` and push to origin.
- [ ] Create GitHub release with notes from `CHANGELOG.md`.
- [ ] Attach `dist/*.whl` and `dist/*.tar.gz` to the release.

## What I need from you

Your **PyPI API token** (or permission to use the existing one in the environment).
I can run the build; only you should handle the token.
