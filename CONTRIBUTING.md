# Development and verification

Read [AGENTS.md](AGENTS.md), [CODEX_TASK.md](CODEX_TASK.md) and their referenced
documents before changes. Python **3.14** and Home Assistant **2026.10+** are
required. Never use real panel commands in tests or development. The reference
repository is read-only; only its `ecoflow/` scripts are authoritative.

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/ruff check custom_components tests scripts
.venv/bin/ruff format --check custom_components tests scripts
.venv/bin/python scripts/sync_catalog.py --check
.venv/bin/python -m compileall -q custom_components
.venv/bin/pytest -q --disable-socket --allow-unix-socket --tb=short --show-capture=no --timeout=30 --cov=custom_components.ecoflow_smart_home_panel_v1 --cov-report=term-missing
git diff --check
```

Tests use synthetic credentials and data. Internet sockets are blocked; Unix
sockets are permitted for HA internals. The test-only reference script is never
executed as a script: selected functions run against injected memory-only I/O.

## Official HACS distribution tests

Download the pinned upstream source once; it is not installed into HA:

```sh
git init /tmp/ecoflow-hacs-validation
git -C /tmp/ecoflow-hacs-validation fetch --depth=1 https://github.com/hacs/integration.git a15e87ec0d1c82e58f1ddbaf17669d3eaa261eb8
git -C /tmp/ecoflow-hacs-validation checkout --detach FETCH_HEAD
ECOFLOW_HACS_SOURCE=/tmp/ecoflow-hacs-validation .venv/bin/pytest -q tests/test_hacs_install.py --disable-socket --allow-unix-socket --timeout=30
```

These three tests execute actual HACS validators and installation code. Only
remote metadata/download responses are substituted. Nine active official checks
include local branding; `topics` remains optional default-catalog metadata.
The public metadata snapshot was read from GitHub on 2026-10-25. Set
`ECOFLOW_HACS_METADATA` to a fresh public GitHub repository response JSON to
validate changed metadata; CI fetches it before blocking test network access.

Clean install and upgrade from commit
`88ee6e4c094b4d10387a14e0d9fde15f221ceeb7` (0.3.2) extract into disposable paths,
verify every installed byte, retain unrelated storage and run HA onboarding,
options, registry preservation, reload and removal in a separate Python process.
The baseline must exist in Git; CI checks out full history. Without
`ECOFLOW_HACS_SOURCE`, these three tests are skipped. Set it for the complete
suite to include distribution verification in coverage.

## hassfest and DEV checks

```sh
docker run --rm --network none -v "$PWD:/github/workspace:ro" ghcr.io/home-assistant/hassfest:latest
docker compose -f .devcontainer/ha.compose.yml config -q
bash -n scripts/dev-ha.sh scripts/recreate.sh
```

Use the [isolated DEV setup](docs/LOCAL_LIVE_TEST.md) for UI/data inspection.
GitHub workflows are **manual-only** to avoid repeated notification emails.
No workflow publishes or deploys a release. Update README, changelog and
[milestone evidence](docs/MILESTONES.md) with exact commands/results.
[Release and owner acceptance](docs/RELEASE.md) remain explicit.
