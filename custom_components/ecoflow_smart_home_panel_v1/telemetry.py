"""Passive SHP v1 power telemetry; no MQTT publish or device-setting commands.

The public quota topic pushes bare infoList while HTTP exposes the same array
as channelPower.infoList. Only packet counters and receipt time are retained; no readings are stored.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from asyncio import sleep
from typing import TYPE_CHECKING

import paho.mqtt.client as mqtt

from .api import (
    MAX_RESPONSE_BYTES,
    AuthenticationError,
    EcoFlowError,
    InvalidResponseError,
    RateLimitError,
    quota_member,
)
from .quota import QuotaLimitError, RawPath, Scalar, display_path, extract_leaves

if TYPE_CHECKING:
    from .coordinator import EcoFlowCoordinator

POWER_MAX_AGE_SECONDS = 30


def mqtt_credentials(data: dict) -> tuple[str, int, str, str]:
    """Only verified TLS connections to EcoFlow's public brokers are allowed."""
    host, port = data.get("url"), data.get("port")
    account, password = data.get("certificateAccount"), data.get("certificatePassword")
    if (
        data.get("protocol") != "mqtts"
        or host not in ("mqtt-e.ecoflow.com", "mqtt.ecoflow.com")
        or str(port) != "8883"
        or not isinstance(account, str)
        or not account
        or len(account) > 256
        or any(c in account for c in "/+#\x00")
        or not isinstance(password, str)
        or not password
        or len(password) > 1024
    ):
        raise InvalidResponseError("Invalid cloud MQTT certification")
    return host, 8883, account, password


def power_frame(payload: bytes, sensitive: tuple[str, ...]) -> dict[str, Scalar] | None:
    """Decode only the evidenced SHP power-array shape, ignoring other frames."""
    if len(payload) > MAX_RESPONSE_BYTES:
        return None
    try:
        body = json.loads(payload)
        if not isinstance(body, dict) or not isinstance(params := body.get("params"), dict):
            return None
        direct = params.get("infoList")
        prefixed = quota_member(params, "channelPower.infoList")
        if direct is not None and prefixed is not None:
            return None
        items = direct if direct is not None else prefixed
        if (
            not isinstance(items, list)
            or len(items) not in (10, 12)
            or not all(
                isinstance(item, dict) and "chWatt" in item and "powType" in item for item in items
            )
        ):
            return None
        leaves = extract_leaves({"channelPower.infoList": items}, sensitive).leaves
        return {display_path(path): value for path, value in leaves.items()}
    except ValueError, TypeError, RecursionError, EcoFlowError, QuotaLimitError:
        return None


class PowerTelemetry:
    """One passive public MQTT connection owned by the shared coordinator."""

    def __init__(self, coordinator: EcoFlowCoordinator) -> None:
        self.coordinator = coordinator
        self.enabled = False
        self.connected = False
        self.reports = 0
        self.last_power_at: float | None = None
        self.error: str | None = None
        self._task: asyncio.Task | None = None
        self._client: mqtt.Client | None = None
        self._ready = asyncio.Event()
        self._disconnected = asyncio.Event()

    def start(self) -> None:
        self.enabled = True
        entry = self.coordinator.config_entry
        self._task = entry.async_create_background_task(
            self.coordinator.hass, self._run(), "EcoFlow power telemetry", eager_start=False
        )

    async def async_stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        self._invalidate()

    def _invalidate(self) -> None:
        self.connected = False
        self.last_power_at = None

    def power_age(self) -> float | None:
        return None if self.last_power_at is None else max(0, time.monotonic() - self.last_power_at)

    def apply(self, leaves: dict[RawPath, Scalar]) -> dict[RawPath, Scalar]:
        """Do not present cached HTTP power as current after the live stream stops."""
        if not self.enabled:
            return leaves
        result = dict(leaves)
        age = self.power_age()
        fresh = self.connected and age is not None and age <= POWER_MAX_AGE_SECONDS
        for path in leaves.keys() | self.coordinator.known_paths:
            logical = display_path(path)
            if logical.startswith("channelPower.infoList["):
                if not fresh:
                    result.pop(path, None)
        return result

    def _connected_callback(self, client, _userdata, _flags, reason, _properties) -> None:
        self.coordinator.hass.loop.call_soon_threadsafe(
            self._accept_connection, client, not reason.is_failure
        )

    def _accept_connection(self, client, success: bool) -> None:
        if client is not self._client:
            return
        self.connected = success
        self._ready.set()
        if success:
            self.error = None
        else:
            self.error = "mqtt_auth_or_connection_rejected"
            self._disconnected.set()

    def _disconnect_callback(self, client, *_args) -> None:
        self.coordinator.hass.loop.call_soon_threadsafe(self._accept_disconnect, client)

    def _accept_disconnect(self, client) -> None:
        if client is self._client:
            self._invalidate()
            self._disconnected.set()

    def _message_callback(self, client, _userdata, message) -> None:
        if message.retain:
            return
        values = power_frame(message.payload, self.coordinator._sensitive)
        if values is not None:
            self.coordinator.hass.loop.call_soon_threadsafe(self._accept_power, client, values)

    def _accept_power(self, client, values: dict[str, Scalar]) -> None:
        if client is not self._client or not self.connected:
            return
        self.last_power_at = time.monotonic()
        self.reports += 1

    def _create_client(self, credentials: tuple[str, int, str, str]) -> mqtt.Client:
        host, port, account, password = credentials
        # Stable across reconnects, distinct from other entries and integrations.
        suffix = hashlib.sha256(self.coordinator.config_entry.entry_id.encode()).hexdigest()[:12]
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"Hassio-{account}-shpv1-{suffix}",
            reconnect_on_failure=False,
        )
        client.username_pw_set(account, password)
        client.tls_set()  # Certificate loading runs in HA's executor.
        client.on_connect = self._connected_callback
        client.on_disconnect = self._disconnect_callback
        client.on_message = self._message_callback
        client.connect_async(host, port, keepalive=30)
        return client

    @staticmethod
    def _stop_client(client: mqtt.Client) -> None:
        client.disconnect()
        client.loop_stop()

    async def _run(self) -> None:
        hass = self.coordinator.hass
        while True:
            delay = 30
            try:
                credentials = mqtt_credentials(
                    await self.coordinator.client.get_mqtt_certification()
                )
                self._ready.clear()
                self._disconnected.clear()
                self._client = await hass.async_add_executor_job(self._create_client, credentials)
                await hass.async_add_executor_job(self._client.loop_start)
                async with asyncio.timeout(20):
                    await self._ready.wait()
                if self.connected:
                    topic = f"/open/{credentials[2]}/{self.coordinator.serial}/quota"
                    result, _ = self._client.subscribe(topic, qos=0)
                    if result != mqtt.MQTT_ERR_SUCCESS:
                        raise EcoFlowError("Cloud telemetry subscription failed")
                    while not self._disconnected.is_set():
                        try:
                            async with asyncio.timeout(60):
                                await self._disconnected.wait()
                        except TimeoutError:
                            age = self.power_age()
                            if age is None or age > POWER_MAX_AGE_SECONDS:
                                raise EcoFlowError("Cloud power telemetry stalled") from None
            except AuthenticationError:
                self.error = "authentication_failed"
                self.coordinator.config_entry.async_start_reauth(hass)
                return
            except (EcoFlowError, OSError, ValueError, TimeoutError) as error:
                self.error = "telemetry_connection_failed"
                if isinstance(error, RateLimitError):
                    delay = max(delay, error.retry_after)
            finally:
                client, self._client = self._client, None
                self._invalidate()
                if client is not None:
                    await hass.async_add_executor_job(self._stop_client, client)
            await sleep(delay)
