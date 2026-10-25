"""Compare full native batch traces with the owner's unmodified working script."""

import ast
import asyncio
import hashlib
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.ecoflow_smart_home_panel_v1.api import AuthenticationError, EcoFlowError
from custom_components.ecoflow_smart_home_panel_v1.controls import (
    CIRCUIT_ORDER,
    read_batch_sources,
)

REFERENCE = Path(__file__).parent / "reference" / "shp_mode.py.txt"


def reference_namespace():
    """Load real reference functions, with no imports, I/O or main execution."""
    source = REFERENCE.read_bytes()
    assert hashlib.sha1(f"blob {len(source)}\0".encode() + source).hexdigest() == (
        "5b409c05f51ae15c3fe5f8c32826bf877894eadb"
    )
    tree = ast.parse(source)
    tree.body = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name != "log")
        or (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id
            in {"GRID_ORDER", "BATTERY_ORDER", "SETTLE_SECONDS", "RETRY_SECONDS", "MAX_ATTEMPTS"}
        )
    ]
    namespace = {"log": lambda _message: None}
    exec(compile(tree, str(REFERENCE), "exec"), namespace)
    return namespace


class Scenario:
    """A deterministic synthetic panel; methods only append to an in-memory trace."""

    def __init__(self, name, target):
        self.name = name
        self.target = int(target == "battery")
        self.values = [self.target if name == "already" else 1 - self.target] * 10
        self.trace = []
        self.reads = 0
        self.attempts = [0] * 10
        self.current = None
        self.completed = []
        self.failed = []

    def read(self):
        self.trace.append(("get",))
        self.reads += 1
        if (self.name == "get_before_error" and self.reads == 1) or (
            self.name == "get_after_error" and self.reads == 2
        ):
            raise EcoFlowError("synthetic GET failure")
        items = [{"ctrlSta": value} for value in self.values]
        if self.name == "missing":
            return {}
        if self.name == "partial":
            items.pop()
        if self.name == "unrelated_missing":
            items[9] = {}
        if self.name == "strings":
            items = [{"ctrlSta": str(value)} for value in self.values]
        if self.name == "sta_fallback":
            items = [{"sta": value} for value in self.values]
        if self.name == "ch_fallback":
            items[6] = None
            items.append({"ch": "6", "ctrlSta": self.values[6]})
        if self.name == "nested":
            return {"heartbeat": {"loadCmdChCtrlInfos": items}}
        data = {"heartbeat.loadCmdChCtrlInfos": items}
        if self.name == "both_layouts":
            data["heartbeat"] = {"loadCmdChCtrlInfos": [{"ctrlSta": 1 - self.target}] * 10}
        return data

    def write(self, params):
        self.trace.append(("put", deepcopy(params)))
        index = params["ch"]
        self.attempts[index] += 1
        if (self.name == "put_error" and index == 5) or (
            self.name == "multiple_errors" and index in (5, 9)
        ):
            raise EcoFlowError("synthetic PUT failure")
        if self.name == "unexpected_error" and index == 5:
            raise RuntimeError("synthetic unexpected failure")
        if self.name == "all_put_errors":
            raise EcoFlowError("synthetic PUT failure")
        if self.name == "exhausted" and index == 5:
            return {"code": "0"}
        if self.name != "retry" or index != 5 or self.attempts[index] == 3:
            self.values[index] = params["sta"]
        return {"code": "0"}

    def pause(self, seconds):
        self.trace.append(("sleep", seconds))

    def run_reference(self, target):
        namespace = reference_namespace()

        def refresh():
            self.current = {"data": self.read()}

        namespace.update(
            put_quota=self.write,
            refresh_quota_all=refresh,
            get_quota_all=lambda: self.current,
            time=SimpleNamespace(sleep=self.pause),
        )
        set_channel = namespace["set_channel_until_confirmed"]

        def record_result(channel, desired):
            try:
                result = set_channel(channel, desired)
            except Exception:
                self.failed.append(channel)
                raise
            self.completed.append(channel)
            return result

        namespace["set_channel_until_confirmed"] = record_result
        try:
            namespace["run_mode"](target)
        except RuntimeError:
            return False
        return True


@pytest.mark.parametrize("target", ["grid", "battery"])
@pytest.mark.parametrize(
    "scenario",
    [
        "success",
        "already",
        "retry",
        "exhausted",
        "missing",
        "partial",
        "unrelated_missing",
        "nested",
        "both_layouts",
        "strings",
        "sta_fallback",
        "ch_fallback",
        "get_before_error",
        "get_after_error",
        "put_error",
        "multiple_errors",
        "all_put_errors",
        "unexpected_error",
    ],
)
async def test_entire_batch_matches_reference(control_env, mock_quota, scenario, target):
    controls, put, sleep = control_env
    reference = Scenario(scenario, target)
    expected_success = reference.run_reference(target)
    native = Scenario(scenario, target)
    mock_quota.side_effect = native.read
    put.side_effect = native.write
    sleep.side_effect = native.pause
    if expected_success:
        result = await controls.async_set_all_sources(target)
        assert result["state"] == "succeeded"
        assert result["failed"] == []
    else:
        with pytest.raises(HomeAssistantError) as raised:
            await controls.async_set_all_sources(target)
        assert raised.value.translation_key == "batch_failed"
        assert raised.value.translation_placeholders == {
            "channels": ", ".join(map(str, controls.status["failed"]))
        }
        assert controls.status["state"] == "failed"
    assert native.trace == reference.trace
    assert native.values == reference.values
    assert controls.status["completed"] == reference.completed
    assert controls.status["failed"] == reference.failed
    assert len(controls.status["completed"]) + len(controls.status["failed"]) == 10
    assert set(controls.status["completed"]).isdisjoint(controls.status["failed"])
    assert set(controls.status["completed"] + controls.status["failed"]) == set(CIRCUIT_ORDER)


@pytest.mark.parametrize(
    "items",
    [
        [],
        [{"ctrlSta": "1"}],
        [{"ctrlSta": True}],
        [{"ctrlSta": 0.9}],
        [{"ctrlSta": None, "sta": 1}],
        [{"sta": 0}],
        [{"ctrlSta": 2}],
        [{"ctrlSta": "bad"}],
        [{"ctrlSta": {}}],
        [{"ctrlSta": float("inf")}],
        [None, {"ch": "0", "ctrlSta": 1}],
        [None, {"ch": "bad", "ctrlSta": 0}, {"ch": 0, "ctrlSta": 1}],
        [{}, {"ch": 0, "ctrlSta": 1}],
        [{"ch": 9, "ctrlSta": 0}, {"ch": 0, "ctrlSta": 1}],
    ],
)
def test_channel_lookup_and_conversion_match_reference(items):
    namespace = reference_namespace()
    data = {"heartbeat.loadCmdChCtrlInfos": items}
    namespace["get_quota_all"] = lambda: {"data": data}
    expected = tuple(namespace["read_channel_state"](i) for i in range(1, 11))
    assert tuple(state or "unknown" for state in read_batch_sources(data)) == expected


@pytest.mark.parametrize("stage", ["after_failure", "last_retry", "between_channels"])
async def test_cancellation_stops_batch_even_after_failure(control_env, mock_quota, stage):
    controls, put, sleep = control_env
    panel = Scenario("exhausted" if stage == "last_retry" else "success", "battery")
    mock_quota.side_effect = panel.read
    put.side_effect = EcoFlowError("synthetic failure") if stage == "after_failure" else panel.write
    waiting = asyncio.Event()

    async def pause(seconds):
        if (
            stage == "after_failure"
            or (stage == "last_retry" and seconds == 15 and panel.attempts[5] == 8)
            or (stage == "between_channels" and controls.status["completed"])
        ):
            waiting.set()
            await asyncio.Event().wait()

    sleep.side_effect = pause
    task = asyncio.create_task(controls.async_set_all_sources("battery"))
    async with asyncio.timeout(2):
        await waiting.wait()
    writes = put.await_count
    await controls.async_cancel()
    assert task.cancelled()
    assert put.await_count == writes
    assert controls.status["state"] == "cancelled"
    assert len(controls.status["completed"]) < 10


async def test_put_auth_failure_starts_reauth_and_processes_other_circuits(control_env, mock_quota):
    controls, put, _ = control_env
    panel = Scenario("success", "battery")
    mock_quota.side_effect = panel.read
    put.side_effect = AuthenticationError("synthetic auth failure")
    with patch.object(controls.coordinator.config_entry, "async_start_reauth") as reauth:
        with pytest.raises(HomeAssistantError):
            await controls.async_set_all_sources("battery")
    assert reauth.called
    assert [c.args[0]["ch"] + 1 for c in put.await_args_list] == list(CIRCUIT_ORDER)
    assert controls.status["failed"] == list(CIRCUIT_ORDER)


async def test_batch_lock_survives_channel_failure(control_env, mock_quota):
    """A queued individual command waits for all ten channels, including failures."""
    controls, put, sleep = control_env
    panel = Scenario("put_error", "battery")
    mock_quota.side_effect = panel.read
    put.side_effect = panel.write
    waiting = asyncio.Event()
    release = asyncio.Event()

    async def pause(seconds):
        if controls.status["failed"] == [6] and not waiting.is_set():
            waiting.set()
            await release.wait()

    sleep.side_effect = pause
    batch = asyncio.create_task(controls.async_set_all_sources("battery"))
    async with asyncio.timeout(2):
        await waiting.wait()
    individual = asyncio.create_task(controls.async_set_source(0, "grid"))
    await asyncio.sleep(0)
    assert [c.args[0]["ch"] + 1 for c in put.await_args_list] == [7, 6]
    release.set()
    results = await asyncio.gather(batch, individual, return_exceptions=True)
    assert isinstance(results[0], HomeAssistantError) and results[1] is None
    assert [c.args[0]["ch"] + 1 for c in put.await_args_list] == [*CIRCUIT_ORDER, 1]
