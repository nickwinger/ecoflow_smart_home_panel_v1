"""Offline checks for the developer script index and fresh-install alias."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_recreate_is_bash_wrapper_and_has_documented_help() -> None:
    script = ROOT / "scripts/recreate.sh"
    content = script.read_text()
    assert 'exec bash "$SCRIPT_DIR/dev-ha.sh" reset "$@"' in content
    assert "docker compose down -v" not in content
    syntax = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert syntax.returncode == 0, syntax.stderr
    help_result = subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True)
    assert help_result.returncode == 0, help_result.stderr
    assert "ecoflow-shp-v1-live-test_ha_config" in help_result.stdout


def test_scripts_md_lists_every_project_script() -> None:
    contents = (ROOT / "scripts.md").read_text()
    for script in (ROOT / "scripts").glob("*.sh"):
        assert f"scripts/{script.name}" in contents
    for script in (ROOT / "scripts").glob("*.py"):
        assert f"scripts/{script.name}" in contents
    assert "Fresh Install" in contents
