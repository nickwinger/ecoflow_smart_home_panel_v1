"""Offline passive MQTT lifecycle, raw identity and stale-power protection."""

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.ecoflow_smart_home_panel_v1.api import (
    AuthenticationError,
    EcoFlowError,
    InvalidResponseError,
    RateLimitError,
)
from custom_components.ecoflow_smart_home_panel_v1.const import DOMAIN
from custom_components.ecoflow_smart_home_panel_v1.telemetry import (
    PowerTelemetry,
    mqtt_credentials,
    power_frame,
)

START = PowerTelemetry.start
CERT = {
    "url": "mqtt-e.ecoflow.com",
    "port": "8883",
    "protocol": "mqtts",
    "certificateAccount": "synthetic-account",
    "certificatePassword": "synthetic-password",
}
FRAME = {"params": {"infoList": [{"chWatt": 100 + i, "powType": 0} for i in range(12)]}}


@pytest.mark.parametrize(
    "change",
    [
        {"url": "127.0.0.1"},
        {"url": "mqtt.ecoflow.com.evil.invalid"},
        {"port": 1883},
        {"port": True},
        {"protocol": "mqtt"},
        {"certificateAccount": "a/#"},
        {"certificateAccount": ""},
        {"certificateAccount": True},
        {"certificatePassword": ""},
        {"certificatePassword": 1},
    ],
)
def test_reject_unsafe_certificates(change):
    with pytest.raises(InvalidResponseError):
        mqtt_credentials({**CERT, **change})


def test_certificates_and_bounded_frame():
    assert mqtt_credentials(CERT) == (
        "mqtt-e.ecoflow.com",
        8883,
        "synthetic-account",
        "synthetic-password",
    )
    values = power_frame(json.dumps(FRAME).encode(), ())
    assert values["channelPower.infoList[6].chWatt"] == 106
    assert len(values) == 24
    frame = {"params": {"channelPower": {"infoList": FRAME["params"]["infoList"]}}}
    assert power_frame(json.dumps(frame).encode(), ()) == values
    assert (
        power_frame(
            json.dumps({"params": {"channelPower.infoList": FRAME["params"]["infoList"]}}).encode(),
            (),
        )
        == values
    )


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        {"params": []},
        {"params": {"infoList": []}},
        {"params": {"infoList": [{}] * 12}},
        {"params": {"infoList": FRAME["params"]["infoList"][:-1]}},
        {
            "params": {
                "infoList": FRAME["params"]["infoList"],
                "channelPower.infoList": FRAME["params"]["infoList"],
            }
        },
    ],
)
def test_irrelevant_or_ambiguous_messages(body):
    assert power_frame(json.dumps(body).encode(), ()) is None


def test_malformed_oversized_and_deep_messages():
    assert power_frame(b"not-json", ()) is None
    assert power_frame(b"x" * 1048577, ()) is None
    frame = deepcopy(FRAME)
    frame["params"]["infoList"][0]["bad"] = {"deep": list(range(129))}
    assert power_frame(json.dumps(frame).encode(), ()) is None


async def setup_stream(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    stream = entry.runtime_data.telemetry
    stream.enabled = True
    stream._client = Mock()
    stream.connected = True
    return stream


async def test_freshness_does_not_rewrite_http_values_or_raw_paths(hass, entry, mock_quota):
    stream = await setup_stream(hass, entry)
    flat = ("channelPower.infoList", 6, "chWatt")
    nested = ("channelPower", "infoList", 6, "chWatt")
    other = ("heartbeat.gridSta",)
    leaves = {flat: 10, nested: 20, other: 1}
    assert stream.apply(leaves) == {other: 1}
    stream._message_callback(
        stream._client, None, SimpleNamespace(payload=json.dumps(FRAME).encode(), retain=False)
    )
    await hass.async_block_till_done()
    assert stream.reports == 1
    assert stream.apply(leaves) == leaves  # MQTT data are not merged into HTTP or control status.
    assert not hasattr(stream, "_power")  # No second readings store.
    stream.last_power_at -= 31
    assert stream.apply(leaves) == {other: 1}
    stream._accept_disconnect(stream._client)
    assert stream.last_power_at is None
    stream._client = None  # This test uses an inert transport.


async def test_stale_http_power_unavailable_and_recovery_keeps_entity(
    hass, entry, mock_quota, quota
):
    mock_quota.return_value = {
        **quota,
        "channelPower.infoList": deepcopy(FRAME["params"]["infoList"]),
    }
    stream = await setup_stream(hass, entry)
    coordinator = entry.runtime_data
    uid = coordinator.unique_id(("channelPower.infoList", 6, "chWatt"))
    eid = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, uid)
    await coordinator.async_refresh()
    assert hass.states.get(eid).state == "unavailable"
    stream._accept_power(stream._client, {})
    await coordinator.async_refresh()
    assert hass.states.get(eid).state == "106"
    stream.last_power_at -= 31
    await coordinator.async_refresh()
    assert hass.states.get(eid).state == "unavailable"
    stream._accept_power(stream._client, {})
    mock_quota.return_value["channelPower.infoList"][6]["chWatt"] = 321
    await coordinator.async_refresh()
    assert hass.states.get(eid).state == "321"
    assert er.async_get(hass).async_get_entity_id("sensor", DOMAIN, uid) == eid
    stream._client = None


async def test_retained_old_connection_and_irrelevant_frames_are_ignored(hass, entry, mock_quota):
    stream = await setup_stream(hass, entry)
    stream._message_callback(
        stream._client, None, SimpleNamespace(payload=json.dumps(FRAME).encode(), retain=True)
    )
    stream._message_callback(stream._client, None, SimpleNamespace(payload=b"{}", retain=False))
    stream._accept_power(Mock(), {})
    stream._accept_disconnect(Mock())
    stream._accept_connection(Mock(), True)
    await hass.async_block_till_done()
    assert stream.reports == 0
    assert stream.connected
    stream._client = None


async def test_transport_only_subscribes_no_publish_and_stops_on_unload(hass, entry, mock_quota):
    assert await hass.config_entries.async_setup(entry.entry_id)
    stream = entry.runtime_data.telemetry
    transport = Mock()
    transport.subscribe.return_value = (0, 1)
    subscribed = asyncio.Event()

    def start():
        stream._connected_callback(transport, None, None, SimpleNamespace(is_failure=False), None)

    def subscribe(topic, qos):
        assert topic == "/open/synthetic-account/SHP-TEST-0001/quota" and qos == 0
        subscribed.set()
        return (0, 1)

    transport.loop_start.side_effect = start
    transport.subscribe.side_effect = subscribe
    with (
        patch.object(stream, "_create_client", return_value=transport),
        patch.object(
            entry.runtime_data.client, "get_mqtt_certification", new=AsyncMock(return_value=CERT)
        ),
    ):
        START(stream)
        async with asyncio.timeout(2):
            await subscribed.wait()
        assert stream.connected
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert not stream.connected and stream._task is None
    transport.publish.assert_not_called()
    transport.disconnect.assert_called_once()
    transport.loop_stop.assert_called_once()


@pytest.mark.parametrize("failure", ["rejected", "subscribe", "disconnect", "silent", "stale"])
async def test_broker_failure_stops_transport_before_retry(hass, entry, mock_quota, failure):
    """Connection loss and a silent broker must recover without a leaked thread."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    stream = entry.runtime_data.telemetry
    transport = Mock()
    waiting = asyncio.Event()

    def start():
        stream._connected_callback(
            transport, None, None, SimpleNamespace(is_failure=failure == "rejected"), None
        )

    def subscribe(*args, **kwargs):
        if failure == "disconnect":
            stream._disconnect_callback(transport)
        return (1 if failure == "subscribe" else 0, 1)

    async def pause(seconds):
        assert seconds == 30
        waiting.set()
        await asyncio.Event().wait()

    async def stalled():
        if failure == "stale":
            stream._accept_power(transport, {})
            stream.last_power_at -= 31
        raise TimeoutError

    transport.loop_start.side_effect = start
    transport.subscribe.side_effect = subscribe
    if failure in ("silent", "stale"):
        stream._disconnected.wait = stalled
    with (
        patch.object(stream, "_create_client", return_value=transport),
        patch.object(entry.runtime_data.client, "get_mqtt_certification", return_value=CERT),
        patch("custom_components.ecoflow_smart_home_panel_v1.telemetry.sleep", side_effect=pause),
    ):
        START(stream)
        async with asyncio.timeout(2):
            await waiting.wait()
        assert not stream.connected and stream.last_power_at is None
        assert stream._client is None
        transport.disconnect.assert_called_once()
        transport.loop_stop.assert_called_once()
        transport.publish.assert_not_called()
        await stream.async_stop()


@pytest.mark.parametrize(
    "error,delay",
    [
        (EcoFlowError("secret message"), 30),
        (RateLimitError(90), 90),
        (OSError("private hostname"), 30),
    ],
)
async def test_retry_uses_bounded_delay_without_sensitive_error(
    hass, entry, mock_quota, error, delay
):
    assert await hass.config_entries.async_setup(entry.entry_id)
    stream = entry.runtime_data.telemetry
    waiting = asyncio.Event()
    delays = []

    async def sleep(seconds):
        delays.append(seconds)
        waiting.set()
        await asyncio.Event().wait()

    with (
        patch.object(entry.runtime_data.client, "get_mqtt_certification", side_effect=error),
        patch("custom_components.ecoflow_smart_home_panel_v1.telemetry.sleep", side_effect=sleep),
    ):
        START(stream)
        async with asyncio.timeout(2):
            await waiting.wait()
        assert delays == [delay]
        assert stream.error == "telemetry_connection_failed"
        await stream.async_stop()


async def test_mqtt_auth_starts_reauth(hass, entry, mock_quota):
    assert await hass.config_entries.async_setup(entry.entry_id)
    stream = entry.runtime_data.telemetry
    with patch.object(
        entry.runtime_data.client,
        "get_mqtt_certification",
        side_effect=AuthenticationError("secret"),
    ):
        START(stream)
        await stream._task
    assert stream.error == "authentication_failed"
    assert any(
        f["context"].get("source") == "reauth" for f in hass.config_entries.flow.async_progress()
    )


async def test_client_uses_verified_tls_and_stable_identity(hass, entry, mock_quota):
    assert await hass.config_entries.async_setup(entry.entry_id)
    stream = entry.runtime_data.telemetry
    with patch("custom_components.ecoflow_smart_home_panel_v1.telemetry.mqtt.Client") as factory:
        stream._create_client(mqtt_credentials(CERT))
        first = factory.call_args
        stream._create_client(mqtt_credentials(CERT))
        assert factory.call_args == first
        factory.return_value.tls_set.assert_called_with()
        factory.return_value.tls_insecure_set.assert_not_called()
        factory.return_value.connect_async.assert_called_with(
            "mqtt-e.ecoflow.com", 8883, keepalive=30
        )
        factory.return_value.publish.assert_not_called()
