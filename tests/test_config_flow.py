"""Tests for the CTEK Battery Sense config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError
from custom_components.ctek_battery_sense.const import (
    CONF_CAPACITY_AH,
    CONF_SENDER_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from home_assistant_bluetooth import BluetoothServiceInfoBleak
from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from ctek_battery_sense import SERVICE_UUID, CTEKPairingError

ADDRESS = "AA:BB:CC:DD:EE:FF"
SENDER_ID = "Z99TEST0001"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def service_info(*, connectable: bool = True) -> BluetoothServiceInfoBleak:
    """Return synthetic CTEK discovery data."""

    device = BLEDevice(ADDRESS, "CTEK", {})
    advertisement = AdvertisementData(
        local_name="CTEK",
        manufacturer_data={},
        service_data={},
        service_uuids=[SERVICE_UUID],
        tx_power=None,
        rssi=-70,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak(
        name="CTEK",
        address=ADDRESS,
        rssi=-70,
        manufacturer_data={},
        service_data={},
        service_uuids=[SERVICE_UUID],
        source="test",
        device=device,
        advertisement=advertisement,
        connectable=connectable,
        time=0,
        tx_power=None,
    )


async def test_bluetooth_flow_success(hass: HomeAssistant) -> None:
    """Test successful Bluetooth discovery and validation."""

    discovery = service_info()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=discovery,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    with (
        patch(
            "custom_components.ctek_battery_sense.config_flow.bluetooth.async_ble_device_from_address",
            return_value=discovery.device,
        ),
        patch(
            "custom_components.ctek_battery_sense.config_flow.close_stale_connections_by_address",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.ctek_battery_sense.config_flow.CTEKBatterySense.async_validate",
            new=AsyncMock(),
        ) as validate,
        patch(
            "custom_components.ctek_battery_sense.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SENDER_ID: SENDER_ID.lower(), CONF_CAPACITY_AH: 70},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"CTEK {SENDER_ID}"
    assert result["data"] == {
        CONF_SENDER_ID: SENDER_ID,
        CONF_CAPACITY_AH: 70,
    }
    assert result["result"].unique_id == ADDRESS
    validate.assert_awaited_once()


@pytest.mark.parametrize(
    ("discoveries", "reason"),
    [
        ([], "no_devices_found"),
        ([service_info(connectable=False)], "no_connectable_devices"),
    ],
)
async def test_user_flow_without_connectable_device(
    hass: HomeAssistant,
    discoveries: list[BluetoothServiceInfoBleak],
    reason: str,
) -> None:
    """Test manual setup when no connectable monitor is available."""

    with patch(
        "custom_components.ctek_battery_sense.config_flow.async_discovered_service_info",
        return_value=discoveries,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_user_flow_selects_connectable_device(hass: HomeAssistant) -> None:
    """Test selecting a discovered monitor during manual setup."""

    discovery = service_info()
    with patch(
        "custom_components.ctek_battery_sense.config_flow.async_discovered_service_info",
        return_value=[discovery],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"


async def test_invalid_sender_id(hass: HomeAssistant) -> None:
    """Test that a malformed Sender ID does not attempt a connection."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info(),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SENDER_ID: "invalid", CONF_CAPACITY_AH: 70},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {CONF_SENDER_ID: "invalid_sender_id"}


async def test_monitor_disappears_before_validation(hass: HomeAssistant) -> None:
    """Test a monitor going out of range before credentials are validated."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info(),
    )
    with patch(
        "custom_components.ctek_battery_sense.config_flow.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SENDER_ID: SENDER_ID, CONF_CAPACITY_AH: 70},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_found"}


@pytest.mark.parametrize(
    ("error", "flow_error"),
    [
        (CTEKPairingError("pairing failed"), "pairing_failed"),
        (BleakError("connection failed"), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (ValueError("authentication failed"), "invalid_auth"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
async def test_validation_errors(
    hass: HomeAssistant, error: Exception, flow_error: str
) -> None:
    """Test connection and validation error mapping."""

    discovery = service_info()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=discovery,
    )
    with (
        patch(
            "custom_components.ctek_battery_sense.config_flow.bluetooth.async_ble_device_from_address",
            return_value=discovery.device,
        ),
        patch(
            "custom_components.ctek_battery_sense.config_flow.close_stale_connections_by_address",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.ctek_battery_sense.config_flow.CTEKBatterySense.async_validate",
            new=AsyncMock(side_effect=error),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SENDER_ID: SENDER_ID, CONF_CAPACITY_AH: 70},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": flow_error}


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test that the same Bluetooth address cannot be configured twice."""

    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test updating battery capacity and polling interval."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        data={CONF_SENDER_ID: SENDER_ID, CONF_CAPACITY_AH: 70},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_CAPACITY_AH: 80, CONF_UPDATE_INTERVAL: 60},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_CAPACITY_AH: 80, CONF_UPDATE_INTERVAL: 60}
    reload.assert_awaited_once_with(entry.entry_id)


async def test_options_flow_default_interval(hass: HomeAssistant) -> None:
    """Test the default interval is exposed for an existing entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        data={CONF_SENDER_ID: SENDER_ID, CONF_CAPACITY_AH: 70},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    schema = result["data_schema"]
    defaults = {str(key): key.default() for key in schema.schema}
    assert defaults[CONF_UPDATE_INTERVAL] == DEFAULT_UPDATE_INTERVAL
    assert CONF_ADDRESS not in defaults
