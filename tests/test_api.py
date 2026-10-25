"""Transport tests never open network sockets."""

import asyncio
import hashlib
import hmac
from unittest.mock import patch

import aiohttp
import pytest

from custom_components.ecoflow_smart_home_panel_v1.api import (
    MAX_RESPONSE_BYTES,
    AuthenticationError,
    EcoFlowClient,
    EcoFlowError,
    InvalidResponseError,
    RateLimitError,
    UnsupportedDeviceError,
    flatten_parameters,
    signed_headers,
    validate_shp_v1,
)

from .http import MockHTTP

URL = "https://api-e.ecoflow.com/iot-open/sign/device/quota/all?sn=SHP-TEST-0001"


@pytest.mark.parametrize(
    "params,expected",
    [
        ({"sn": "SHP-TEST-0001"}, "sn=SHP-TEST-0001"),
        (
            {
                "sn": "SHP-TEST-0001",
                "params": {"id": 16, "cmdSet": 11, "ch": 6, "ctrlMode": 1, "sta": 1},
            },
            "params.ch=6&params.cmdSet=11&params.ctrlMode=1&params.id=16&params.sta=1&sn=SHP-TEST-0001",
        ),
        ({"ids": [2, 3], "device": {"a": 4}}, "device.a=4&ids[0]=2&ids[1]=3"),
    ],
)
def test_signature(params, expected):
    message = expected + "&accessKey=test-access&nonce=123456&timestamp=1700000000000"
    expected_sign = hmac.new(b"test-secret", message.encode(), hashlib.sha256).hexdigest()
    headers = signed_headers(
        params, "test-access", "test-secret", nonce="123456", timestamp="1700000000000"
    )
    assert headers["sign"] == expected_sign
    assert headers["nonce"] == "123456"
    assert flatten_parameters({"x": [True, None]}) == {"x[0]": "True", "x[1]": "None"}


async def test_get_signed_current_data(quota):
    async with aiohttp.ClientSession() as session:
        client = EcoFlowClient(session, "test-access", "test-secret", "SHP-TEST-0001")
        with MockHTTP() as mocked:
            mocked.get(URL, payload={"code": "0", "data": quota})
            mocked.get(URL, payload={"code": "0", "data": {}})
            assert await client.get_quota_all() == quota
            assert await client.get_quota_all() == {}
            for (method, _), requests in mocked.requests.items():
                assert method == "GET"
                assert requests[0].kwargs["allow_redirects"] is False
                assert requests[0].kwargs["headers"]["accessKey"] == "test-access"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"code": 0, "data": {}},
        {"code": "1234", "message": "secret"},
        {"code": "0"},
        {"code": "0", "data": []},
    ],
)
async def test_invalid_payload(payload):
    async with aiohttp.ClientSession() as session:
        with MockHTTP() as mocked:
            mocked.get(URL, payload=payload)
            with pytest.raises(InvalidResponseError):
                await EcoFlowClient(session, "a", "b", "SHP-TEST-0001").get_quota_all()


@pytest.mark.parametrize(
    "status,error",
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (429, RateLimitError),
        (500, EcoFlowError),
        (302, EcoFlowError),
    ],
)
async def test_http_failure(status, error, caplog):
    async with aiohttp.ClientSession() as session:
        with MockHTTP() as mocked:
            mocked.get(URL, status=status, body="test-secret SHP-TEST-0001")
            with pytest.raises(error) as caught:
                await EcoFlowClient(
                    session, "test-access", "test-secret", "SHP-TEST-0001"
                ).get_quota_all()
            assert "test-secret" not in str(caught.value) + caplog.text
            assert "SHP-TEST" not in str(caught.value) + caplog.text


@pytest.mark.parametrize(
    "body",
    ["not JSON", "[" * 2000, "x" * (MAX_RESPONSE_BYTES + 1)],
    ids=["bad_json", "deep_json", "oversize"],
)
async def test_malformed_and_large(body):
    async with aiohttp.ClientSession() as session:
        with MockHTTP() as mocked:
            mocked.get(URL, body=body)
            with pytest.raises(InvalidResponseError):
                await EcoFlowClient(session, "a", "b", "SHP-TEST-0001").get_quota_all()


@pytest.mark.parametrize("error", [aiohttp.ClientError("secret"), TimeoutError("secret")])
async def test_network_error_redacted(error):
    async with aiohttp.ClientSession() as session:
        with MockHTTP() as mocked:
            mocked.get(URL, exception=error)
            with pytest.raises(EcoFlowError, match="Cannot communicate"):
                await EcoFlowClient(session, "a", "b", "SHP-TEST-0001").get_quota_all()


async def test_rate_limit_prevents_manual_refresh():
    async with aiohttp.ClientSession() as session:
        client = EcoFlowClient(session, "a", "b", "SHP-TEST-0001")
        with MockHTTP() as mocked:
            mocked.get(URL, status=429, headers={"Retry-After": "120"})
            for _ in range(2):
                with pytest.raises(RateLimitError):
                    await client.get_quota_all()
            assert sum(map(len, mocked.requests.values())) == 1


async def test_cancellation_propagates():
    async with aiohttp.ClientSession() as session:
        with patch.object(session, "get", side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await EcoFlowClient(session, "a", "b", "SHP-TEST-0001").get_quota_all()


def test_layout(quota):
    validate_shp_v1(quota)
    nested = {"heartbeat": {k.split(".")[1]: v for k, v in quota.items()}}
    validate_shp_v1(nested)
    with pytest.raises(UnsupportedDeviceError):
        validate_shp_v1({})
    with pytest.raises(UnsupportedDeviceError):
        validate_shp_v1({**nested, **quota})
    quota["heartbeat.loadCmdChCtrlInfos"].pop()
    with pytest.raises(UnsupportedDeviceError):
        validate_shp_v1(quota)


PUT_URL = "https://api-e.ecoflow.com/iot-open/sign/device/quota"


@pytest.mark.parametrize(
    "params",
    [
        {"cmdSet": 11, "id": 16, "ch": 0, "ctrlMode": 0, "sta": 0},
        {"cmdSet": 11, "id": 16, "ch": 9, "ctrlMode": 1, "sta": 1},
        {"cmdSet": 11, "id": 17, "ch": 10, "ctrlMode": 1, "sta": 2},
        {"cmdSet": 11, "id": 17, "ch": 11, "ctrlMode": 0, "sta": 0},
    ],
)
async def test_put_signed_body_and_acknowledgment(params):
    with MockHTTP() as mocked:
        async with aiohttp.ClientSession() as session:
            mocked.put(PUT_URL, payload={"code": "0", "message": "ack"})
            client = EcoFlowClient(session, "test-access", "test-secret", "SHP-TEST-0001")
            assert await client.put_quota(params) is None
            request = mocked.requests[("PUT", PUT_URL)][0].kwargs
            assert request["json"] == {"sn": "SHP-TEST-0001", "params": params}
            assert request["allow_redirects"] is False
            assert request["headers"]["Content-Type"] == "application/json;charset=UTF-8"
            headers = request["headers"]
            # Independent known wire format, not production flattening logic.
            message = "&".join(f"params.{key}={params[key]}" for key in sorted(params))
            message += f"&sn=SHP-TEST-0001&accessKey=test-access&nonce={headers['nonce']}&timestamp={headers['timestamp']}"
            assert (
                headers["sign"]
                == hmac.new(b"test-secret", message.encode(), hashlib.sha256).hexdigest()
            )


@pytest.mark.parametrize(
    "response,error",
    [
        ({"payload": {"code": 0}}, InvalidResponseError),
        ({"payload": {"code": "123", "message": "test-secret"}}, InvalidResponseError),
        ({"payload": []}, InvalidResponseError),
        ({"status": 401}, AuthenticationError),
        ({"status": 403}, AuthenticationError),
        ({"status": 429}, RateLimitError),
        ({"status": 500}, EcoFlowError),
        ({"status": 302}, EcoFlowError),
        ({"body": "not json"}, InvalidResponseError),
        ({"body": "x" * (MAX_RESPONSE_BYTES + 1)}, InvalidResponseError),
        ({"exception": TimeoutError("test-secret")}, EcoFlowError),
        ({"exception": aiohttp.ClientError("test-secret")}, EcoFlowError),
    ],
)
async def test_put_failures_are_sanitized(response, error, caplog):
    with MockHTTP() as mocked:
        async with aiohttp.ClientSession() as session:
            mocked.put(PUT_URL, **response)
            with pytest.raises(error) as caught:
                await EcoFlowClient(
                    session, "test-access", "test-secret", "SHP-TEST-0001"
                ).put_quota({"id": 16})
            assert "test-secret" not in str(caught.value) + caplog.text
            assert "SHP-TEST" not in str(caught.value) + caplog.text


@pytest.mark.parametrize("first", ["GET", "PUT"])
async def test_get_and_put_share_rate_limit_cooldown(first):
    with MockHTTP() as mocked:
        async with aiohttp.ClientSession() as session:
            client = EcoFlowClient(session, "a", "b", "SHP-TEST-0001")
            mocked.get(
                URL if first == "GET" else PUT_URL, status=429, headers={"Retry-After": "180"}
            )
            with pytest.raises(RateLimitError):
                await (client.get_quota_all() if first == "GET" else client.put_quota({"id": 16}))
            with pytest.raises(RateLimitError):
                await client.get_quota_all()
            with pytest.raises(RateLimitError):
                await client.put_quota({"id": 16})
            assert sum(map(len, mocked.requests.values())) == 1


async def test_certification_and_read_only_heartbeat_signed_transport():
    endpoint = "https://api-e.ecoflow.com/iot-open/sign"
    async with aiohttp.ClientSession() as session:
        client = EcoFlowClient(session, "test-access", "test-secret", "SHP-TEST-0001")
        with MockHTTP() as mocked:
            mocked.get(
                endpoint + "/certification",
                payload={"code": "0", "data": {"certificateAccount": "fake"}},
            )
            assert await client.get_mqtt_certification() == {"certificateAccount": "fake"}
            request = mocked.requests[("GET", endpoint + "/certification")][0]
            h = request.kwargs["headers"]
            msg = f"accessKey=test-access&nonce={h['nonce']}&timestamp={h['timestamp']}"
            assert h["sign"] == hmac.new(b"test-secret", msg.encode(), hashlib.sha256).hexdigest()
            mocked.get(endpoint + "/device/quota", payload={"code": "0", "data": {}})
            await client.request_heartbeat()
            request = mocked.requests[("POST", endpoint + "/device/quota")][0]
            assert request.kwargs["json"] == {
                "sn": "SHP-TEST-0001",
                "params": {"quotas": ["heartbeat.time"]},
            }
            h = request.kwargs["headers"]
            msg = f"params.quotas[0]=heartbeat.time&sn=SHP-TEST-0001&accessKey=test-access&nonce={h['nonce']}&timestamp={h['timestamp']}"
            assert h["sign"] == hmac.new(b"test-secret", msg.encode(), hashlib.sha256).hexdigest()
            assert not any(k[0] == "PUT" for k in mocked.requests)


async def test_dev_home_assistant_hard_interlock_forbids_every_put(monkeypatch, quota):
    """Never actuate the real panel from isolated DEV, even with control options."""
    monkeypatch.setenv("ECOFLOW_SHP_DEV_READ_ONLY", "1")
    async with aiohttp.ClientSession() as session:
        client = EcoFlowClient(session, "test-access", "test-secret", "SHP-TEST-0001")
        with MockHTTP() as mocked:
            mocked.get(URL, payload={"code": "0", "data": quota})
            # Safe GET is still allowed.
            assert await client.get_quota_all() == quota
            # No write leaves the process.
            with pytest.raises(EcoFlowError, match="disabled in DEV"):
                await client.put_quota(
                    {"cmdSet": 11, "id": 16, "ch": 0, "ctrlMode": 1, "sta": 1}
                )
            with pytest.raises(EcoFlowError, match="disabled in DEV"):
                await client._request(
                    "PUT", {"sn": "SHP-TEST-0001", "params": {"cmdSet": 11, "id": 16}}
                )
            assert ("PUT", PUT_URL) not in mocked.requests
