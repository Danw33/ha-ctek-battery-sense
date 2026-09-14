"""Config flow for CTEK Battery Sense."""

import logging
from typing import Any, override

import voluptuous as vol
from bleak.exc import BleakError
from bleak_retry_connector import close_stale_connections_by_address
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ADDRESS, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers import selector

from ctek_battery_sense import (
    SERVICE_UUID,
    CTEKBatterySense,
    CTEKPairingError,
    normalize_sender_id,
)

from .const import (
    CONF_CAPACITY_AH,
    CONF_SENDER_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CAPACITY_AH,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_CAPACITY_AH,
    MAX_UPDATE_INTERVAL,
    MIN_CAPACITY_AH,
    MIN_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class CTEKConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle CTEK Battery Sense configuration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""

        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> CTEKOptionsFlow:
        """Return the options flow."""

        return CTEKOptionsFlow()

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {
            "name": f"CTEK ({discovery_info.address})"
        }
        return await self.async_step_credentials()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select a discovered CTEK monitor."""

        if user_input is not None:
            self._discovery = self._discovered[user_input[CONF_ADDRESS]]
            await self.async_set_unique_id(
                self._discovery.address, raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            return await self.async_step_credentials()

        current_ids = self._async_current_ids(include_ignore=False)
        seen_ctek_devices = [
            info
            for info in async_discovered_service_info(self.hass)
            if info.address not in current_ids
            and SERVICE_UUID in (uuid.lower() for uuid in info.service_uuids)
        ]
        self._discovered = {
            info.address: info for info in seen_ctek_devices if info.connectable
        }
        if not self._discovered:
            if seen_ctek_devices:
                return self.async_abort(reason="no_connectable_devices")
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: f"{info.name} ({address}, {info.rssi} dBm)"
                            for address, info in self._discovered.items()
                        }
                    )
                }
            ),
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect Sender ID and battery capacity, then test the connection."""

        assert self._discovery is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                normalized_sender_id = normalize_sender_id(user_input[CONF_SENDER_ID])
            except ValueError:
                errors[CONF_SENDER_ID] = "invalid_sender_id"
            else:
                ble_device = bluetooth.async_ble_device_from_address(
                    self.hass, self._discovery.address, connectable=True
                )
                if ble_device is None:
                    errors["base"] = "not_found"
                else:
                    await close_stale_connections_by_address(self._discovery.address)
                    try:
                        await CTEKBatterySense(
                            ble_device, normalized_sender_id
                        ).async_validate()
                    except CTEKPairingError:
                        _LOGGER.debug("CTEK pairing failed", exc_info=True)
                        errors["base"] = "pairing_failed"
                    except BleakError, TimeoutError:
                        _LOGGER.debug("CTEK connection failed", exc_info=True)
                        errors["base"] = "cannot_connect"
                    except ValueError:
                        _LOGGER.debug("CTEK authentication failed", exc_info=True)
                        errors["base"] = "invalid_auth"
                    except Exception:
                        _LOGGER.exception("Unexpected CTEK validation error")
                        errors["base"] = "unknown"
                    else:
                        return self.async_create_entry(
                            title=f"CTEK {normalized_sender_id}",
                            data={
                                CONF_SENDER_ID: normalized_sender_id,
                                CONF_CAPACITY_AH: user_input[CONF_CAPACITY_AH],
                            },
                        )

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SENDER_ID): str,
                    vol.Required(
                        CONF_CAPACITY_AH, default=DEFAULT_CAPACITY_AH
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_CAPACITY_AH,
                            max=MAX_CAPACITY_AH,
                            step=1,
                            unit_of_measurement="Ah",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"address": self._discovery.address},
        )


class CTEKOptionsFlow(OptionsFlowWithReload):
    """Manage CTEK options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the battery capacity and polling interval."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self.config_entry.options.get(
            CONF_CAPACITY_AH,
            self.config_entry.data.get(CONF_CAPACITY_AH, DEFAULT_CAPACITY_AH),
        )
        current_update_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CAPACITY_AH, default=current): (
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=MIN_CAPACITY_AH,
                                max=MAX_CAPACITY_AH,
                                step=1,
                                unit_of_measurement="Ah",
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        )
                    ),
                    vol.Required(
                        CONF_UPDATE_INTERVAL, default=current_update_interval
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_UPDATE_INTERVAL,
                            max=MAX_UPDATE_INTERVAL,
                            step=5,
                            unit_of_measurement=UnitOfTime.MINUTES,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
