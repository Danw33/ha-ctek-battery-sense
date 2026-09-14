"""Constants for the CTEK Battery Sense integration."""

from homeassistant.const import Platform

DOMAIN = "ctek_battery_sense"

CONF_SENDER_ID = "sender_id"
CONF_CAPACITY_AH = "capacity_ah"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_CAPACITY_AH = 75
MIN_CAPACITY_AH = 5
MAX_CAPACITY_AH = 200

DEFAULT_UPDATE_INTERVAL = 5
MIN_UPDATE_INTERVAL = 5
MAX_UPDATE_INTERVAL = 24 * 60

MANUFACTURER = "CTEK"
MODEL = "Battery Sense 40-149"

PLATFORMS = [Platform.SENSOR]
