#!/usr/bin/env bash
# Fresh, isolated Home Assistant DEV install. Do not run inside the VS Code
# Python Dev Container: the Docker CLI belongs to the WSL/Linux host.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'HELP'
EcoFlow SHP v1 — recreate isolated Home Assistant DEV

  bash scripts/recreate.sh                 Fresh HA DEV install and open the browser
  bash scripts/recreate.sh --no-browser    Fresh HA DEV install without opening a browser
  bash scripts/recreate.sh --help          Show this help

WARNING: This erases the DEV Home Assistant data volume:
  ecoflow-shp-v1-live-test_ha_config

It removes the DEV login, EcoFlow credentials, entity/device registries,
Recorder database and history, then starts a clean HA DEV instance and
provisions test/test. It does NOT delete source code, the VS Code development
workspace, or any production Home Assistant configuration.
HELP
}

case "${1:-}" in
    --help|-h)
        [[ "$#" -eq 1 ]] || { usage >&2; exit 2; }
        usage
        exit 0
        ;;
    ""|--no-browser)
        [[ "$#" -le 1 ]] || { usage >&2; exit 2; }
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

echo "Recreating ONLY the isolated EcoFlow Home Assistant DEV instance..."
exec bash "$SCRIPT_DIR/dev-ha.sh" reset "$@"
