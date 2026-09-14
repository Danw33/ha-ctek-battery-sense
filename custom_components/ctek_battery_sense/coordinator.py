"""Data coordinator for CTEK Battery Sense."""

import logging
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, override

from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from ctek_battery_sense import (
    CTEKBatterySense,
    CTEKHistory,
    battery_status,
    calculate_soc,
)

from .const import (
    CONF_CAPACITY_AH,
    CONF_SENDER_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CAPACITY_AH,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .models import CTEKData

_LOGGER = logging.getLogger(__name__)
_STORAGE_VERSION = 1

type CTEKConfigEntry = ConfigEntry["CTEKCoordinator"]


async def async_remove_stored_history(hass: HomeAssistant, entry_id: str) -> None:
    """Remove locally cached history for a deleted config entry."""

    await Store[dict[str, Any]](
        hass, _STORAGE_VERSION, f"{DOMAIN}.{entry_id}"
    ).async_remove()


class CTEKCoordinator(DataUpdateCoordinator[CTEKData]):
    """Manage CTEK connection, history and calculated state."""

    config_entry: CTEKConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CTEKConfigEntry) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"CTEK {entry.data[CONF_SENDER_ID]}",
            update_interval=timedelta(minutes=self._configured_update_interval(entry)),
        )
        address = entry.unique_id
        assert address is not None
        self.address: str = address
        self.sender_id: str = entry.data[CONF_SENDER_ID]
        self._history = CTEKHistory()
        self.last_successful_sync: datetime | None = None
        self._store: Store[dict[str, Any]] = Store(
            hass, _STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )

    @staticmethod
    def _configured_update_interval(entry: CTEKConfigEntry) -> int:
        """Return the configured update interval in minutes."""

        return int(entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))

    @property
    def capacity_ah(self) -> float:
        """Return configured capacity."""

        return float(
            self.config_entry.options.get(
                CONF_CAPACITY_AH,
                self.config_entry.data.get(CONF_CAPACITY_AH, DEFAULT_CAPACITY_AH),
            )
        )

    @property
    def update_interval_minutes(self) -> int:
        """Return the configured update interval in minutes."""

        return self._configured_update_interval(self.config_entry)

    @override
    async def _async_setup(self) -> None:
        """Restore persisted voltage history."""

        stored = await self._store.async_load()
        if stored:
            try:
                self._history = CTEKHistory(
                    cursor=stored.get("cursor"),
                    sample_interval=stored.get("sample_interval"),
                    voltages=[float(value) for value in stored.get("voltages", [])],
                )
                if isinstance(last_sync := stored.get("last_successful_sync"), str):
                    self.last_successful_sync = dt_util.parse_datetime(last_sync)
            except TypeError, ValueError:
                _LOGGER.warning("Ignoring invalid stored CTEK history")
                self._history = CTEKHistory()
        if not bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        ):
            raise ConfigEntryNotReady(f"CTEK {self.address} is not in range")

    @override
    async def _async_update_data(self) -> CTEKData:
        """Fetch and calculate the latest device data."""

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(f"CTEK {self.address} is not in range")

        try:
            result = await CTEKBatterySense(ble_device, self.sender_id).async_read(
                self._history
            )
        except (BleakError, TimeoutError, ValueError) as err:
            raise UpdateFailed(f"Unable to read CTEK monitor: {err}") from err

        voltages = self._history.voltages or [result.voltage]
        soc = calculate_soc(
            voltages,
            capacity_ah=self.capacity_ah,
            sample_minutes=result.sample_interval,
        )
        status = battery_status(soc)
        last_successful_sync = dt_util.utcnow()
        await self._store.async_save(
            {
                **asdict(self._history),
                "last_successful_sync": last_successful_sync.isoformat(),
            }
        )
        self.last_successful_sync = last_successful_sync
        service_info = bluetooth.async_last_service_info(
            self.hass, self.address, connectable=True
        )
        return CTEKData(
            voltage=result.voltage,
            temperature=result.temperature,
            state_of_charge=soc,
            status=status,
            rssi=service_info.rssi if service_info else None,
            uptime=result.uptime,
            sample_interval=result.sample_interval,
            history_cursor=result.cursor,
            history_records=len(self._history.voltages),
            last_successful_sync=last_successful_sync,
        )
