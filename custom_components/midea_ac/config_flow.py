"""Config flow for Midea Smart AC."""
from __future__ import annotations

from typing import Any, Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from msmart.const import DeviceType
from msmart.device import AirConditioner as AC
from msmart.discover import Discover
from msmart.lan import AuthenticationError

from .const import (CONF_ADDITIONAL_OPERATION_MODES, CONF_BEEP, CONF_KEY,
                    CONF_MAX_CONNECTION_LIFETIME, CONF_SHOW_ALL_PRESETS,
                    CONF_TEMP_STEP, CONF_USE_FAN_ONLY_WORKAROUND, DOMAIN)

_DEFAULT_OPTIONS = {
    CONF_BEEP: True,
    CONF_TEMP_STEP: 1.0,
    CONF_USE_FAN_ONLY_WORKAROUND: False,
    CONF_SHOW_ALL_PRESETS: False,
    CONF_ADDITIONAL_OPERATION_MODES: None,
    CONF_MAX_CONNECTION_LIFETIME: None,
}


class MideaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Midea Smart AC."""

    async def async_step_user(self, _) -> FlowResult:
        """Handle a config flow initialized by the user."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["discover", "manual"],
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the discovery step of config flow."""
        errors = {}

        if user_input is not None:
            # If host was not provided, discover all devices
            if not (host := user_input.get(CONF_HOST)):
                return await self.async_step_pick_device()

            # Attempt to find specified device
            device = await Discover.discover_single(host, auto_connect=False, timeout=2)

            if device is None:
                errors["base"] = "device_not_found"
            elif device.type != DeviceType.AIR_CONDITIONER:
                errors["base"] = "unsupported_device"
            else:
                # Check if device has already been configured
                await self.async_set_unique_id(device.id)
                self._abort_if_unique_id_configured()

                # Finish connection
                if await Discover.connect(device):
                    return await self._create_entry_from_device(device)
                else:
                    # Indicate a connection could not be made
                    return self.async_abort(reason="cannot_connect")

        data_schema = vol.Schema({
            vol.Optional(CONF_HOST, default=""): str
        })

        return self.async_show_form(step_id="discover",
                                    data_schema=data_schema, errors=errors)

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the pick device step of config flow."""

        if user_input is not None:
            # Find selected device
            device = next(dev
                          for dev in self._discovered_devices
                          if dev.id == user_input[CONF_ID])

            if device:
                # Check if device has already been configured
                await self.async_set_unique_id(device.id)
                self._abort_if_unique_id_configured()

                # Finish connection
                if await Discover.connect(device):
                    return await self._create_entry_from_device(device)
                else:
                    # Indicate a connection could not be made
                    return self.async_abort(reason="cannot_connect")

        # Create a set of already configured devices by ID
        configured_devices = {
            entry.unique_id for entry in self._async_current_entries()
        }

        # Discover all devices
        self._discovered_devices = await Discover.discover(auto_connect=False, timeout=2)

        # Create dict of device ID to friendly name
        devices_name = {
            device.id: (
                f"{device.name} - {device.id} ({device.ip})"
            )
            for device in self._discovered_devices
            if (device.id not in configured_devices and
                device.type == DeviceType.AIR_CONDITIONER)
        }

        # Check if there is at least one device
        if len(devices_name) == 0:
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema({
            vol.Required(CONF_ID): vol.In(devices_name)
        })

        return self.async_show_form(step_id="pick_device",
                                    data_schema=data_schema)

    async def async_step_manual(self, user_input) -> FlowResult:
        """Handle the manual step of config flow."""
        errors = {}

        if user_input is not None:
            # Get device ID from user input
            id = int(user_input.get(CONF_ID))

            # Check if device has already been configured
            await self.async_set_unique_id(id)
            self._abort_if_unique_id_configured()

            # Attempt a connection to see if config is valid
            device = await self._test_manual_connection(user_input)

            if device:
                return await self._create_entry_from_device(device)

            # Indicate a connection could not be made
            errors["base"] = "cannot_connect"

        user_input = user_input or {}

        data_schema = vol.Schema({
            vol.Required(CONF_ID,
                         default=user_input.get(CONF_ID)): cv.string,
            vol.Required(CONF_HOST,
                         default=user_input.get(CONF_HOST)): cv.string,
            vol.Required(CONF_PORT,
                         default=user_input.get(CONF_PORT, 6444)): cv.port,
            vol.Optional(CONF_TOKEN,
                         description={"suggested_value": user_input.get(CONF_TOKEN, "")}): cv.string,
            vol.Optional(CONF_KEY,
                         description={"suggested_value": user_input.get(CONF_KEY, "")}): cv.string
        })

        return self.async_show_form(step_id="manual",
                                    data_schema=data_schema, errors=errors)

    async def _test_manual_connection(self, config) -> Optional[AC]:
        # Construct the device
        id = config.get(CONF_ID)
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        device = AC(ip=host, port=port, device_id=int(id))

        # Configure token and key as needed
        token = config.get(CONF_TOKEN)
        key = config.get(CONF_KEY)
        if token and key:
            try:
                await device.authenticate(token, key)
                success = True
            except AuthenticationError:
                success = False
        else:
            await device.refresh()
            success = device.online

        return device if success else None

    async def _create_entry_from_device(self, device) -> FlowResult:
        # Save the device into global data
        self.hass.data.setdefault(DOMAIN, {})

        # Populate config data
        data = {
            CONF_ID: device.id,
            CONF_HOST: device.ip,
            CONF_PORT: device.port,
            CONF_TOKEN: device.token,
            CONF_KEY: device.key,
        }

        # Create a config entry with the config data and default options
        return self.async_create_entry(title=f"{DOMAIN} {device.id}", data=data, options=_DEFAULT_OPTIONS)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return MideaOptionsFlow(config_entry)


class MideaOptionsFlow(OptionsFlow):
    """Options flow from Midea Smart AC."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle the first step of options flow."""
        if user_input is not None:
            # Confusingly, data argument in OptionsFlow is passed to async_setup_entry in the options member
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options

        data_schema = vol.Schema({
            vol.Optional(CONF_BEEP,
                         default=options.get(CONF_BEEP, True)): cv.boolean,
            vol.Optional(CONF_TEMP_STEP,
                         default=options.get(CONF_TEMP_STEP, 1.0)): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=5)),
            vol.Optional(CONF_USE_FAN_ONLY_WORKAROUND,
                         default=options.get(CONF_USE_FAN_ONLY_WORKAROUND, False)): cv.boolean,
            vol.Optional(CONF_SHOW_ALL_PRESETS,
                         default=options.get(CONF_SHOW_ALL_PRESETS, False)): cv.boolean,
            vol.Optional(CONF_ADDITIONAL_OPERATION_MODES,
                         description={"suggested_value": options.get(CONF_ADDITIONAL_OPERATION_MODES, None)}): cv.string,
            vol.Optional(CONF_MAX_CONNECTION_LIFETIME,
                         description={"suggested_value": options.get(CONF_MAX_CONNECTION_LIFETIME, None)}): vol.All(vol.Coerce(int), vol.Range(min=30)),
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)
