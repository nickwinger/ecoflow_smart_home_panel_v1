"""Shared polling with current-response semantics and bounded failure backoff."""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, EcoFlowClient, EcoFlowError, RateLimitError
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL_SECONDS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EcoFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """All entities consume one quota/all request per polling cycle."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: EcoFlowClient) -> None:
        self.client = client
        self.poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL_SECONDS)
        self.failures = 0
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.poll_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.get_quota_all()
        except AuthenticationError:
            raise ConfigEntryAuthFailed("EcoFlow authentication rejected") from None
        except EcoFlowError as error:
            self.failures = min(self.failures + 1, 5)
            seconds = min(900, self.poll_interval * 2**self.failures)
            if isinstance(error, RateLimitError):
                seconds = max(seconds, error.retry_after)
            self.update_interval = timedelta(seconds=seconds)
            raise UpdateFailed(str(error)) from None
        self.failures = 0
        self.update_interval = timedelta(seconds=self.poll_interval)
        return data
