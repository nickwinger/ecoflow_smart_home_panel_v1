"""Explicit, serialized commands using the working SHP v1 reference protocol.

Only fresh quota can confirm a command. No restored state, cache or PUT reply
can prove success. Timings and circuit order follow shp_mode.py.
"""

from __future__ import annotations

import asyncio
import logging
from asyncio import sleep
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .api import AuthenticationError, quota_member
from .const import CONF_BATCH_CONTROLS, CONF_CHARGE_CONTROLS, CONF_SOURCE_CONTROLS, DOMAIN
from .logging_utils import failure_reason
from .quota import Snapshot

if TYPE_CHECKING:
    from .coordinator import EcoFlowCoordinator

CIRCUIT_ORDER = (7, 6, 3, 1, 2, 4, 5, 8, 9, 10)
SETTLE_SECONDS = 10
CHARGE_SETTLE_SECONDS = 2  # ecoflow_config.SETTLE_AFTER_SET_SECONDS for ecoflow_set.py
RETRY_SECONDS = 15
MAX_ATTEMPTS = 8
_LOGGER = logging.getLogger(__name__)


class BatchSwitchError(HomeAssistantError):
    """All circuits were processed, but some targets remain unconfirmed."""


def read_batch_sources(data: dict[str, Any]) -> tuple[str | None, ...]:
    """Match shp_mode.py's per-channel lookup and int conversion exactly.

    The owner requires the working batch semantics: dotted list first, positional
    item first, ch fallback only if that item is absent, ctrlSta before sta.
    This decoder is only for batch confirmation, not raw entities or other controls.
    """
    items = data.get("heartbeat.loadCmdChCtrlInfos")
    if not isinstance(items, list):
        heartbeat = data.get("heartbeat")
        items = heartbeat.get("loadCmdChCtrlInfos") if isinstance(heartbeat, dict) else None
    if not isinstance(items, list):
        return (None,) * 10
    states = []
    for index in range(10):
        item = items[index] if index < len(items) and isinstance(items[index], dict) else None
        if item is None:
            for candidate in items:
                if not isinstance(candidate, dict):
                    continue
                try:
                    if int(candidate.get("ch")) == index:
                        item = candidate
                        break
                except TypeError, ValueError, OverflowError:
                    continue
        try:
            value = int(item.get("ctrlSta", item.get("sta"))) if item is not None else None
        except TypeError, ValueError, OverflowError:
            value = None
        states.append({0: "grid", 1: "battery"}.get(value))
    return tuple(states)


def read_control_states(data: dict[str, Any]) -> dict[str, tuple[str | bool | None, ...]]:
    """Derive strict individual states and reference-compatible batch states.

    ctrlSta wins; sta is the reference fallback only when ctrlSta is absent.
    Never coerce invalid types or invent channel mapping from powCh.
    """
    result = {}
    for kind, array, size in (
        ("source", "loadCmdChCtrlInfos", 10),
        ("mode", "loadCmdChCtrlInfos", 10),
        ("load_state", "loadCmdChCtrlInfos", 10),
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
                isinstance(item, dict)
                and ("ctrlMode" in item if kind == "mode" else "ctrlSta" in item or "sta" in item)
                for item in items
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
        mapping = {
            "source": {0: "grid", 1: "battery"},
            "mode": {0: "automatic", 1: "manual"},
            "load_state": {0: "grid", 1: "battery", 2: "off"},
            "charge": {0: False, 1: False, 2: True},
        }[kind]
        values = [
            item.get("ctrlMode") if kind == "mode" else item.get("ctrlSta", item.get("sta"))
            for item in items
        ]
        result[kind] = tuple(mapping.get(value) if type(value) is int else None for value in values)
    result["batch_source"] = read_batch_sources(data)
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
        key = CONF_SOURCE_CONTROLS if kind in ("source", "mode") else CONF_CHARGE_CONTROLS
        return not self._closed and options.get(key) is True

    def batch_enabled(self) -> bool:
        return (
            self.enabled("source")
            and self.coordinator.config_entry.options.get(CONF_BATCH_CONTROLS) is True
        )

    def _require_enabled(self, kind: str, batch: bool = False) -> None:
        if not self.enabled(kind) or (
            batch and self.coordinator.config_entry.options.get(CONF_BATCH_CONTROLS) is not True
        ):
            raise ServiceValidationError("EcoFlow control is not enabled in integration options")

    def _status(self, **values: Any) -> None:
        self.status = {**self.status, **values}
        self.coordinator.async_update_listeners()

    def _log_channel_failure(self, error: Exception, *, batch: bool) -> None:
        """Log only validated targets, bounded progress and an allowlisted cause."""
        _LOGGER.error(
            "EcoFlow entry %s: %s %s -> %s failed during %s (attempt %s/%s): %s.%s",
            self.coordinator.config_entry.entry_id[:8],
            "backup charging"
            if self.status["kind"] == "charge"
            else "circuit " + self.status["kind"],
            self.status.get("channel", "not started"),
            self.status["target"],
            self.status.get("stage", "preflight"),
            self.status.get("attempt", 0),
            MAX_ATTEMPTS,
            failure_reason(error),
            " Continuing with remaining circuits after the normal pause." if batch else "",
        )

    def _log_unconfirmed(self, attempt: int) -> None:
        _LOGGER.log(
            logging.WARNING if attempt == 1 else logging.DEBUG,
            "EcoFlow entry %s: %s %s -> %s not yet confirmed (attempt %s/%s); following the configured retry sequence",
            self.coordinator.config_entry.entry_id[:8],
            "backup charging"
            if self.status["kind"] == "charge"
            else "circuit " + self.status["kind"],
            self.status["channel"],
            self.status["target"],
            attempt,
            MAX_ATTEMPTS,
        )

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
                    "failed": [],
                    "stage": "preflight",
                }
                self._status()
                _LOGGER.info(
                    "EcoFlow entry %s: starting %s%s -> %s",
                    self.coordinator.config_entry.entry_id[:8],
                    "all-circuit " if batch else "",
                    kind,
                    target,
                )
                try:
                    yield
                except asyncio.CancelledError:
                    self._status(state="cancelled")
                    _LOGGER.warning(
                        "EcoFlow entry %s: %s -> %s cancelled; confirmed circuits=%s, failed circuits=%s, last channel=%s; an already sent command may still take effect",
                        self.coordinator.config_entry.entry_id[:8],
                        kind,
                        target,
                        self.status["completed"],
                        self.status["failed"],
                        self.status.get("channel", "not started"),
                    )
                    self.coordinator.async_control_error(
                        HomeAssistantError("EcoFlow command cancelled; device outcome unconfirmed")
                    )
                    raise
                except Exception as error:
                    self._status(state="failed")
                    self.coordinator.async_control_error(error)
                    if isinstance(error, AuthenticationError):
                        self.coordinator.config_entry.async_start_reauth(self.coordinator.hass)
                    if isinstance(error, BatchSwitchError):
                        _LOGGER.error(
                            "EcoFlow entry %s: all-circuit switching -> %s finished with failures; confirmed circuits=%s; unconfirmed circuits=%s",
                            self.coordinator.config_entry.entry_id[:8],
                            target,
                            self.status["completed"],
                            self.status["failed"],
                        )
                        raise
                    self._log_channel_failure(error, batch=False)
                    raise HomeAssistantError(
                        "EcoFlow command failed; target was not confirmed"
                    ) from None
                else:
                    self._status(state="succeeded", stage="complete")
                    _LOGGER.info(
                        "EcoFlow entry %s: %s%s -> %s completed and confirmed; channel=%s, confirmed circuits=%s",
                        self.coordinator.config_entry.entry_id[:8],
                        "all-circuit " if batch else "",
                        kind,
                        target,
                        self.status.get("channel", "not started"),
                        self.status["completed"],
                    )
        finally:
            self._tasks.discard(task)

    async def _set(self, kind: str, index: int, target: str | bool, *, batch: bool = False) -> None:
        state_kind = "batch_source" if batch else kind
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
            self._status(channel=index + 1, attempt=attempt, stage="preflight")
            snapshot = await self.coordinator.async_control_refresh()
            if control_state(snapshot, state_kind, index) == target:
                return
            self._require_enabled(kind, batch)
            self._status(stage="write")
            await self.coordinator.client.put_quota(params)
            self._status(stage="settle")
            await sleep(SETTLE_SECONDS if kind == "source" else CHARGE_SETTLE_SECONDS)
            self._status(stage="verify")
            snapshot = await self.coordinator.async_control_refresh()
            if control_state(snapshot, state_kind, index) == target:
                return
            self._log_unconfirmed(attempt)
            if batch or attempt < MAX_ATTEMPTS:
                self._status(stage="retry wait")
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

    async def async_set_mode(self, index: int, target: str) -> None:
        """Select automatic routing or hold the freshly observed supply manually.

        Automatic uses the reference's ctrlMode=0, sta=0 command. It hands
        routing back to the panel; the source can legitimately change afterwards.
        Never fill a missing supply state with a guessed default.
        """
        if type(index) is not int or not 0 <= index < 10 or target not in ("automatic", "manual"):
            raise ServiceValidationError("Invalid circuit or control mode")
        async with self._operation("mode", target):
            for attempt in range(1, MAX_ATTEMPTS + 1):
                self._require_enabled("mode")
                self._status(channel=index + 1, attempt=attempt, stage="preflight")
                snapshot = await self.coordinator.async_control_refresh()
                if control_state(snapshot, "mode", index) == target:
                    return
                source = control_state(snapshot, "load_state", index)
                if target == "manual" and source not in ("grid", "battery", "off"):
                    raise HomeAssistantError("Current circuit supply state is unknown")
                self._require_enabled("mode")
                self._status(stage="write")
                await self.coordinator.client.put_quota(
                    {
                        "cmdSet": 11,
                        "id": 16,
                        "ch": index,
                        "ctrlMode": int(target == "manual"),
                        "sta": 0
                        if target == "automatic"
                        else {"grid": 0, "battery": 1, "off": 2}[source],
                    }
                )
                self._status(stage="settle")
                await sleep(SETTLE_SECONDS)
                self._status(stage="verify")
                snapshot = await self.coordinator.async_control_refresh()
                if control_state(snapshot, "mode", index) == target:
                    return
                self._log_unconfirmed(attempt)
                if attempt < MAX_ATTEMPTS:
                    self._status(stage="retry wait")
                    await sleep(RETRY_SECONDS)
            raise HomeAssistantError("EcoFlow control mode not confirmed after eight attempts")

    async def async_set_all_sources(self, target: str) -> dict[str, Any]:
        """Run shp_mode's complete ordered sequence and report failures at the end."""
        if target not in ("grid", "battery"):
            raise ServiceValidationError("Invalid source")
        async with self._operation("source", target, batch=True):
            for channel in CIRCUIT_ORDER:
                self._require_enabled("source", batch=True)
                try:
                    await self._set("source", channel - 1, target, batch=True)
                except Exception as error:  # Same per-channel boundary as shp_mode.run_mode.
                    self._status(failed=[*self.status["failed"], channel])
                    self._log_channel_failure(error, batch=True)
                    self.coordinator.async_control_error(error)
                    if isinstance(error, AuthenticationError):
                        self.coordinator.config_entry.async_start_reauth(self.coordinator.hass)
                else:
                    self._status(completed=[*self.status["completed"], channel])
                self._status(stage="channel pause")
                await sleep(SETTLE_SECONDS)
            if self.status["failed"]:
                raise BatchSwitchError(
                    translation_domain=DOMAIN,
                    translation_key="batch_failed",
                    translation_placeholders={
                        "channels": ", ".join(map(str, self.status["failed"]))
                    },
                )
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
