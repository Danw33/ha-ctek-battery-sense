"""Tests for CTEK Battery Sense sensor entities."""

from datetime import UTC, datetime

import pytest
from custom_components.ctek_battery_sense.const import (
    CONF_CAPACITY_AH,
    CONF_SENDER_ID,
    DOMAIN,
)
from custom_components.ctek_battery_sense.coordinator import CTEKCoordinator
from custom_components.ctek_battery_sense.models import CTEKData
from custom_components.ctek_battery_sense.sensor import (
    CTEKSensor,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

ADDRESS = "AA:BB:CC:DD:EE:FF"
SENDER_ID = "Z99TEST0001"
LAST_SYNC = datetime(2026, 9, 10, 10, tzinfo=UTC)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _setup_coordinator(hass: HomeAssistant) -> tuple[MockConfigEntry, CTEKCoordinator]:
    """Return an entry and coordinator containing representative data."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        data={CONF_SENDER_ID: SENDER_ID, CONF_CAPACITY_AH: 70},
    )
    coordinator = CTEKCoordinator(hass, entry)
    coordinator.last_successful_sync = LAST_SYNC
    coordinator.async_set_updated_data(
        CTEKData(
            voltage=12.5,
            temperature=20.5,
            state_of_charge=74,
            status="green",
            rssi=-72,
            uptime=600,
            sample_interval=5,
            history_cursor=2,
            history_records=100,
            last_successful_sync=LAST_SYNC,
        )
    )
    entry.runtime_data = coordinator
    return entry, coordinator


async def test_sensor_setup(hass: HomeAssistant) -> None:
    """Test all enabled and diagnostic sensors expose coordinator data."""

    entry, _coordinator = _setup_coordinator(hass)
    entities: list[CTEKSensor] = []
    await async_setup_entry(hass, entry, entities.extend)

    values = {entity.entity_description.key: entity.native_value for entity in entities}
    assert values == {
        "voltage": 12.5,
        "temperature": 20.5,
        "state_of_charge": 74,
        "status": "green",
        "signal_strength": -72,
        "uptime": 600,
        "history_records": 100,
        "sample_interval": 5,
        "last_successful_sync": LAST_SYNC,
    }
    assert all(entity.unique_id.startswith(SENDER_ID) for entity in entities)
    assert entities[0].device_info["identifiers"] == {(DOMAIN, SENDER_ID)}


async def test_last_sync_remains_available(hass: HomeAssistant) -> None:
    """Test only the last sync sensor remains available after an update failure."""

    entry, coordinator = _setup_coordinator(hass)
    entities: list[CTEKSensor] = []
    await async_setup_entry(hass, entry, entities.extend)
    coordinator.last_update_success = False

    by_key = {entity.entity_description.key: entity for entity in entities}
    assert by_key["last_successful_sync"].available
    assert not by_key["voltage"].available


async def test_last_sync_unavailable_before_first_update(hass: HomeAssistant) -> None:
    """Test the last sync sensor has no state before a successful update."""

    entry, coordinator = _setup_coordinator(hass)
    entities: list[CTEKSensor] = []
    await async_setup_entry(hass, entry, entities.extend)
    coordinator.last_successful_sync = None

    last_sync = next(
        entity
        for entity in entities
        if entity.entity_description.key == "last_successful_sync"
    )
    assert not last_sync.available
