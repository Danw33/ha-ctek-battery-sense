"""Tests for CTEK Battery Sense diagnostics."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from custom_components.ctek_battery_sense.const import (
    CONF_CAPACITY_AH,
    CONF_SENDER_ID,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from custom_components.ctek_battery_sense.coordinator import CTEKCoordinator
from custom_components.ctek_battery_sense.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.ctek_battery_sense.models import CTEKData
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery_flow import DiscoveryKey
from pytest_homeassistant_custom_component.common import MockConfigEntry

ADDRESS = "AA:BB:CC:DD:EE:FF"
SOURCE = "11:22:33:44:55:66"
SENDER_ID = "Z99TEST0001"
LAST_SYNC = datetime(2026, 9, 10, 10, tzinfo=UTC)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a loaded synthetic config entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"CTEK {SENDER_ID}",
        unique_id=ADDRESS,
        data={CONF_SENDER_ID: SENDER_ID, CONF_CAPACITY_AH: 70},
        discovery_keys={
            "bluetooth": (DiscoveryKey(domain="bluetooth", key=ADDRESS, version=1),)
        },
        options={CONF_UPDATE_INTERVAL: 60},
    )
    coordinator = CTEKCoordinator(hass, entry)
    coordinator.last_successful_sync = LAST_SYNC
    coordinator.async_set_updated_data(
        CTEKData(12.5, 20, 74, "green", -72, 600, 5, 2, 100, LAST_SYNC)
    )
    entry.runtime_data = coordinator
    return entry


async def test_diagnostics_redact_identifiers(hass: HomeAssistant) -> None:
    """Test diagnostics redact monitor and Bluetooth adapter identifiers."""

    entry = _entry(hass)
    service_info = MagicMock(
        address=ADDRESS,
        source=SOURCE,
        connectable=True,
        rssi=-72,
        service_uuids=["812ca8ed-a177-4d74-aefa-70098c5416af"],
        time=123.0,
    )
    with patch(
        "custom_components.ctek_battery_sense.diagnostics.bluetooth.async_last_service_info",
        return_value=service_info,
    ):
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    serialized = repr(diagnostics)
    assert SENDER_ID not in serialized
    assert ADDRESS not in serialized
    assert SOURCE not in serialized
    assert diagnostics["entry"]["title"] == "**REDACTED**"
    assert diagnostics["entry"]["unique_id"] == "**REDACTED**"
    assert diagnostics["entry"]["discovery_keys"] == "**REDACTED**"
    assert diagnostics["service_info"]["address"] == "**REDACTED**"
    assert diagnostics["service_info"]["source"] == "**REDACTED**"
    assert diagnostics["data"]["voltage"] == 12.5
    assert diagnostics["update_interval_minutes"] == 60
    assert diagnostics["last_exception_type"] is None


async def test_diagnostics_without_advertisement(hass: HomeAssistant) -> None:
    """Test diagnostics when no current Bluetooth source is available."""

    entry = _entry(hass)
    with patch(
        "custom_components.ctek_battery_sense.diagnostics.bluetooth.async_last_service_info",
        return_value=None,
    ):
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["service_info"] is None
