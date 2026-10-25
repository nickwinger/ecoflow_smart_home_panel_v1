"""Exhaustive paths, malformed-input bounds and sensitive subtree exclusions."""

import json
from pathlib import Path

import pytest

from custom_components.ecoflow_smart_home_panel_v1.quota import (
    MAX_ARRAY,
    MAX_DEPTH,
    MAX_ENTITIES,
    QuotaLimitError,
    display_path,
    extract_leaves,
    identity,
)

FIXTURE = json.loads(Path("tests/fixtures/quota.json").read_text())["data"]


def independent_leaves(value, path=()):
    if isinstance(value, dict):
        return {
            leaf
            for key, child in value.items()
            for leaf in independent_leaves(child, path + (key,))
        }
    if isinstance(value, list):
        return {
            leaf for i, child in enumerate(value) for leaf in independent_leaves(child, path + (i,))
        }
    return {path}


def test_every_scalar_exactly_once():
    actual = extract_leaves(FIXTURE)
    assert actual.excluded == 0
    assert set(actual.leaves) == independent_leaves(FIXTURE)
    assert len({identity(path) for path in actual.leaves}) == len(actual.leaves)
    assert actual.leaves[("collision.value",)] == 8
    assert actual.leaves[("collision", "value")] == 9
    assert display_path(("collision.value",)) == display_path(("collision", "value"))
    assert extract_leaves(dict(reversed(list(FIXTURE.items())))) == actual


def test_typed_identity_and_empty_null():
    snapshot = extract_leaves({"a": [None, [], {}, False], "a[0]": 3, "n": {"a.b": 2}})
    assert set(snapshot.leaves) == {("a", 0), ("a", 3), ("a[0]",), ("n", "a.b")}
    assert snapshot.leaves[("a", 0)] is None
    assert identity(("a", 0)) != identity(("a[0]",))


@pytest.mark.parametrize(
    "key",
    [
        "accessKey",
        "secret_key",
        "password",
        "token",
        "serialNumber",
        "heartbeat.mm100Sn",
        "bms.sn",
        "certificatePassword",
        "a.authorization",
        "__bad/key",
        "123dynamic",
    ],
)
def test_sensitive_or_invalid_subtree(key):
    assert extract_leaves({key: {"value": [1, 2]}}).leaves == {}


def test_sensitive_value_and_invalid_scalars():
    snapshot = extract_leaves(
        {
            "plain": "test-secret",
            "key-test-secret": 1,
            "huge": "x" * 256,
            "nan": float("nan"),
            "infinity": float("inf"),
            "bignum": 10**200,
            "valid": "ok",
        },
        ("test-secret",),
    )
    assert snapshot.leaves == {
        ("huge",): None,
        ("nan",): None,
        ("infinity",): None,
        ("bignum",): None,
        ("valid",): "ok",
    }
    assert snapshot.excluded == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"array": list(range(MAX_ARRAY + 1))},
        {f"key{i}": i for i in range(MAX_ENTITIES + 1)},
        {"many": [{f"k{j}": j for j in range(50)} for _ in range(100)]},
    ],
    ids=["array", "keys", "leaves"],
)
def test_limits(payload):
    with pytest.raises(QuotaLimitError):
        extract_leaves(payload)


def test_depth_cycle_and_path_limits():
    value = {}
    current = value
    for _ in range(MAX_DEPTH + 1):
        current["child"] = {}
        current = current["child"]
    with pytest.raises(QuotaLimitError):
        extract_leaves(value)
    cycle = {}
    cycle["child"] = cycle
    with pytest.raises(QuotaLimitError):
        extract_leaves(cycle)
    value = {"x" * 128: {"y" * 128: {"z" * 128: {"w" * 128: 1}}}}
    with pytest.raises(QuotaLimitError):
        extract_leaves(value)


def test_local_cache_is_not_device_telemetry():
    assert extract_leaves({"_cached_at": 5, "_has_loadCmdChCtrlInfos": True}).leaves == {}
