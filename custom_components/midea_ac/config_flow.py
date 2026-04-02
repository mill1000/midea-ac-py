"""Config flow for Midea Smart AC."""
from __future__ import annotations

import logging
from typing import Any, cast

import homeassistant.helpers.config_validation as cv
import httpx
import voluptuous as vol
import yaml
from homeassistant.config_entries import (ConfigEntry, ConfigFlow,
                                          ConfigFlowResult, OptionsFlow)
from homeassistant.const import (CONF_COUNTRY_CODE, CONF_HOST, CONF_ID,
                                 CONF_PORT, CONF_TOKEN, DEGREE)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import httpx_client
from homeassistant.helpers.selector import (CountrySelector,
                                            CountrySelectorConfig,
                                            NumberSelector,
                                            NumberSelectorConfig,
                                            NumberSelectorMode, SelectSelector,
                                            SelectSelectorConfig,
                                            SelectSelectorMode, TextSelector,
                                            TextSelectorConfig,
                                            TextSelectorType)
from msmart.base_device import Device
from msmart.const import DeviceType
from msmart.device import AirConditioner as AC
from msmart.device import CommercialAirConditioner as CC
from msmart.discover import CloudError, Discover
from msmart.lan import AuthenticationError

from .const import (CONF_BEEP, CONF_CAPABILITY_OVERRIDES,
                    CONF_CLOUD_COUNTRY_CODES, CONF_DEFAULT_CLOUD_COUNTRY,
                    CONF_DEVICE_TYPE, CONF_ENERGY_DATA_FORMAT,
                    CONF_ENERGY_DATA_SCALE, CONF_ENERGY_SENSOR,
                    CONF_FAN_SPEED_STEP, CONF_KEY,
                    CONF_MAX_CONNECTION_LIFETIME,
                    CONF_MERGE_CAPABILITY_OVERRIDES, CONF_POWER_SENSOR,
                    CONF_SWING_ANGLE_RTL, CONF_TEMP_STEP,
                    CONF_USE_FAN_ONLY_WORKAROUND, CONF_WORKAROUNDS, DOMAIN,
                    UPDATE_INTERVAL, EnergyFormat)

_LOGGER = logging.getLogger(__name__)

_DEFAULT_OPTIONS = {
    CONF_TEMP_STEP: 1.0,
    CONF_MAX_CONNECTION_LIFETIME: None,
    CONF_SWING_ANGLE_RTL: False,
    CONF_CAPABILITY_OVERRIDES: "",
    CONF_MERGE_CAPABILITY_OVERRIDES: True
}

_DEFAULT_AC_OPTIONS = {
    CONF_BEEP: True,
    CONF_FAN_SPEED_STEP: 1,
    CONF_ENERGY_SENSOR: {
        CONF_ENERGY_DATA_FORMAT: EnergyFormat.BCD,
        CONF_ENERGY_DATA_SCALE: 1.0
    },
    CONF_POWER_SENSOR: {
        CONF_ENERGY_DATA_FORMAT: EnergyFormat.BCD,
        CONF_ENERGY_DATA_SCALE: 1.0
    },
    CONF_WORKAROUNDS: {
        CONF_USE_FAN_ONLY_WORKAROUND: False,
    }
}

_CLOUD_CREDENTIALS = {
    "DE": ("midea_eu@mailinator.com", "das_ist_passwort1"),
    "KR": ("midea_sea@mailinator.com", "password_for_sea1")
}


class MideaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Midea Smart AC."""

    VERSION = 1
    MINOR_VERSION = 6

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a config flow initialized by the user."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["discover", "manual"],
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
            elif device.type not in [DeviceType.AIR_CONDITIONER, DeviceType.COMMERCIAL_AC]:
                errors["base"] = "unsupported_device"
            else:
                # Check if device has already been configured
                await self.async_set_unique_id(str(device.id))
                self._abort_if_unique_id_configured()

                # Finish connection
                try:
                    if await Discover.connect(device):
                        assert isinstance(device, (AC, CC))
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

        return self.async_show_form(
            step_id="discover",
            data_schema=data_schema,
            errors=errors
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None,
        *,
        country_code: str = CONF_DEFAULT_CLOUD_COUNTRY
    ) -> ConfigFlowResult:
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
                        assert isinstance(device, (AC, CC))
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
                device.type in [DeviceType.AIR_CONDITIONER, DeviceType.COMMERCIAL_AC])
        }

        # Check if there is at least one device
        if len(devices_name) == 0:
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema({
            vol.Required(CONF_ID): vol.In(devices_name)
        })

        return self.async_show_form(
            step_id="pick_device",
            data_schema=data_schema
        )

    async def async_step_show_token_key(
        self, user_input: dict[str, Any] | None = None,
        *,
        device: AC | CC | None = None
    ) -> ConfigFlowResult:
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

        return self.async_show_form(
            step_id="show_token_key",
            data_schema=data_schema
        )

    async def async_step_manual(self, user_input) -> ConfigFlowResult:
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

                if not device or device.online == False:
                    # Indicate a connection could not be made
                    errors["base"] = "cannot_connect"
                elif device and device.supported == False:
                    # Indicate unsupported device type
                    errors["base"] = "unsupported_device"
                else:
                    # Create entry from valid device
                    return await self._create_entry_from_device(device)

        user_input = user_input or {}

        data_schema = self.add_suggested_values_to_schema(
            vol.Schema({
                vol.Required(CONF_ID): cv.string,
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT, default=6444): cv.port,
                vol.Required(CONF_DEVICE_TYPE): SelectSelector(
                    SelectSelectorConfig(
                        options=[f"{e.value:X}" for e in
                                 [DeviceType.AIR_CONDITIONER, DeviceType.COMMERCIAL_AC]],
                        translation_key="device_type",
                        mode=SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(CONF_KEY): cv.string
            }), user_input)

        return self.async_show_form(
            step_id="manual",
            data_schema=data_schema,
            errors=errors
        )

    async def async_step_reconfigure(self, user_input) -> ConfigFlowResult:
        """Handle the reconfiguration step of config flow."""
        errors = {}

        if user_input is not None:
            # Validate the hex format of certain fields
            for field in [CONF_TOKEN, CONF_KEY]:
                if input := user_input.get(field):
                    try:
                        bytes.fromhex(input)
                    except (ValueError, TypeError):
                        errors[field] = "invalid_hex_format"

            if not errors:
                config_entry = self._get_reconfigure_entry()

                # Copy ID from existing entry
                user_input[CONF_ID] = config_entry.data[CONF_ID]

                # Convert type to hex representation
                user_input[CONF_DEVICE_TYPE] = f"{config_entry.data[CONF_DEVICE_TYPE]:X}"

                # Ensure key & token are in dict
                user_input.setdefault(CONF_KEY, None)
                user_input.setdefault(CONF_TOKEN, None)

                # Attempt a connection to see if config is valid
                device = await self._test_manual_connection(user_input)

                if not device or device.online == False:
                    # Indicate a connection could not be made
                    errors["base"] = "cannot_connect"
                elif device and device.supported == False:
                    # Indicate unsupported device type
                    errors["base"] = "unsupported_device"
                else:
                    # Update entry
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates={
                            CONF_DEVICE_TYPE: device.type,
                            CONF_ID: device.id,
                            CONF_HOST: device.ip,
                            CONF_PORT: device.port,
                            CONF_TOKEN: device.token,
                            CONF_KEY: device.key,
                        },
                    )

        # Use existing config entry data if no user input
        user_input = user_input or self._get_reconfigure_entry().data

        data_schema = self.add_suggested_values_to_schema(
            vol.Schema({
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT, default=6444): cv.port,
                vol.Optional(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(CONF_KEY): cv.string
            }), user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors
        )

    def _get_async_client(self, *args, **kwargs) -> httpx.AsyncClient:
        """Create an httpx AsyncClient in a HA friendly way."""
        return httpx_client.get_async_client(self.hass, *args, **kwargs)

    async def _test_manual_connection(self, config) -> AC | CC | None:
        DEVICE_TYPES = {
            "AC": DeviceType.AIR_CONDITIONER,
            "CC": DeviceType.COMMERCIAL_AC
        }

        # Construct the device
        device = Device.construct(
            type=DEVICE_TYPES[config.get(CONF_DEVICE_TYPE).upper()],
            ip=config.get(CONF_HOST),
            port=config.get(CONF_PORT),
            device_id=int(config.get(CONF_ID)),
        )

        # Ensure device is a supported type
        assert isinstance(device, (AC, CC))

        # Authenticate with device as needed
        token = config.get(CONF_TOKEN)
        key = config.get(CONF_KEY)
        if token and key:
            try:
                await device.authenticate(token, key)
            except AuthenticationError:
                return None

        # Attempt to refresh device state
        await device.refresh()

        return device

    async def _create_entry_from_device(self, device) -> ConfigFlowResult:
        # Save the device into global data
        self.hass.data.setdefault(DOMAIN, {})

        # Populate config data
        data = {
            CONF_DEVICE_TYPE: device.type,
            CONF_ID: device.id,
            CONF_HOST: device.ip,
            CONF_PORT: device.port,
            CONF_TOKEN: device.token,
            CONF_KEY: device.key,
        }

        # Build default options based on device type
        default_options = _DEFAULT_OPTIONS
        if device.type == DeviceType.AIR_CONDITIONER:
            default_options |= _DEFAULT_AC_OPTIONS

        # Create a config entry with the config data and default options
        return self.async_create_entry(title=f"{DOMAIN} {device.id}", data=data, options=default_options)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MideaOptionsFlow:
        """Create the options flow."""
        return MideaOptionsFlow()


class MideaOptionsFlow(OptionsFlow):
    """Options flow from Midea Smart AC."""

    _BASE_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_SWING_ANGLE_RTL): cv.boolean,
            vol.Optional(CONF_TEMP_STEP): NumberSelector(
                NumberSelectorConfig(
                    min=.5,
                    max=5,
                    step=.5,
                    unit_of_measurement=DEGREE
                )
            ),
            vol.Optional(CONF_MAX_CONNECTION_LIFETIME): vol.All(
                vol.Coerce(int),
                vol.Range(min=UPDATE_INTERVAL)
            ),
            vol.Optional(CONF_CAPABILITY_OVERRIDES):  TextSelector(
                TextSelectorConfig(
                    multiline=True,
                    type=TextSelectorType.TEXT
                )
            ),
            vol.Optional(CONF_MERGE_CAPABILITY_OVERRIDES): cv.boolean,
        }
    )

    _ENERGY_SENSOR_SCHEMA = section(
        vol.Schema(
            {
                vol.Required(CONF_ENERGY_DATA_FORMAT): SelectSelector(
                    SelectSelectorConfig(
                        options=[e.value for e in
                                 [EnergyFormat.BCD, EnergyFormat.BINARY]],
                        translation_key="energy_data_format",
                        mode=SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Required(CONF_ENERGY_DATA_SCALE): NumberSelector(
                    NumberSelectorConfig(
                        min=.001, step="any", mode=NumberSelectorMode.BOX)
                ),
            }
        ),
        {"collapsed": True}
    )

    _AC_OPTION_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_BEEP): cv.boolean,
            vol.Optional(CONF_FAN_SPEED_STEP): NumberSelector(
                NumberSelectorConfig(min=1, max=20, step=1)
            ),
            vol.Optional(CONF_ENERGY_SENSOR): _ENERGY_SENSOR_SCHEMA,
            vol.Optional(CONF_POWER_SENSOR): _ENERGY_SENSOR_SCHEMA,
            vol.Optional(CONF_WORKAROUNDS): section(
                vol.Schema({
                    vol.Optional(CONF_USE_FAN_ONLY_WORKAROUND): cv.boolean
                }),
                {"collapsed": True},
            )
        }
    )

    _CC_OPTION_SCHEMA = vol.Schema({})

    _DEVICE_SCHEMAS = {
        DeviceType.AIR_CONDITIONER: _AC_OPTION_SCHEMA,
        DeviceType.COMMERCIAL_AC: _CC_OPTION_SCHEMA,
    }

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Handle the options flow."""
        errors = {}

        if user_input is not None:
            if yaml_input := user_input.get(CONF_CAPABILITY_OVERRIDES):
                try:
                    overrides = yaml.safe_load(yaml_input)
                    if not isinstance(overrides, dict):
                        raise ValueError()

                except yaml.YAMLError as e:
                    _LOGGER.error(
                        "Failed to parse capability overrides YAML: %s", e)
                    errors[CONF_CAPABILITY_OVERRIDES] = "override_yaml_parse_error"
                except ValueError as e:
                    _LOGGER.error("Expected dict for capability overrides.")
                    errors[CONF_CAPABILITY_OVERRIDES] = "override_yaml_format_error"

            if not errors:
                return self.async_create_entry(data=user_input)

        # Get options schema based on device type
        device_type = self.config_entry.data.get(CONF_DEVICE_TYPE)
        device_schema = {}

        if schema := self._DEVICE_SCHEMAS.get(device_type):
            device_schema = schema.schema

        # Use existing data if no user input
        user_input = user_input or self.config_entry.options

        # Merge base and device-specific schema
        data_schema = self.add_suggested_values_to_schema(
            self._BASE_SCHEMA.extend(device_schema),
            user_input,
        )

        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)
