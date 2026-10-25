"""Allowlisted failure reasons; never render an exception's arbitrary contents."""

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import (
    AuthenticationError,
    EcoFlowError,
    InvalidResponseError,
    RateLimitError,
    UnsupportedDeviceError,
)
from .quota import QuotaLimitError


def failure_reason(error: Exception) -> str:
    """Return useful fixed text without credentials, URLs, response bodies or tracebacks."""
    # The coordinator wraps a classified transport failure; inspect its type only.
    if isinstance(error, UpdateFailed) and isinstance(
        error.__context__, (EcoFlowError, QuotaLimitError)
    ):
        error = error.__context__
    if isinstance(error, (AuthenticationError, ConfigEntryAuthFailed)):
        return "authentication rejected; reauthenticate the integration"
    if isinstance(error, RateLimitError):
        return "EcoFlow rate limit reached; requests wait for the cloud cooldown"
    if isinstance(error, UnsupportedDeviceError):
        return "supported Smart Home Panel v1 layout could not be confirmed"
    if isinstance(error, InvalidResponseError):
        return "invalid or rejected EcoFlow response"
    if isinstance(error, QuotaLimitError):
        return "quota response exceeds supported size or structure limits"
    if isinstance(error, EcoFlowError):
        return "EcoFlow request failed or timed out"
    if isinstance(error, ServiceValidationError):
        return "control request is invalid or no longer enabled"
    if isinstance(error, HomeAssistantError):
        return "requested state could not be confirmed from current quota"
    if isinstance(error, (OSError, TimeoutError)):
        return "connection failed or timed out"
    return "unexpected internal error"
