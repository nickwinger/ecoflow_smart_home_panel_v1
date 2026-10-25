"""Optional, bounded batch-failure notifications using Home Assistant only."""

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import CONF_BATCH_NOTIFICATIONS, DOMAIN, NAME


def notification_id(entry: ConfigEntry, target: str) -> str:
    """Use the HA entry identity, never credentials or a device serial."""
    return f"{DOMAIN}.{entry.entry_id}.batch_{target}"


@callback
def async_batch_failed(
    hass: HomeAssistant, entry: ConfigEntry, target: str, completed: list[int]
) -> None:
    """Create/update one message per entry and target after the complete sequence."""
    if entry.options.get(CONF_BATCH_NOTIFICATIONS) is not True:
        return
    unconfirmed = ", ".join(str(channel) for channel in range(1, 11) if channel not in completed)
    if hass.config.language == "de":
        source = "Netzstrom" if target == "grid" else "Batterie"
        title = f"{NAME}: Umschaltung fehlgeschlagen"
        message = (
            f"Die Umschaltung aller Stromkreise auf **{source}** wurde nicht vollständig bestätigt.\n\n"
            f"**Nicht bestätigte Stromkreise: {unconfirmed}.**\n\n"
            "Die Schaltfolge ist beendet. Eine aufrufende Automation meldet einen Fehler. "
            "Es wurde nicht automatisch zurückgeschaltet. Prüfe die Zustände und "
            "**Einstellungen → System → Protokolle**, bevor du erneut umschaltest.\n\n"
            "Nach einer vollständig erfolgreichen Sammelschaltung zum selben Ziel "
            "wird diese Meldung automatisch entfernt.\n\n"
            f"Integrationseintrag: `{entry.entry_id[:8]}`"
        )
    else:
        source = "grid" if target == "grid" else "battery"
        title = f"{NAME}: Switching failed"
        message = (
            f"Switching all circuits to **{source}** was not fully confirmed.\n\n"
            f"**Unconfirmed circuits: {unconfirmed}.**\n\n"
            "The sequence has ended. A calling automation receives an error. "
            "No automatic rollback was performed. Check the states and "
            "**Settings → System → Logs** before switching again.\n\n"
            "This notification is removed automatically after a fully successful "
            "all-circuit sequence to the same target.\n\n"
            f"Integration entry: `{entry.entry_id[:8]}`"
        )
    persistent_notification.async_create(
        hass, message, title=title, notification_id=notification_id(entry, target)
    )


@callback
def async_batch_succeeded(hass: HomeAssistant, entry: ConfigEntry, target: str) -> None:
    """Only success for this target resolves its notification."""
    persistent_notification.async_dismiss(hass, notification_id(entry, target))


@callback
def async_clear_notifications(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear this entry's two messages when the option is disabled or entry removed."""
    for target in ("grid", "battery"):
        async_batch_succeeded(hass, entry, target)
