"""Async EcoFlow transport; signing follows the working reference.

Never log response messages, request URLs, credentials or quota values.
GET and PUT share authentication, request serialization and rate-limit cooldown.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

import aiohttp

from .const import HOSTS

MAX_RESPONSE_BYTES = 1_048_576


class EcoFlowError(Exception):
    """A sanitized cloud failure."""


class AuthenticationError(EcoFlowError):
    """HTTP authentication/authorization rejected."""


class InvalidResponseError(EcoFlowError):
    """Malformed or unsuccessful cloud response."""


class UnsupportedDeviceError(EcoFlowError):
    """Cannot establish the SHP v1 quota layout."""


class RateLimitError(EcoFlowError):
    """The cloud requests a delay."""

    def __init__(self, retry_after: int = 60) -> None:
        super().__init__("Cloud rate limit")
        self.retry_after = retry_after


def flatten_parameters(value: Any, prefix: str = "") -> dict[str, str]:
    """Preserve the reference's string conversion and indexed signing format."""
    result: dict[str, str] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            result.update(flatten_parameters(child, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(flatten_parameters(child, f"{prefix}[{index}]"))
    else:
        result[prefix] = str(value)
    return result


def signed_headers(
    parameters: dict[str, Any],
    access_key: str,
    secret_key: str,
    *,
    nonce: str | None = None,
    timestamp: str | None = None,
) -> dict[str, str]:
    """Sign sorted parameters, without URL encoding before signing."""
    nonce = nonce or str(secrets.randbelow(900_000) + 100_000)
    timestamp = timestamp or str(int(time.time() * 1000))
    flat = flatten_parameters(parameters)
    message = "&".join(f"{key}={flat[key]}" for key in sorted(flat))
    message = (
        message + "&" if message else ""
    ) + f"accessKey={access_key}&nonce={nonce}&timestamp={timestamp}"
    return {
        "accessKey": access_key,
        "nonce": nonce,
        "timestamp": timestamp,
        "sign": hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest(),
    }


def quota_member(data: dict[str, Any], path: str) -> Any:
    """Read a structural marker in either format; reject ambiguous layouts."""
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            current = None
            break
        current = current[part]
    if path in data:
        if current is not None:
            raise UnsupportedDeviceError("Ambiguous panel layout")
        return data[path]
    return current


def validate_shp_v1(data: dict[str, Any]) -> None:
    """Require the supported v1 topology without a redundant confirmation checkbox.

    The published device list has no model identifier. This conservative layout
    check is not authoritative hardware identification. Retry partial onboarding
    responses; subsequent polls may be partial.
    """
    for path, length in (
        ("heartbeat.loadCmdChCtrlInfos", 10),
        ("heartbeat.backupCmdChCtrlInfos", 2),
    ):
        items = quota_member(data, path)
        if not isinstance(items, list) or len(items) != length:
            raise UnsupportedDeviceError("SHP v1 topology missing or unsupported")
        if not all(isinstance(item, dict) and "ctrlSta" in item for item in items):
            raise UnsupportedDeviceError("Incomplete SHP v1 topology")


class EcoFlowClient:
    """One authenticated client per config entry, using HA's shared session."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_key: str,
        secret_key: str,
        serial: str,
        region: str = "eu",
    ) -> None:
        self._session = session
        self._access_key = access_key
        self._secret_key = secret_key
        self._serial = serial
        self._host = HOSTS[region]
        self._lock = asyncio.Lock()
        self._retry_at = 0.0

    async def get_quota_all(self) -> dict[str, Any]:
        """Fetch only current data. Never merge with an older response."""
        payload = await self._request("GET", {"sn": self._serial})
        if not isinstance(payload.get("data"), dict):
            raise InvalidResponseError("Missing cloud quota data")
        return payload["data"]

    async def put_quota(self, params: dict[str, int]) -> None:
        """Send a signed command. An acknowledgment does not confirm device state."""
        await self._request("PUT", {"sn": self._serial, "params": params})

    async def request_heartbeat(self) -> None:
        """Query heartbeat.time using the documented read-only GetCmdRequest.

        General HTTP documentation specifies POST for this query. This is not
        PUT, does not set RTC and contains no actuator command or desired state.
        """
        await self._request("POST", {"sn": self._serial, "params": {"quotas": ["heartbeat.time"]}})

    async def get_mqtt_certification(self) -> dict[str, Any]:
        """Obtain read-telemetry connection credentials through the shared transport."""
        payload = await self._request("GET", {}, endpoint="/iot-open/sign/certification")
        if not isinstance(payload.get("data"), dict):
            raise InvalidResponseError("Missing cloud MQTT certification")
        return payload["data"]

    async def _request(
        self, method: str, parameters: dict[str, Any], *, endpoint: str | None = None
    ) -> dict[str, Any]:
        async with self._lock:
            if time.monotonic() < self._retry_at:
                raise RateLimitError(max(1, int(self._retry_at - time.monotonic()) + 1))
            headers = signed_headers(parameters, self._access_key, self._secret_key)
            if method == "GET":
                request = self._session.get
                endpoint = endpoint or "/iot-open/sign/device/quota/all"
                arguments = {"params": parameters}
            else:
                request = self._session.post if method == "POST" else self._session.put
                endpoint = "/iot-open/sign/device/quota"
                headers["Content-Type"] = "application/json;charset=UTF-8"
                arguments = {"json": parameters}
            try:
                async with request(
                    f"{self._host}{endpoint}",
                    **arguments,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                    allow_redirects=False,
                ) as response:
                    if response.status in (401, 403):
                        raise AuthenticationError("Cloud authentication rejected")
                    if response.status == 429:
                        delay = response.headers.get("Retry-After", "60")
                        seconds = min(3600, max(30, int(delay))) if delay.isdigit() else 60
                        self._retry_at = time.monotonic() + seconds
                        raise RateLimitError(seconds)
                    if response.status != 200:
                        raise EcoFlowError("Cloud HTTP request failed")
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(16_384):
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise InvalidResponseError("Cloud response exceeds size limit")
                    payload = json.loads(body)
            except aiohttp.ClientError, TimeoutError:
                raise EcoFlowError("Cannot communicate with EcoFlow") from None
            except ValueError, RecursionError:
                raise InvalidResponseError("Invalid cloud JSON") from None
            if not isinstance(payload, dict) or payload.get("code") != "0":
                # No authoritative HTTP application error table is supplied.
                # An arbitrary nonzero code is not proof of invalid credentials.
                raise InvalidResponseError("Cloud rejected quota request")
            return payload
