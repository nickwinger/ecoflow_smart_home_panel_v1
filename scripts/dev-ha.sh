#!/usr/bin/env bash
# Disposable Home Assistant for EcoFlow SHP v1 development.
# This file must be run on the WSL/Linux HOST, not inside the Python Dev Container.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/.devcontainer/ha.compose.yml"
BOOTSTRAP="$ROOT/scripts/dev_ha_bootstrap.py"
URL="http://localhost:8124/config/integrations/add?domain=ecoflow_smart_home_panel_v1"
PROJECT="ecoflow-shp-v1-live-test"

usage() {
    cat <<'HELP'
EcoFlow SHP v1 — isolated Home Assistant DEV workflow

  bash scripts/dev-ha.sh start [--no-browser]   Start HA, create test/test if new, open integration
  bash scripts/dev-ha.sh open                   Open integration page in browser
  bash scripts/dev-ha.sh restart                Restart only DEV HA (code reload)
  bash scripts/dev-ha.sh status                 Show DEV container status
  bash scripts/dev-ha.sh logs                   Follow DEV HA logs
  bash scripts/dev-ha.sh stop                   Stop DEV HA, KEEP users/entities/history
  bash scripts/dev-ha.sh reset                  DELETE ONLY DEV HA volume and start fresh
  bash scripts/dev-ha.sh clean                  DELETE ONLY DEV HA volume; do not restart
  bash scripts/dev-ha.sh test                   Run isolated offline pytest suite
  bash scripts/dev-ha.sh help                   Show this help

Run from WSL HOST for Docker operations. Tests can run inside VS Code Dev Container.
DEV UI: http://localhost:8124 ; local login: test / test (new volume only).
Existing DEV users are never changed on re-run. No production HA mounts or API use.
HELP
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

preflight() {
    command -v docker >/dev/null 2>&1 || die "Docker CLI not found; enable Docker Desktop WSL integration."
    command -v python3 >/dev/null 2>&1 || die "Python 3 is needed on the WSL host."
    docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required."
    docker info >/dev/null 2>&1 || die "Docker daemon is unavailable. Start Docker Desktop first."
    grep -qx "name: $PROJECT" "$COMPOSE_FILE" || die "Unexpected Docker Compose project name; refusing operation."
    grep -q '127.0.0.1:8124:8123' "$COMPOSE_FILE" || die "DEV port is not loopback-bound; refusing operation."
    docker compose -p "$PROJECT" -f "$COMPOSE_FILE" config -q || die "Invalid Docker Compose file."
}

compose() {
    docker compose -p "$PROJECT" -f "$COMPOSE_FILE" "$@"
}

open_browser() {
    echo "EcoFlow integration: $URL"
    if command -v wslview >/dev/null 2>&1 && wslview "$URL" >/dev/null 2>&1; then
        return
    fi
    if command -v powershell.exe >/dev/null 2>&1 &&
        powershell.exe -NoProfile -NonInteractive -Command "Start-Process '$URL'" >/dev/null 2>&1; then
        return
    fi
    if command -v xdg-open >/dev/null 2>&1 && xdg-open "$URL" >/dev/null 2>&1; then
        return
    fi
    echo "Could not open a browser automatically. Open the URL above manually."
}

start() {
    preflight
    echo "Starting isolated EcoFlow DEV Home Assistant (not production)..."
    compose up -d --remove-orphans
    python3 "$BOOTSTRAP"
    echo
    echo "DEV Home Assistant is ready at http://localhost:8124"
    echo "DEV login: test / test (fresh test volume; local-only; never use in production)"
    echo "Add EcoFlow credentials once in the DEV integration dialog; they persist until reset."
    if [ "$OPEN_BROWSER" = "yes" ]; then
        open_browser
    fi
}

delete_dev_volume() {
    preflight
    echo "Removing ONLY the '$PROJECT' Docker Compose project and its own DEV volume."
    echo "This erases the DEV account, EcoFlow DEV credentials, entity registry and Recorder history."
    echo "Your production Home Assistant and Git working tree are not mounted."
    compose down --volumes --remove-orphans
}

OPEN_BROWSER="yes"
if [ "$#" -gt 0 ]; then
    COMMAND="$1"
    shift
else
    COMMAND="start"
fi

case "$COMMAND" in
    start|reset)
        if [ "$#" -gt 0 ]; then
            if [ "$1" = "--no-browser" ] && [ "$#" -eq 1 ]; then
                OPEN_BROWSER="no"
            else
                usage
                exit 2
            fi
        fi
        if [ "$COMMAND" = "reset" ]; then
            delete_dev_volume
        fi
        start
        ;;
    restart)
        [ "$#" -eq 0 ] || die "Unexpected arguments."
        preflight
        compose restart homeassistant
        python3 "$BOOTSTRAP"
        echo "DEV Home Assistant restarted; integration source reloaded."
        ;;
    open)
        [ "$#" -eq 0 ] || die "Unexpected arguments."
        open_browser
        ;;
    status)
        [ "$#" -eq 0 ] || die "Unexpected arguments."
        preflight
        compose ps
        ;;
    logs)
        [ "$#" -eq 0 ] || die "Unexpected arguments."
        preflight
        compose logs --tail 150 -f homeassistant
        ;;
    stop)
        [ "$#" -eq 0 ] || die "Unexpected arguments."
        preflight
        compose down --remove-orphans
        echo "DEV stopped, test volume retained."
        ;;
    clean)
        [ "$#" -eq 0 ] || die "Unexpected arguments."
        delete_dev_volume
        echo "DEV removed. Next start recreates a clean DEV account and registry."
        ;;
    test)
        [ "$#" -eq 0 ] || die "Unexpected arguments."
        cd "$ROOT"
        python -m pytest -q --timeout=30
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        usage
        exit 2
        ;;
esac
