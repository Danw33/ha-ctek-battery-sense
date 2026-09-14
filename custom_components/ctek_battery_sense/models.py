"""Data models for CTEK Battery Sense."""

from dataclasses import dataclass
from datetime import datetime

from ctek_battery_sense import BatteryStatus


@dataclass(frozen=True)
class CTEKData:
    """Latest decoded device data."""

    voltage: float
    temperature: float
    state_of_charge: float
    status: BatteryStatus
    rssi: int | None
    uptime: int
    sample_interval: int
    history_cursor: int
    history_records: int
    last_successful_sync: datetime
