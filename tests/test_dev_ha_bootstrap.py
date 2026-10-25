"""Offline tests for the localhost-only Home Assistant DEV bootstrap.

No Docker, sockets, EcoFlow cloud calls or live Home Assistant credentials.
"""

import subprocess
from pathlib import Path

import pytest

from scripts.dev_ha_bootstrap import (
    ALL_STEPS,
    BASE_URL,
    DEV_PASSWORD,
    DEV_USERNAME,
    APIStatusError,
    BootstrapError,
    Client,
    bootstrap,
)

ROOT = Path(__file__).resolve().parent.parent


class FakeHomeAssistant:
    """Simulate the 2026.10.3 onboarding endpoints without network access."""

    def __init__(self, completed=()):
        self.done = set(completed)
        self.calls = []
        self.owner_creations = 0

    def steps_done(self):
        return set(self.done)

    def call(self, path, *, data=None, bearer=None, form=False):
        self.calls.append((path, data, bearer, form))
        if path == "/api/onboarding/users":
            assert "user" not in self.done
            assert data["username"] == DEV_USERNAME
            assert data["password"] == DEV_PASSWORD
            assert data["language"] == "de"
            self.owner_creations += 1
            self.done.add("user")
            return {"auth_code": "test-one-time-code"}
        if path == "/auth/login_flow":
            assert "user" in self.done
            assert data["handler"] == ["homeassistant", None]
            return {"flow_id": "fake-login-flow"}
        if path == "/auth/login_flow/fake-login-flow":
            assert data["username"] == DEV_USERNAME
            assert data["password"] == DEV_PASSWORD
            return {"type": "create_entry", "result": "test-login-code"}
        if path == "/auth/token":
            assert form
            assert data["grant_type"] == "authorization_code"
            assert data["code"] in ("test-one-time-code", "test-login-code")
            return {"access_token": "ephemeral-test-access-token"}
        if path.startswith("/api/onboarding/"):
            assert bearer == "ephemeral-test-access-token"
            step = path.removeprefix("/api/onboarding/")
            assert step in ALL_STEPS
            assert step not in self.done
            if step == "integration":
                assert data["redirect_uri"].startswith("http://localhost:8124/")
            self.done.add(step)
            return {}
        raise AssertionError(f"Unexpected path: {path}")


def test_fresh_bootstrap_creates_local_owner_and_completes_onboarding(capsys):
    client = FakeHomeAssistant()
    bootstrap(client, timeout=1)
    assert client.done == ALL_STEPS
    assert client.owner_creations == 1
    output = capsys.readouterr().out
    assert "test / test" in output
    assert "test-one-time-code" not in output
    assert "ephemeral-test-access-token" not in output


def test_repeated_bootstrap_preserves_existing_owner_and_registry():
    client = FakeHomeAssistant(ALL_STEPS)
    bootstrap(client, timeout=1)
    assert client.done == ALL_STEPS
    assert client.owner_creations == 0
    assert client.calls == []


def test_partial_bootstrap_uses_existing_dev_login_without_recreating_user():
    client = FakeHomeAssistant({"user", "core_config"})
    bootstrap(client, timeout=1)
    assert client.done == ALL_STEPS
    assert client.owner_creations == 0
    assert [path for path, *_ in client.calls[:3]] == [
        "/auth/login_flow",
        "/auth/login_flow/fake-login-flow",
        "/auth/token",
    ]


def test_never_allows_non_dev_base_url():
    with pytest.raises(BootstrapError, match="local DEV"):
        Client("http://homeassistant.local:8123")
    assert Client(BASE_URL).base_url == BASE_URL


def test_rejects_absolute_url_paths_before_network():
    client = Client()
    with pytest.raises(BootstrapError, match="API path"):
        client.call("//another.example/evil")


def test_bash_entrypoint_is_valid_and_help_uses_no_docker():
    script = ROOT / "scripts" / "dev-ha.sh"
    syntax = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert syntax.returncode == 0, syntax.stderr
    help_result = subprocess.run(["bash", str(script), "help"], capture_output=True, text=True)
    assert help_result.returncode == 0, help_result.stderr
    assert "reset" in help_result.stdout
    assert "test / test" in help_result.stdout


def test_completed_installation_without_onboarding_view(monkeypatch):
    """After HA restart the onboarding component no longer installs that view."""
    client = Client()
    requested = []

    def fake_call(path, **_):
        requested.append(path)
        if path == "/api/onboarding":
            raise APIStatusError(path, 404)
        if path == "/auth/providers":
            return {"providers": [{"name": "Home Assistant", "type": "homeassistant", "id": None}]}
        raise AssertionError(path)

    monkeypatch.setattr(client, "call", fake_call)
    assert client.steps_done() == ALL_STEPS
    assert requested == ["/api/onboarding", "/auth/providers"]


def test_missing_onboarding_view_without_auth_provider_is_not_a_success(monkeypatch):
    client = Client()

    def fake_call(path, **_):
        if path == "/api/onboarding":
            raise APIStatusError(path, 404)
        if path == "/auth/providers":
            return {"providers": []}
        raise AssertionError(path)

    monkeypatch.setattr(client, "call", fake_call)
    with pytest.raises(BootstrapError, match="onboarding view missing"):
        client.steps_done()
