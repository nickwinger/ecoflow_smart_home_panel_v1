"""Native UI setup, options, credential replacement and reauthentication."""

import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    AuthenticationError,
    EcoFlowClient,
    EcoFlowError,
    InvalidResponseError,
    RateLimitError,
    UnsupportedDeviceError,
    validate_shp_v1,
)
from .const import (
    CONF_ACCESS_KEY,
    CONF_BATCH_CONTROLS,
    CONF_CHARGE_CONTROLS,
    CONF_CONFIRM_V1,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    CONF_SECRET_KEY,
    CONF_SERIAL,
    CONF_SOURCE_CONTROLS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    HOSTS,
    MAX_POLL_INTERVAL_SECONDS,
    MIN_POLL_INTERVAL_SECONDS,
    NAME,
)


def credential_schema(*, initial: bool) -> vol.Schema:
    """Never prefill secrets from an existing entry."""
    fields = {
        vol.Required(CONF_ACCESS_KEY): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_SECRET_KEY): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
    if initial:
        fields[vol.Required(CONF_SERIAL)] = str
        fields[vol.Required(CONF_REGION, default="eu")] = vol.In(HOSTS)
        fields[vol.Required(CONF_CONFIRM_V1, default=False)] = bool
    return vol.Schema(fields)


class EcoFlowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Only explicitly confirmed SHP v1 panels may be configured."""

    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EcoFlowOptionsFlow()

    async def _validate(self, data: dict[str, Any]) -> dict[str, str]:
        for key in (CONF_ACCESS_KEY, CONF_SECRET_KEY, CONF_SERIAL):
            if not isinstance(data.get(key), str) or not data[key].strip() or len(data[key]) > 256:
                return {"base": "invalid_input"}
            data[key] = data[key].strip()
            if any(ord(char) < 32 for char in data[key]):
                return {"base": "invalid_input"}
        data[CONF_SERIAL] = data[CONF_SERIAL].upper()
        if (
            not re.fullmatch(r"[A-Z0-9_-]{1,64}", data[CONF_SERIAL])
            or data.get(CONF_REGION) not in HOSTS
        ):
            return {"base": "invalid_input"}
        if not data.get(CONF_CONFIRM_V1):
            return {"base": "confirm_v1"}
        client = EcoFlowClient(
            async_get_clientsession(self.hass),
            data[CONF_ACCESS_KEY],
            data[CONF_SECRET_KEY],
            data[CONF_SERIAL],
            data[CONF_REGION],
        )
        try:
            validate_shp_v1(await client.get_quota_all())
        except AuthenticationError:
            return {"base": "invalid_auth"}
        except UnsupportedDeviceError:
            return {"base": "unsupported_device"}
        except RateLimitError:
            return {"base": "rate_limited"}
        except InvalidResponseError:
            return {"base": "invalid_response"}
        except EcoFlowError:
            return {"base": "cannot_connect"}
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            serial = data.get(CONF_SERIAL)
            if isinstance(serial, str) and serial.strip():
                await self.async_set_unique_id(serial.strip().upper())
                self._abort_if_unique_id_configured()
            errors = await self._validate(data)
            if not errors:
                return self.async_create_entry(title=NAME, data=data)
        return self.async_show_form(
            step_id="user", data_schema=credential_schema(initial=True), errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._replace_credentials(
            "reauth_confirm", self._get_reauth_entry(), user_input
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._replace_credentials(
            "reconfigure", self._get_reconfigure_entry(), user_input
        )

    async def _replace_credentials(
        self, step: str, entry: ConfigEntry, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                **entry.data,
                **{key: user_input[key] for key in (CONF_ACCESS_KEY, CONF_SECRET_KEY)},
            }
            errors = await self._validate(data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id=step, data_schema=credential_schema(initial=False), errors=errors
        )


class EcoFlowOptionsFlow(OptionsFlow):
    """Bounded polling and independently opted-in source, charge and batch writes."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            interval = user_input.get(CONF_POLL_INTERVAL)
            if (
                type(interval) is int
                and MIN_POLL_INTERVAL_SECONDS <= interval <= MAX_POLL_INTERVAL_SECONDS
            ):
                options = {CONF_POLL_INTERVAL: interval}
                for key in (CONF_SOURCE_CONTROLS, CONF_CHARGE_CONTROLS, CONF_BATCH_CONTROLS):
                    value = user_input.get(key, self.config_entry.options.get(key, False))
                    if type(value) is not bool:
                        errors["base"] = "invalid_controls"
                    options[key] = value
                if options[CONF_BATCH_CONTROLS] and not options[CONF_SOURCE_CONTROLS]:
                    errors["base"] = "batch_requires_source"
                if not errors:
                    return self.async_create_entry(title="", data=options)
            else:
                errors["base"] = "invalid_poll_interval"
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL_SECONDS
                        ),
                    ): vol.All(
                        int,
                        vol.Range(min=MIN_POLL_INTERVAL_SECONDS, max=MAX_POLL_INTERVAL_SECONDS),
                    ),
                    **{
                        vol.Optional(key, default=self.config_entry.options.get(key, False)): bool
                        for key in (CONF_SOURCE_CONTROLS, CONF_CHARGE_CONTROLS, CONF_BATCH_CONTROLS)
                    },
                }
            ),
        )
