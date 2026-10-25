"""Shared polling with current-response semantics and bounded failure backoff."""

import json
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, EcoFlowClient, EcoFlowError, RateLimitError
from .catalog import Catalog
from .const import (
    CONF_ACCESS_KEY,
    CONF_POLL_INTERVAL,
    CONF_SECRET_KEY,
    CONF_SERIAL,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    MAX_POLL_INTERVAL_SECONDS,
    MIN_POLL_INTERVAL_SECONDS,
)
from .controls import PanelControls, read_control_states
from .quota import (
    MAX_ENTITIES,
    QuotaLimitError,
    RawPath,
    Snapshot,
    extract_leaves,
    identity,
    safe_key,
)

_LOGGER = logging.getLogger(__name__)


class EcoFlowCoordinator(DataUpdateCoordinator[Snapshot]):
    """All entities consume one quota/all request per polling cycle."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: EcoFlowClient, catalog: Catalog
    ) -> None:
        self.client = client
        self.catalog = catalog
        self.serial = entry.data[CONF_SERIAL]
        self.unique_prefix = f"{self.serial}:quota:"
        self._sensitive = tuple(
            entry.data[k] for k in (CONF_ACCESS_KEY, CONF_SECRET_KEY, CONF_SERIAL)
        )
        self.known_paths: set[RawPath] = set()
        self.registry_limit_reached = False
        # Persist only identities in HA's registry. No quota values or private store.
        for registered in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
            if registered.unique_id.startswith(self.unique_prefix):
                try:
                    path = tuple(json.loads(registered.unique_id[len(self.unique_prefix) :]))
                    if path and all(
                        (type(p) is int and 0 <= p < 128) or safe_key(p, self._sensitive)
                        for p in path
                    ):
                        self.known_paths.add(path)
                except ValueError, TypeError:
                    continue
        interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL_SECONDS)
        self.poll_interval = (
            min(MAX_POLL_INTERVAL_SECONDS, max(MIN_POLL_INTERVAL_SECONDS, interval))
            if type(interval) is int
            else DEFAULT_POLL_INTERVAL_SECONDS
        )
        self.failures = 0
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.poll_interval),
        )
        self.controls = PanelControls(self)

    async def async_shutdown(self) -> None:
        """Cancel commands before unloading or shutting down; never restore targets."""
        await self.controls.async_cancel(shutdown=True)
        await super().async_shutdown()

    def async_control_error(self, error: Exception) -> None:
        """Invalidate telemetry after an unconfirmed write without leaking payloads."""
        if isinstance(error, RateLimitError):
            self.update_interval = timedelta(seconds=error.retry_after)
        self.async_set_update_error(UpdateFailed("EcoFlow control outcome unconfirmed"))

    async def async_control_refresh(self) -> Snapshot:
        """Bypass the refresh debouncer/cache for every pre/post-command read."""
        try:
            snapshot = await self._async_update_data()
        except ConfigEntryAuthFailed:
            self.config_entry.async_start_reauth(self.hass)
            raise
        self.async_set_updated_data(snapshot)
        return snapshot

    def unique_id(self, path: RawPath) -> str:
        return self.unique_prefix + identity(path)

    async def _async_update_data(self) -> Snapshot:
        try:
            data = await self.client.get_quota_all()
            snapshot = extract_leaves(data, self._sensitive)
        except AuthenticationError:
            raise ConfigEntryAuthFailed("EcoFlow authentication rejected") from None
        except (EcoFlowError, QuotaLimitError) as error:
            self.failures = min(self.failures + 1, 5)
            seconds = min(900, self.poll_interval * 2**self.failures)
            if isinstance(error, RateLimitError):
                seconds = max(seconds, error.retry_after)
            self.update_interval = timedelta(seconds=seconds)
            raise UpdateFailed(str(error)) from None
        self.failures = 0
        self.update_interval = timedelta(seconds=self.poll_interval)
        # A registry-backed lifetime cap also applies across restarts/key churn.
        for path in sorted(snapshot.leaves, key=identity):
            if path in self.known_paths:
                continue
            if len(self.known_paths) >= MAX_ENTITIES:
                self.registry_limit_reached = True
                break
            self.known_paths.add(path)
        return Snapshot(
            {path: value for path, value in snapshot.leaves.items() if path in self.known_paths},
            snapshot.excluded,
            read_control_states(data),
        )
