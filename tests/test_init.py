"""Tests for CTEK Battery Sense setup and removal."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.ctek_battery_sense import (
    async_remove_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.ctek_battery_sense.const import (
    CONF_CAPACITY_AH,
    CONF_SENDER_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_returned_device_refresh_is_rate_limited(hass: HomeAssistant) -> None:
    """Test repeated advertisements only request one immediate refresh."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AA:BB:CC:DD:EE:FF",
        data={CONF_SENDER_ID: "Z99TEST0001", CONF_CAPACITY_AH: 70},
    )
    coordinator = MagicMock(
        address=entry.unique_id,
        last_update_success=False,
        async_config_entry_first_refresh=AsyncMock(),
        async_request_refresh=AsyncMock(),
    )
    unregister = MagicMock()
    with (
        patch(
            "custom_components.ctek_battery_sense.CTEKCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.ctek_battery_sense.bluetooth.async_register_callback",
            return_value=unregister,
        ) as register,
    ):
        assert await async_setup_entry(hass, entry)

    callback = register.call_args.args[1]
    callback(MagicMock(), MagicMock())
    callback(MagicMock(), MagicMock())
    await hass.async_block_till_done()

    coordinator.async_request_refresh.assert_awaited_once()


async def test_remove_entry_removes_cached_history(hass: HomeAssistant) -> None:
    """Test removing an entry also removes its stored history."""

    entry = MockConfigEntry(domain=DOMAIN)
    with patch(
        "custom_components.ctek_battery_sense.async_remove_stored_history",
        new=AsyncMock(),
    ) as remove_history:
        await async_remove_entry(hass, entry)

    remove_history.assert_awaited_once_with(hass, entry.entry_id)


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the sensor platform."""

    entry = MockConfigEntry(domain=DOMAIN)
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=True),
    ) as unload_platforms:
        assert await async_unload_entry(hass, entry)

    unload_platforms.assert_awaited_once()
