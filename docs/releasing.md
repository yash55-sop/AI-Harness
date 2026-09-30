# Releasing v0.1.0

Distribution: `lightweight-ai-harness`; import package: `harness`.
On October 1, 2026, the public PyPI JSON endpoint returned HTTP 404 for this name.
That indicates no visible project at check time; it does not reserve the name or
guarantee PyPI will accept the first upload. Recheck before release.

## Verify locally

```bash
python -m pip install -e ".[dev,openai]"
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest --cov=harness --cov-branch --cov-report=term-missing
python -m build
python -m twine check --strict dist/*
python scripts/verify_wheel.py
python scripts/check_release.py v0.1.0
```

Build into a directory containing only this release's artifacts. The smoke script
creates a fresh temporary venv, installs the wheel with the OpenAI extra, checks
dependencies, verifies the import comes from site-packages, executes offline Agent
and CodingAgent workflows, and tests both CLI entry points outside the checkout.

## Configure trusted publishing

1. Push this project to the intended GitHub repository and create a `pypi` environment.
2. On PyPI, add a pending trusted publisher for a new project (or a publisher on an
   existing project): project `lightweight-ai-harness`, your actual GitHub owner and
   repository, workflow `publish.yml`, environment `pypi`.
3. For review before public uploads, add a required reviewer to the GitHub environment.
4. Push the tag `v0.1.0` after version values in pyproject.toml and harness.__version__ match.

```bash
git tag v0.1.0
git push origin v0.1.0
```

The workflow reruns the Linux/Windows Python 3.10–3.13 quality matrix against the
release ref, builds artifacts, checks versions and metadata, tests the installed
wheel, and then uploads through PyPI OIDC. No long-lived PyPI token is stored.
The workflow can also be dispatched with an existing tag for retrying a failed
upload; successful version uploads cannot be overwritten.

See [PyPI trusted publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
and [pending publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
The project must be connected to GitHub and the PyPI publisher must be configured
in the release owner's account before this workflow can upload successfully.

## After upload

Verify installation from PyPI in a fresh environment, update the README release
status, and record the released version/date in CHANGELOG.md. Use semantic versions
and keep the tag, project metadata, and import version aligned for later releases.
