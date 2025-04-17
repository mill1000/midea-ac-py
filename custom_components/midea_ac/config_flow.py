"""Config flow for Midea Smart AC."""
from __future__ import annotations

from typing import Any, Optional, cast

import homeassistant.helpers.config_validation as cv
import httpx
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (CONF_COUNTRY_CODE, CONF_HOST, CONF_ID,
                                 CONF_PORT, CONF_TOKEN)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import httpx_client
from homeassistant.helpers.selector import (CountrySelector,
                                            CountrySelectorConfig,
                                            SelectSelector,
                                            SelectSelectorConfig,
                                            SelectSelectorMode, TextSelector,
                                            TextSelectorConfig,
                                            TextSelectorType)
from msmart.const import DeviceType
from msmart.device import AirConditioner as AC
from msmart.discover import CloudError, Discover
from msmart.lan import AuthenticationError

from .const import (CONF_ADDITIONAL_OPERATION_MODES, CONF_BEEP,
                    CONF_CLOUD_COUNTRY_CODES, CONF_DEFAULT_CLOUD_COUNTRY,
                    CONF_ENERGY_FORMAT, CONF_FAN_SPEED_STEP, CONF_KEY,
                    CONF_MAX_CONNECTION_LIFETIME, CONF_SHOW_ALL_PRESETS,
                    CONF_SWING_ANGLE_RTL, CONF_TEMP_STEP,
                    CONF_USE_FAN_ONLY_WORKAROUND, DOMAIN, UPDATE_INTERVAL,
                    EnergyFormat)

_DEFAULT_OPTIONS = {
    CONF_BEEP: True,
    CONF_TEMP_STEP: 1.0,
    CONF_FAN_SPEED_STEP: 1,
    CONF_USE_FAN_ONLY_WORKAROUND: False,
    CONF_SHOW_ALL_PRESETS: False,
    CONF_ADDITIONAL_OPERATION_MODES: None,
    CONF_MAX_CONNECTION_LIFETIME: None,
    CONF_ENERGY_FORMAT: EnergyFormat.DEFAULT,
    CONF_SWING_ANGLE_RTL: False
}

_CLOUD_CREDENTIALS = {
    "DE": ("midea_eu@mailinator.com", "das_ist_passwort1"),
    "KR": ("midea_sea@mailinator.com", "password_for_sea1")
}


class MideaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Midea Smart AC."""

    VERSION = 1
    MINOR_VERSION = 3

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
            country_code = cast(str, user_input.get(CONF_COUNTRY_CODE))

            # If host was not provided, discover all devices
            if not (host := user_input.get(CONF_HOST)):
                return await self.async_step_pick_device(country_code=country_code)

            # Get credentials for region
            account, password = _CLOUD_CREDENTIALS.get(
                country_code, (None, None))

            # Attempt to find specified device
            device = await Discover.discover_single(
                host,
                auto_connect=False,
                timeout=2,
                account=account,
                password=password,
                get_async_client=self._get_async_client
            )

            if device is None:
                errors["base"] = "device_not_found"
            elif device.type != DeviceType.AIR_CONDITIONER:
                errors["base"] = "unsupported_device"
            else:
                # Check if device has already been configured
                await self.async_set_unique_id(str(device.id))
                self._abort_if_unique_id_configured()

                # Finish connection
                try:
                    if await Discover.connect(device):
                        return await self.async_step_show_token_key(device=device)
                    else:
                        # Indicate a connection could not be made
                        return self.async_abort(reason="cannot_connect")
                except CloudError:
                    # Catch cloud errors and report to user
                    return self.async_abort(reason="cloud_connection_failed")

        data_schema = self.add_suggested_values_to_schema(
            vol.Schema({
                vol.Optional(CONF_HOST, default=""): str,
                vol.Optional(
                    CONF_COUNTRY_CODE, default=CONF_DEFAULT_CLOUD_COUNTRY
                ): CountrySelector(
                    CountrySelectorConfig(
                        countries=CONF_CLOUD_COUNTRY_CODES)
                ),
            }), user_input)

        return self.async_show_form(step_id="discover",
                                    data_schema=data_schema, errors=errors)

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None,
        *,
        country_code: str = CONF_DEFAULT_CLOUD_COUNTRY
    ) -> FlowResult:
        """Handle the pick device step of config flow."""

        if user_input is not None:
            # Find selected device
            device = next(dev
                          for dev in self._discovered_devices
                          if dev.id == user_input[CONF_ID])

            if device:
                # Check if device has already been configured
                await self.async_set_unique_id(str(device.id))
                self._abort_if_unique_id_configured()

                # Finish connection
                try:
                    if await Discover.connect(device):
                        return await self.async_step_show_token_key(device=device)
                    else:
                        # Indicate a connection could not be made
                        return self.async_abort(reason="cannot_connect")
                except CloudError:
                    # Catch cloud errors and report to user
                    return self.async_abort(reason="cloud_connection_failed")

        # Create a set of already configured devices by ID
        configured_devices = {
            entry.unique_id for entry in self._async_current_entries()
        }

        # Get credentials for region
        account, password = _CLOUD_CREDENTIALS.get(country_code, (None, None))

        # Discover all devices
        self._discovered_devices = await Discover.discover(
            auto_connect=False,
            timeout=2,
            account=account,
            password=password,
            get_async_client=self._get_async_client
        )

        # Create dict of device ID to friendly name
        devices_name = {
            device.id: (
                f"{device.name} - {device.id} ({device.ip})"
            )
            for device in self._discovered_devices
            if (str(device.id) not in configured_devices and
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

    async def async_step_show_token_key(
        self, user_input: dict[str, Any] | None = None,
        *,
        device: AC = None
    ) -> FlowResult:
        """Handle the show token step of config flow."""

        # V2 devices don't have a token and key to display
        if device and device.version < 3:
            return await self._create_entry_from_device(device)

        if user_input is not None:
            # User input is discarded and device entry is created from saved device
            return await self._create_entry_from_device(self._device)

        # Show the user the token and key so they can be copied down
        data_schema = self.add_suggested_values_to_schema(
            vol.Schema({
                vol.Optional(CONF_ID): cv.string,
                vol.Optional(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(CONF_KEY): cv.string
            }), {
                CONF_ID: device.id,
                CONF_TOKEN: device.token,
                CONF_KEY: device.key
            })

        # Save incoming device
        self._device = device

        return self.async_show_form(step_id="show_token_key",
                                    data_schema=data_schema)

    async def async_step_manual(self, user_input) -> FlowResult:
        """Handle the manual step of config flow."""
        errors = {}

        if user_input is not None:
            # Get device ID from user input
            id = int(user_input.get(CONF_ID))

            # Check if device has already been configured
            await self.async_set_unique_id(str(id))
            self._abort_if_unique_id_configured()

            # Validate the hex format of certain fields
            for field in [CONF_TOKEN, CONF_KEY]:
                if input := user_input.get(field):
                    try:
                        bytes.fromhex(input)
                    except (ValueError, TypeError):
                        errors[field] = "invalid_hex_format"

            if not errors:
                # Attempt a connection to see if config is valid
                device = await self._test_manual_connection(user_input)

                if device:
                    return await self._create_entry_from_device(device)

                # Indicate a connection could not be made
                errors["base"] = "cannot_connect"

        user_input = user_input or {}

        data_schema = self.add_suggested_values_to_schema(
            vol.Schema({
                vol.Required(CONF_ID): cv.string,
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT, default=6444): cv.port,
                vol.Optional(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(CONF_KEY): cv.string
            }), user_input)

        return self.async_show_form(step_id="manual",
                                    data_schema=data_schema, errors=errors)

    def _get_async_client(self, *args, **kwargs) -> httpx.AsyncClient:
        """Create an httpx AsyncClient in a HA friendly way."""
        return httpx_client.get_async_client(self.hass, *args, **kwargs)

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
    def async_get_options_flow(config_entry: ConfigEntry) -> MideaOptionsFlow:
        """Create the options flow."""
        return MideaOptionsFlow()


class MideaOptionsFlow(OptionsFlow):
    """Options flow from Midea Smart AC."""

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle the options flow."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        data_schema = self.add_suggested_values_to_schema(
            vol.Schema({
                vol.Optional(CONF_BEEP): cv.boolean,
                vol.Optional(CONF_TEMP_STEP): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=5)),
                vol.Optional(CONF_FAN_SPEED_STEP): vol.All(vol.Coerce(float), vol.Range(min=1, max=20)),
                vol.Optional(CONF_USE_FAN_ONLY_WORKAROUND): cv.boolean,
                vol.Optional(CONF_SHOW_ALL_PRESETS): cv.boolean,
                vol.Optional(CONF_ADDITIONAL_OPERATION_MODES): cv.string,
                vol.Optional(CONF_MAX_CONNECTION_LIFETIME): vol.All(vol.Coerce(int), vol.Range(min=UPDATE_INTERVAL)),
                vol.Optional(CONF_ENERGY_FORMAT): SelectSelector(
                    SelectSelectorConfig(
                        options=[e.value for e in EnergyFormat],
                        translation_key="energy_format",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_SWING_ANGLE_RTL): cv.boolean,
            }), self.config_entry.options)

        return self.async_show_form(step_id="init", data_schema=data_schema)
