#!/usr/bin/env python3
"""One-time, localhost-only Home Assistant DEV account/onboarding bootstrap.

Never use against another host or production HA. Home Assistant 2026.10.3:
- GET  /api/onboarding
- POST /api/onboarding/users
- POST /auth/token
- POST /api/onboarding/core_config, /analytics, /integration

The onboarding credentials are a deliberate *local-only test fixture*, not
secrets for another system. Auth/access/refresh codes remain in memory.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping
from typing import Any
from urllib import error, parse, request

BASE_URL = "http://127.0.0.1:8124"
COMPOSE_SERVICE_URL = "http://homeassistant:8123"
CLIENT_ID = "http://localhost:8124/"
REDIRECT_URI = "http://localhost:8124/?auth_callback=1"
DEV_USERNAME = "test"
DEV_PASSWORD = "test"
ALL_STEPS = frozenset({"user", "core_config", "analytics", "integration"})


class BootstrapError(RuntimeError):
    """An intentionally sanitized DEV bootstrap failure."""


class APIStatusError(BootstrapError):
    """A non-success HTTP status from the local DEV API."""

    def __init__(self, path: str, status: int) -> None:
        super().__init__(f"Home Assistant returned HTTP {status} for {path}")
        self.status = status


class Client:
    """Communicate only with the hard-coded localhost DEV Home Assistant."""

    def __init__(self, base_url: str = BASE_URL) -> None:
        if base_url not in (BASE_URL, COMPOSE_SERVICE_URL):
            raise BootstrapError("Only the dedicated local DEV Home Assistant is permitted")
        self.base_url = base_url

    def call(
        self,
        path: str,
        *,
        data: Mapping[str, Any] | None = None,
        bearer: str | None = None,
        form: bool = False,
    ) -> Any:
        if not path.startswith("/") or path.startswith("//"):
            raise BootstrapError("Unexpected API path")
        headers = {"Accept": "application/json"}
        payload = None
        if data is not None:
            if form:
                payload = parse.urlencode(data).encode("utf-8")
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            else:
                payload = json.dumps(data).encode("utf-8")
                headers["Content-Type"] = "application/json"
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        req = request.Request(
            self.base_url + path,
            data=payload,
            headers=headers,
            method="POST" if data is not None else "GET",
        )
        try:
            with request.urlopen(req, timeout=15) as response:
                body = response.read(131_072)
        except error.HTTPError as exc:
            raise APIStatusError(path, exc.code) from None
        except (error.URLError, TimeoutError, OSError) as exc:
            raise BootstrapError(f"Cannot reach DEV Home Assistant at {path}") from exc
        try:
            return json.loads(body)
        except ValueError:
            raise BootstrapError(f"Invalid JSON response for {path}") from None

    def steps_done(self) -> set[str]:
        try:
            progress = self.call("/api/onboarding")
        except APIStatusError as exc:
            if exc.status != 404:
                raise
            # HA 2026.10.3 does not register onboarding views after a fully
            # completed setup on subsequent process starts. /auth/providers
            # stays available, and only responds normally after user onboarding.
            provider_status = self.call("/auth/providers")
            providers = (
                provider_status.get("providers") if isinstance(provider_status, dict) else None
            )
            if isinstance(providers, list) and any(
                isinstance(provider, dict) and provider.get("type") == "homeassistant"
                for provider in providers
            ):
                return set(ALL_STEPS)
            raise BootstrapError(
                "DEV onboarding view missing without a local auth provider"
            ) from None
        if not isinstance(progress, list) or not all(
            isinstance(item, dict)
            and isinstance(item.get("step"), str)
            and isinstance(item.get("done"), bool)
            for item in progress
        ):
            raise BootstrapError("Unexpected Home Assistant onboarding response")
        return {item["step"] for item in progress if item["done"]}


def wait_until_ready(client: Client, timeout: int = 300) -> set[str]:
    """Wait for onboard status, not merely an open HTTP port."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return client.steps_done()
        except BootstrapError:
            time.sleep(2)
    raise BootstrapError(
        "DEV Home Assistant did not expose onboarding; check scripts/dev-ha.sh logs"
    )


def create_owner(client: Client) -> str:
    response = client.call(
        "/api/onboarding/users",
        data={
            "client_id": CLIENT_ID,
            "name": "EcoFlow DEV",
            "username": DEV_USERNAME,
            "password": DEV_PASSWORD,
            "language": "de",
        },
    )
    code = response.get("auth_code") if isinstance(response, dict) else None
    if not isinstance(code, str) or not code:
        raise BootstrapError("DEV owner creation did not return an authorization code")
    print("Created local Home Assistant DEV owner: test / test")
    return code


def login_existing_owner(client: Client) -> str:
    """Recover partial onboarding on a retained DEV volume, without replacing users."""
    started = client.call(
        "/auth/login_flow",
        data={
            "client_id": CLIENT_ID,
            "redirect_uri": CLIENT_ID,
            "handler": ["homeassistant", None],
        },
    )
    flow_id = started.get("flow_id") if isinstance(started, dict) else None
    if not isinstance(flow_id, str):
        raise BootstrapError("Could not start DEV user login for incomplete onboarding")
    result = client.call(
        f"/auth/login_flow/{flow_id}",
        data={"client_id": CLIENT_ID, "username": DEV_USERNAME, "password": DEV_PASSWORD},
    )
    code = result.get("result") if isinstance(result, dict) else None
    if not isinstance(code, str) or result.get("type") != "create_entry":
        raise BootstrapError(
            "Existing DEV account is not test/test; use manual onboarding or reset DEV volume"
        )
    return code


def access_token_for_code(client: Client, code: str) -> str:
    token_data = client.call(
        "/auth/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
        },
        form=True,
    )
    token = token_data.get("access_token") if isinstance(token_data, dict) else None
    if not isinstance(token, str) or not token:
        raise BootstrapError("Could not authorize DEV onboarding")
    return token


def finish_onboarding(client: Client, done: set[str], token: str) -> None:
    """Complete only unfinished onboarding steps through the supported API."""
    for step in ("core_config", "analytics", "integration"):
        if step in done:
            continue
        body: dict[str, str] = {}
        if step == "integration":
            body = {"client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI}
        client.call(f"/api/onboarding/{step}", data=body, bearer=token)
        print(f"DEV onboarding step finished: {step}")
    if not ALL_STEPS.issubset(client.steps_done()):
        raise BootstrapError("Some DEV onboarding steps remain incomplete")


def bootstrap(client: Client, timeout: int = 300) -> None:
    done = wait_until_ready(client, timeout)
    if ALL_STEPS.issubset(done):
        print("Existing DEV user/registry preserved; onboarding already complete.")
        return

    # The owner is created exactly once per DEV volume. Later invocations
    # neither overwrite its login nor touch production Home Assistant.
    code = create_owner(client) if "user" not in done else login_existing_owner(client)
    token = access_token_for_code(client, code)
    finish_onboarding(client, done | {"user"}, token)
    print("DEV onboarding complete; web login is test / test.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap localhost EcoFlow DEV HA only")
    parser.add_argument("--timeout", type=int, default=300, help="Maximum readiness wait seconds")
    parser.add_argument("--compose-service", action="store_true", help="Use fixed DEV Compose hostname")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 900:
        parser.error("--timeout must be between 1 and 900")
    try:
        bootstrap(Client(COMPOSE_SERVICE_URL if args.compose_service else BASE_URL), timeout=args.timeout)
    except BootstrapError as exc:
        parser.exit(1, f"DEV bootstrap error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
