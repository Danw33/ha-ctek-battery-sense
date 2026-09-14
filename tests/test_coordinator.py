"""Tests for the CTEK Battery Sense coordinator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from custom_components.ctek_battery_sense.const import (
    CONF_CAPACITY_AH,
    CONF_SENDER_ID,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from custom_components.ctek_battery_sense.coordinator import (
    CTEKCoordinator,
    async_remove_stored_history,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from ctek_battery_sense import (
    CTEKHistory,
    CTEKReadResult,
    battery_status,
    calculate_soc,
)

ADDRESS = "AA:BB:CC:DD:EE:FF"
SENDER_ID = "Z99TEST0001"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _coordinator(
    hass: HomeAssistant, *, options: dict | None = None
) -> CTEKCoordinator:
    """Return a coordinator backed by a synthetic config entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        data={CONF_SENDER_ID: SENDER_ID, CONF_CAPACITY_AH: 70},
        options=options or {},
    )
    return CTEKCoordinator(hass, entry)


async def test_setup_restores_history(hass: HomeAssistant) -> None:
    """Test persisted history and sync time are restored."""

    coordinator = _coordinator(hass)
    coordinator._store = MagicMock(
        async_load=AsyncMock(
            return_value={
                "cursor": 2,
                "sample_interval": 5,
                "voltages": [12.4, "12.5"],
                "last_successful_sync": "2026-09-10T10:00:00+00:00",
            }
        )
    )
    with patch(
        "custom_components.ctek_battery_sense.coordinator.bluetooth.async_ble_device_from_address",
        return_value=BLEDevice(ADDRESS, "CTEK", {}),
    ):
        await coordinator._async_setup()

    assert coordinator._history == CTEKHistory(
        cursor=2, sample_interval=5, voltages=[12.4, 12.5]
    )
    assert coordinator.last_successful_sync == datetime(2026, 9, 10, 10, tzinfo=UTC)


async def test_setup_ignores_invalid_history(hass: HomeAssistant) -> None:
    """Test corrupt persisted values are discarded safely."""

    coordinator = _coordinator(hass)
    coordinator._store = MagicMock(
        async_load=AsyncMock(
            return_value={"cursor": 2, "sample_interval": 5, "voltages": [None]}
        )
    )
    with patch(
        "custom_components.ctek_battery_sense.coordinator.bluetooth.async_ble_device_from_address",
        return_value=BLEDevice(ADDRESS, "CTEK", {}),
    ):
        await coordinator._async_setup()

    assert coordinator._history == CTEKHistory()


async def test_setup_restores_history_without_sync_time(hass: HomeAssistant) -> None:
    """Test persisted history without an earlier successful sync timestamp."""

    coordinator = _coordinator(hass)
    coordinator._store = MagicMock(
        async_load=AsyncMock(
            return_value={
                "cursor": 2,
                "sample_interval": 5,
                "voltages": [12.4],
            }
        )
    )
    with patch(
        "custom_components.ctek_battery_sense.coordinator.bluetooth.async_ble_device_from_address",
        return_value=BLEDevice(ADDRESS, "CTEK", {}),
    ):
        await coordinator._async_setup()

    assert coordinator._history == CTEKHistory(
        cursor=2, sample_interval=5, voltages=[12.4]
    )
    assert coordinator.last_successful_sync is None


async def test_setup_requires_connectable_device(hass: HomeAssistant) -> None:
    """Test setup is retried when no connection-capable source can see the device."""

    coordinator = _coordinator(hass)
    coordinator._store = MagicMock(async_load=AsyncMock(return_value=None))
    with (
        patch(
            "custom_components.ctek_battery_sense.coordinator.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(ConfigEntryNotReady, match="not in range"),
    ):
        await coordinator._async_setup()


async def test_update_data(hass: HomeAssistant) -> None:
    """Test a successful update calculates and persists all entity data."""

    coordinator = _coordinator(
        hass, options={CONF_CAPACITY_AH: 80, CONF_UPDATE_INTERVAL: 60}
    )
    store = MagicMock(async_save=AsyncMock())
    coordinator._store = store
    device = BLEDevice(ADDRESS, "CTEK", {})

    async def read(history: CTEKHistory) -> CTEKReadResult:
        history.cursor = 4
        history.sample_interval = 5
        history.voltages = [12.4, 12.5]
        return CTEKReadResult(
            voltage=12.5,
            temperature=20,
            uptime=600,
            sample_interval=5,
            cursor=4,
        )

    client = MagicMock(async_read=AsyncMock(side_effect=read))
    with (
        patch(
            "custom_components.ctek_battery_sense.coordinator.bluetooth.async_ble_device_from_address",
            return_value=device,
        ),
        patch(
            "custom_components.ctek_battery_sense.coordinator.bluetooth.async_last_service_info",
            return_value=MagicMock(rssi=-77),
        ),
        patch(
            "custom_components.ctek_battery_sense.coordinator.CTEKBatterySense",
            return_value=client,
        ),
    ):
        data = await coordinator._async_update_data()

    expected_soc = calculate_soc([12.4, 12.5], capacity_ah=80, sample_minutes=5)
    assert data.voltage == 12.5
    assert data.temperature == 20
    assert data.state_of_charge == expected_soc
    assert data.status == battery_status(expected_soc)
    assert data.rssi == -77
    assert data.history_cursor == 4
    assert data.history_records == 2
    assert coordinator.capacity_ah == 80
    assert coordinator.update_interval_minutes == 60
    assert coordinator.last_successful_sync == data.last_successful_sync
    saved = store.async_save.await_args.args[0]
    assert saved["cursor"] == 4
    assert saved["voltages"] == [12.4, 12.5]
    assert saved["last_successful_sync"] == data.last_successful_sync.isoformat()


async def test_update_without_service_info(hass: HomeAssistant) -> None:
    """Test an update remains valid if advertisement metadata has expired."""

    coordinator = _coordinator(hass)
    coordinator._store = MagicMock(async_save=AsyncMock())
    result = CTEKReadResult(12.5, 20, 600, 5, 4)
    with (
        patch(
            "custom_components.ctek_battery_sense.coordinator.bluetooth.async_ble_device_from_address",
            return_value=BLEDevice(ADDRESS, "CTEK", {}),
        ),
        patch(
            "custom_components.ctek_battery_sense.coordinator.bluetooth.async_last_service_info",
            return_value=None,
        ),
        patch(
            "custom_components.ctek_battery_sense.coordinator.CTEKBatterySense.async_read",
            new=AsyncMock(return_value=result),
        ),
    ):
        data = await coordinator._async_update_data()

    assert data.rssi is None


@pytest.mark.parametrize(
    "error", [BleakError("failed"), TimeoutError(), ValueError("invalid")]
)
async def test_update_errors(hass: HomeAssistant, error: Exception) -> None:
    """Test expected read failures mark coordinator data unavailable."""

    coordinator = _coordinator(hass)
    with (
        patch(
            "custom_components.ctek_battery_sense.coordinator.bluetooth.async_ble_device_from_address",
            return_value=BLEDevice(ADDRESS, "CTEK", {}),
        ),
        patch(
            "custom_components.ctek_battery_sense.coordinator.CTEKBatterySense.async_read",
            new=AsyncMock(side_effect=error),
        ),
        pytest.raises(UpdateFailed, match="Unable to read CTEK monitor"),
    ):
        await coordinator._async_update_data()


async def test_update_out_of_range(hass: HomeAssistant) -> None:
    """Test an absent device marks coordinator data unavailable."""

    coordinator = _coordinator(hass)
    with (
        patch(
            "custom_components.ctek_battery_sense.coordinator.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(UpdateFailed, match="not in range"),
    ):
        await coordinator._async_update_data()


async def test_remove_stored_history(hass: HomeAssistant) -> None:
    """Test stored history removal delegates to Home Assistant storage."""

    with patch.object(Store, "async_remove", new=AsyncMock()) as remove:
        await async_remove_stored_history(hass, "entry-id")

    remove.assert_awaited_once()
