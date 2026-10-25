"""Run the pinned official HACS validator/installer without GitHub or device I/O.

Set ECOFLOW_HACS_SOURCE to a checkout of HACS_REVISION. Network responses are
replaced with this repository's files and public metadata; installation, archive
extraction, upgrade backup/cleanup and validators execute actual upstream code.
"""

import asyncio
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.ecoflow_smart_home_panel_v1.const import DOMAIN

ROOT = Path(__file__).resolve().parents[1]
HACS_REVISION = "a15e87ec0d1c82e58f1ddbaf17669d3eaa261eb8"
UPGRADE_FROM = "88ee6e4c094b4d10387a14e0d9fde15f221ceeb7"
REPOSITORY = "nickwinger/ecoflow_smart_home_panel_v1"
REMOTE = f"custom_components/{DOMAIN}"


def package_files():
    """Only distributable runtime assets, no local bytecode or reference documents."""
    return {
        path.relative_to(ROOT).as_posix(): path.read_bytes()
        for path in (ROOT / REMOTE).rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".json", ".yaml", ".png"}
        and "__pycache__" not in path.parts
    } | {name: (ROOT / name).read_bytes() for name in ("README.md", "hacs.json", "LICENSE")}


def archive(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as output:
        for name, data in files.items():
            output.writestr(f"package/{name}", data)
    return buffer.getvalue()


@pytest.fixture
def hacs_repository(hass, tmp_path, monkeypatch):
    source = os.environ.get("ECOFLOW_HACS_SOURCE")
    if not source:
        pytest.skip("Set ECOFLOW_HACS_SOURCE to run official HACS distribution checks")
    revision = subprocess.check_output(
        ["git", "-C", source, "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == HACS_REVISION
    import custom_components

    monkeypatch.setattr(
        custom_components, "__path__", [*custom_components.__path__, f"{source}/custom_components"]
    )
    from aiogithubapi.objects.repository.content import AIOGitHubAPIRepositoryTreeContent
    from custom_components.hacs.base import HacsBase
    from custom_components.hacs.repositories.base import HacsManifest
    from custom_components.hacs.repositories.integration import HacsIntegrationRepository

    hacs = HacsBase()
    hacs.hass = hass
    hacs.core.config_path = str(tmp_path / "ha-config")
    hacs.system.action = True
    repo = HacsIntegrationRepository(hacs, REPOSITORY)
    metadata_path = Path(
        os.environ.get("ECOFLOW_HACS_METADATA", ROOT / "tests/fixtures/hacs_repository.json")
    )
    metadata = json.loads(metadata_path.read_text())
    repo.repository_object = SimpleNamespace(attributes=metadata)
    repo.data.update_data(metadata, action=True)
    repo.ref = "main"
    files = package_files()
    paths = set(files)
    for name in files:
        paths.update(str(parent) for parent in Path(name).parents if str(parent) != ".")
    repo.tree = [
        AIOGitHubAPIRepositoryTreeContent(
            {"path": name, "type": "blob" if name in files else "tree"}, REPOSITORY, "main"
        )
        for name in sorted(paths)
    ]
    repo.treefiles = [item.full_path for item in repo.tree]
    repo.integration_manifest = json.loads(files[f"{REMOTE}/manifest.json"])
    repo.repository_manifest = HacsManifest.from_dict(json.loads(files["hacs.json"]))
    repo.async_get_integration_manifest = AsyncMock(return_value=repo.integration_manifest)
    repo.common_validate = AsyncMock()
    repo.update_repository = AsyncMock()
    repo.get_hacs_json_raw = AsyncMock(return_value=json.loads(files["hacs.json"]))
    hacs.async_download_file = AsyncMock(return_value=archive(files))
    monkeypatch.setenv("INPUT_REPOSITORY", REPOSITORY)
    # Topics are default-catalog metadata, not required for a custom repository.
    monkeypatch.setenv("INPUT_IGNORE", "topics")
    return repo


async def test_official_hacs_validation(hacs_repository):
    from custom_components.hacs.validate.manager import ValidationManager

    repo = hacs_repository
    assert await repo.validate_repository()
    assert repo.content.path.remote == REMOTE
    assert repo.data.domain == DOMAIN
    manager = ValidationManager(repo.hacs, repo.hacs.hass)
    await manager.async_run_repository_checks(repo)
    active = [
        v
        for v in manager.validators
        if v.slug != "topics" and (not v.categories or repo.data.category in v.categories)
    ]
    assert len(active) == 9
    assert all(not validator.failed for validator in active)


@pytest.mark.parametrize("upgrade", [False, True])
async def test_actual_hacs_install_and_isolated_ha_load(hacs_repository, tmp_path, upgrade):
    repo = hacs_repository
    assert await repo.validate_repository()
    installed = Path(repo.content.path.local)
    config = Path(repo.hacs.core.config_path)
    await asyncio.to_thread(config.mkdir, parents=True)
    storage = config / ".storage"
    storage.mkdir()
    marker = storage / "existing_user_data"
    marker.write_text("existing configuration and history must not be touched")
    if upgrade:
        previous = await asyncio.to_thread(
            subprocess.check_output,
            ["git", "archive", "--format=zip", "--prefix=package/", UPGRADE_FROM, REMOTE],
            cwd=ROOT,
        )
        repo.hacs.async_download_file.return_value = previous
        await repo.async_install_repository(version="main")
        assert json.loads((installed / "manifest.json").read_text())["version"] == "0.3.2"
        (installed / "obsolete.py").write_text("# HACS must replace the old integration directory")
    files = package_files()
    repo.hacs.async_download_file.return_value = archive(files)
    await repo.async_install_repository(version="main")
    expected = {
        name.removeprefix(REMOTE + "/"): data
        for name, data in files.items()
        if name.startswith(REMOTE + "/")
    }

    def installed_files():
        return {
            p.relative_to(installed).as_posix(): p.read_bytes()
            for p in installed.rglob("*")
            if p.is_file()
        }

    actual = await asyncio.to_thread(installed_files)
    assert actual == expected
    assert marker.read_text() == "existing configuration and history must not be touched"
    assert not (installed / "tests").exists()
    assert not (installed / "docs").exists()
    assert repo.data.installed
    # A separate Python process can only import the installed distribution. It
    # cannot accidentally pass by importing source modules cached by this suite.
    (config / "test_installed.py").write_bytes(
        (ROOT / "tests/installed_package_smoke.py").read_bytes()
    )
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment["ECOFLOW_INSTALL_UPGRADE"] = "1" if upgrade else "0"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "test_installed.py",
        "--disable-socket",
        "--allow-unix-socket",
        "--timeout=20",
        "-o",
        "asyncio_mode=auto",
        "-o",
        "asyncio_default_fixture_loop_scope=function",
        cwd=config,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    assert process.returncode == 0, output.decode()
