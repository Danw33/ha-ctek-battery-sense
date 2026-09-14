"""Diagnostics for CTEK Battery Sense."""

from dataclasses import asdict
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_SENDER_ID
from .coordinator import CTEKConfigEntry

_ENTRY_FIELDS_TO_REDACT = {CONF_SENDER_ID, "discovery_keys"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CTEKConfigEntry
) -> dict[str, Any]:
    """Return privacy-redacted diagnostics."""

    coordinator = entry.runtime_data
    entry_data = async_redact_data(entry.as_dict(), _ENTRY_FIELDS_TO_REDACT)
    entry_data["title"] = REDACTED
    entry_data["unique_id"] = REDACTED
    service_info = bluetooth.async_last_service_info(
        hass, coordinator.address, connectable=True
    )

    return {
        "entry": entry_data,
        "data": asdict(coordinator.data),
        "capacity_ah": coordinator.capacity_ah,
        "update_interval_minutes": coordinator.update_interval_minutes,
        "last_update_success": coordinator.last_update_success,
        "last_exception_type": (
            type(coordinator.last_exception).__name__
            if coordinator.last_exception
            else None
        ),
        "service_info": (
            {
                "address": REDACTED,
                "source": REDACTED,
                "connectable": service_info.connectable,
                "rssi": service_info.rssi,
                "service_uuids": service_info.service_uuids,
                "time": service_info.time,
            }
            if service_info
            else None
        ),
    }
