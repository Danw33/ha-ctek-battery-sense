"""Sensor entities for CTEK Battery Sense."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import CTEKConfigEntry, CTEKCoordinator
from .models import CTEKData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CTEKSensorDescription(SensorEntityDescription):
    """Describe a CTEK sensor."""

    value_fn: Callable[[CTEKData], Any]


SENSORS: tuple[CTEKSensorDescription, ...] = (
    CTEKSensorDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.voltage,
    ),
    CTEKSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.temperature,
    ),
    CTEKSensorDescription(
        key="state_of_charge",
        translation_key="state_of_charge",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.state_of_charge,
    ),
    CTEKSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=["green", "amber", "red"],
        value_fn=lambda data: data.status,
    ),
    CTEKSensorDescription(
        key="signal_strength",
        translation_key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.rssi,
    ),
    CTEKSensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.uptime,
    ),
    CTEKSensorDescription(
        key="history_records",
        translation_key="history_records",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.history_records,
    ),
    CTEKSensorDescription(
        key="sample_interval",
        translation_key="sample_interval",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.sample_interval,
    ),
    CTEKSensorDescription(
        key="last_successful_sync",
        translation_key="last_successful_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.last_successful_sync,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CTEKConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up CTEK sensors."""

    async_add_entities(
        CTEKSensor(entry.runtime_data, description) for description in SENSORS
    )


class CTEKSensor(CoordinatorEntity[CTEKCoordinator], SensorEntity):
    """Representation of one CTEK sensor."""

    _attr_has_entity_name = True
    entity_description: CTEKSensorDescription

    def __init__(
        self, coordinator: CTEKCoordinator, description: CTEKSensorDescription
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.sender_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.sender_id)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=f"CTEK {coordinator.sender_id}",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    @override
    def native_value(self) -> Any:
        """Return the current sensor value."""

        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def available(self) -> bool:
        """Keep the last successful sync visible while the monitor is away."""

        if self.entity_description.key == "last_successful_sync":
            return self.coordinator.last_successful_sync is not None
        return super().available
