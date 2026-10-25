"""Explicit, serialized commands using the working SHP v1 reference protocol.

Only fresh quota can confirm a command. No restored state, cache or PUT reply
can prove success. Timings and circuit order follow shp_mode.py.
"""

from __future__ import annotations

import asyncio
from asyncio import sleep
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .api import AuthenticationError, EcoFlowError, quota_member
from .const import CONF_BATCH_CONTROLS, CONF_CHARGE_CONTROLS, CONF_SOURCE_CONTROLS
from .quota import Snapshot

if TYPE_CHECKING:
    from .coordinator import EcoFlowCoordinator

CIRCUIT_ORDER = (7, 6, 3, 1, 2, 4, 5, 8, 9, 10)
SETTLE_SECONDS = 10
CHARGE_SETTLE_SECONDS = 2  # ecoflow_config.SETTLE_AFTER_SET_SECONDS for ecoflow_set.py
RETRY_SECONDS = 15
MAX_ATTEMPTS = 8


def read_control_states(data: dict[str, Any]) -> dict[str, tuple[str | bool | None, ...]]:
    """Derive state only from complete, unambiguous actual control arrays.

    ctrlSta wins; sta is the reference fallback only when ctrlSta is absent.
    Never coerce invalid types or invent channel mapping from powCh.
    """
    result = {}
    for kind, array, size in (
        ("source", "loadCmdChCtrlInfos", 10),
        ("charge", "backupCmdChCtrlInfos", 2),
    ):
        unknown = (None,) * size
        heartbeat = data.get("heartbeat")
        if f"heartbeat.{array}" in data and isinstance(heartbeat, dict) and array in heartbeat:
            result[kind] = unknown
            continue
        items = quota_member(data, f"heartbeat.{array}")
        if (
            not isinstance(items, list)
            or len(items) != size
            or not all(
                isinstance(item, dict) and ("ctrlSta" in item or "sta" in item) for item in items
            )
        ):
            result[kind] = unknown
            continue
        if any(
            "ch" in item
            and (type(item["ch"]) is not int or item["ch"] != i + (10 if kind == "charge" else 0))
            for i, item in enumerate(items)
        ):
            result[kind] = unknown
            continue
        mapping = {0: "grid", 1: "battery"} if kind == "source" else {0: False, 1: False, 2: True}
        values = [item.get("ctrlSta", item.get("sta")) for item in items]
        result[kind] = tuple(mapping.get(value) if type(value) is int else None for value in values)
    return result


def control_state(snapshot: Snapshot, kind: str, index: int) -> str | bool | None:
    """Charge codes follow the working helper, not the conflicting vendor enum."""
    values = (snapshot.control_states or {}).get(kind, ())
    return values[index] if type(index) is int and 0 <= index < len(values) else None


class PanelControls:
    """Serialize entire transactions, including retries and intentional batches."""

    def __init__(self, coordinator: EcoFlowCoordinator) -> None:
        self.coordinator = coordinator
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()
        self._closed = False
        self.status: dict[str, Any] = {"state": "idle"}

    def enabled(self, kind: str) -> bool:
        options = self.coordinator.config_entry.options
        key = CONF_SOURCE_CONTROLS if kind == "source" else CONF_CHARGE_CONTROLS
        return not self._closed and options.get(key) is True

    def _require_enabled(self, kind: str, batch: bool = False) -> None:
        if not self.enabled(kind) or (
            batch and self.coordinator.config_entry.options.get(CONF_BATCH_CONTROLS) is not True
        ):
            raise ServiceValidationError("EcoFlow control is not enabled in integration options")

    def _status(self, **values: Any) -> None:
        self.status = {**self.status, **values}
        self.coordinator.async_update_listeners()

    @asynccontextmanager
    async def _operation(
        self, kind: str, target: str | bool, *, batch: bool = False
    ) -> AsyncIterator[None]:
        self._require_enabled(kind, batch)
        task = asyncio.current_task()
        assert task is not None
        self._tasks.add(task)
        try:
            async with self._lock:
                self._require_enabled(kind, batch)
                self.status = {
                    "state": "running",
                    "kind": kind,
                    "target": target,
                    "batch": batch,
                    "completed": [],
                }
                self._status()
                try:
                    yield
                except asyncio.CancelledError:
                    self._status(state="cancelled")
                    self.coordinator.async_control_error(
                        HomeAssistantError("EcoFlow command cancelled; device outcome unconfirmed")
                    )
                    raise
                except (EcoFlowError, HomeAssistantError) as error:
                    self._status(state="failed")
                    self.coordinator.async_control_error(error)
                    if isinstance(error, AuthenticationError):
                        self.coordinator.config_entry.async_start_reauth(self.coordinator.hass)
                    raise HomeAssistantError(
                        "EcoFlow command failed; target was not confirmed"
                    ) from None
                else:
                    self._status(state="succeeded")
        finally:
            self._tasks.discard(task)

    async def _set(self, kind: str, index: int, target: str | bool, *, batch: bool = False) -> None:
        value = (0 if target == "grid" else 1) if kind == "source" else (2 if target else 0)
        params = {
            "cmdSet": 11,
            "id": 16 if kind == "source" else 17,
            "ch": index if kind == "source" else index + 10,
            "ctrlMode": int(value != 0),
            "sta": value,
        }
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._require_enabled(kind, batch)
            self._status(channel=index + 1, attempt=attempt)
            snapshot = await self.coordinator.async_control_refresh()
            if control_state(snapshot, kind, index) == target:
                return
            self._require_enabled(kind, batch)
            await self.coordinator.client.put_quota(params)
            await sleep(SETTLE_SECONDS if kind == "source" else CHARGE_SETTLE_SECONDS)
            snapshot = await self.coordinator.async_control_refresh()
            if control_state(snapshot, kind, index) == target:
                return
            if attempt < MAX_ATTEMPTS:
                await sleep(RETRY_SECONDS)
        raise HomeAssistantError("EcoFlow target not confirmed after eight attempts")

    async def async_set_source(self, index: int, target: str) -> None:
        if type(index) is not int or not 0 <= index < 10 or target not in ("grid", "battery"):
            raise ServiceValidationError("Invalid circuit or source")
        async with self._operation("source", target):
            await self._set("source", index, target)

    async def async_set_charge(self, index: int, target: bool) -> None:
        if type(index) is not int or not 0 <= index < 2 or type(target) is not bool:
            raise ServiceValidationError("Invalid backup entry or charging target")
        async with self._operation("charge", target):
            await self._set("charge", index, target)

    async def async_set_all_sources(self, target: str) -> dict[str, Any]:
        """Explicit all-circuit action. Stop on first failure; never roll back."""
        if target not in ("grid", "battery"):
            raise ServiceValidationError("Invalid source")
        async with self._operation("source", target, batch=True):
            for channel in CIRCUIT_ORDER:
                await self._set("source", channel - 1, target, batch=True)
                self._status(completed=[*self.status["completed"], channel])
                await sleep(SETTLE_SECONDS)
        return dict(self.status)

    async def async_cancel(self, *, shutdown: bool = False) -> None:
        """Stop future writes, including queued callers; no compensating commands."""
        if shutdown:
            self._closed = True
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
