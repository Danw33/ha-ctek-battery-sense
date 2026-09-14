"""CTEK Battery Sense integration."""

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothCallbackMatcher
from homeassistant.core import HomeAssistant, callback

from .const import PLATFORMS
from .coordinator import (
    CTEKConfigEntry,
    CTEKCoordinator,
    async_remove_stored_history,
)

_RECOVERY_RETRY_SECONDS = 5 * 60


async def async_setup_entry(hass: HomeAssistant, entry: CTEKConfigEntry) -> bool:
    """Set up a CTEK Battery Sense config entry."""

    coordinator = CTEKCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    last_recovery_attempt: float | None = None

    @callback
    def _async_device_seen(
        _service_info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ) -> None:
        """Refresh promptly when an unavailable monitor returns."""

        nonlocal last_recovery_attempt
        now = hass.loop.time()
        if coordinator.last_update_success or (
            last_recovery_attempt is not None
            and now - last_recovery_attempt < _RECOVERY_RETRY_SECONDS
        ):
            return
        last_recovery_attempt = now
        hass.async_create_task(
            coordinator.async_request_refresh(),
            f"Refresh returned CTEK {coordinator.address}",
        )

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_device_seen,
            BluetoothCallbackMatcher(address=coordinator.address, connectable=True),
            bluetooth.BluetoothScanningMode.ACTIVE,
            replay=bluetooth.BluetoothCallbackReplay.DISABLED,
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CTEKConfigEntry) -> bool:
    """Unload a CTEK Battery Sense config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: CTEKConfigEntry) -> None:
    """Remove data belonging to a deleted CTEK config entry."""

    await async_remove_stored_history(hass, entry.entry_id)
