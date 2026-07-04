# Publishing PLANTOD to PyPI

`plantod` is a Python package. Its home is **PyPI** (`pip install plantod`), not npm.
The name `plantod` is currently free on PyPI.

## One-time setup

1. Create accounts: [pypi.org](https://pypi.org/account/register/) and
   [test.pypi.org](https://test.pypi.org/account/register/).
2. Create an API token for each (Account settings → API tokens). Scope it to the
   project after the first upload, or "entire account" for the first one.
3. Store tokens in `~/.pypirc`:

   ```ini
   [pypi]
     username = __token__
     password = pypi-AgEI...            # your PyPI token

   [testpypi]
     username = __token__
     password = pypi-AgEN...            # your TestPyPI token
   ```

## Build

```bash
pip install -e ".[dev]"            # gets build + twine
rm -rf dist build src/plantod.egg-info
python -m build                    # -> dist/*.whl and dist/*.tar.gz
twine check dist/*                 # must PASS
```

## Test upload first (recommended)

```bash
twine upload --repository testpypi dist/*
# verify in a clean venv:
python -m venv /tmp/t && /tmp/t/bin/pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ plantod
/tmp/t/bin/plantod --help
```

## Real upload

```bash
twine upload dist/*
```

Then anyone can:

```bash
pip install plantod        # or: pipx install plantod  (isolated global CLI)
plantod login
```

## Releasing a new version

1. Bump `version` in `pyproject.toml` **and** `__version__` in `src/plantod/__init__.py`.
2. Tag: `git tag v0.1.1 && git push --tags`.
3. Rebuild + re-upload (PyPI rejects re-uploading an existing version).

> **Note:** provider CLIs (`claude-code`, `codex`, `opencode`) are runtime tools the
> user installs separately — they are not Python deps and are intentionally not in
> `dependencies`.
