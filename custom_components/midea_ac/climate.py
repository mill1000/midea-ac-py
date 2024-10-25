"""Climate platform from Midea Smart AC."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (PRESET_AWAY, PRESET_BOOST,
                                                    PRESET_ECO, PRESET_NONE,
                                                    PRESET_SLEEP,
                                                    ClimateEntityFeature,
                                                    HVACMode)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (ATTR_TEMPERATURE, CONF_ENABLED,
                                 UnitOfTemperature)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from msmart.device import AirConditioner as AC

from .const import (CONF_ADDITIONAL_OPERATION_MODES, CONF_BEEP,
                    CONF_SHOW_ALL_PRESETS, CONF_TEMP_STEP,
                    CONF_USE_FAN_ONLY_WORKAROUND, DOMAIN, PRESET_IECO)
from .coordinator import MideaCoordinatorEntity, MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_FAN_CUSTOM = "custom"

# Dictionaries to convert from Midea mode to HA mode
_OPERATIONAL_MODE_TO_HVAC_MODE: dict[AC.OperationalMode, HVACMode] = {
    AC.OperationalMode.AUTO: HVACMode.AUTO,
    AC.OperationalMode.COOL: HVACMode.COOL,
    AC.OperationalMode.DRY: HVACMode.DRY,
    AC.OperationalMode.HEAT: HVACMode.HEAT,
    AC.OperationalMode.FAN_ONLY: HVACMode.FAN_ONLY,
}

_HVAC_MODE_TO_OPERATIONAL_MODE: dict[HVACMode, AC.OperationalMode] = {
    HVACMode.COOL: AC.OperationalMode.COOL,
    HVACMode.HEAT: AC.OperationalMode.HEAT,
    HVACMode.FAN_ONLY: AC.OperationalMode.FAN_ONLY,
    HVACMode.DRY: AC.OperationalMode.DRY,
    HVACMode.AUTO: AC.OperationalMode.AUTO,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup the climate platform for Midea Smart AC."""

    _LOGGER.info("Setting up climate platform.")

    # Fetch coordinator from global data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    add_entities([
        MideaClimateACDevice(hass, coordinator, config_entry.options)
    ])

    # Add a service to control 'follow me' function
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_follow_me",
        {
            vol.Required(CONF_ENABLED): cv.boolean,
        },
        "async_set_follow_me",
    )


class MideaClimateACDevice(MideaCoordinatorEntity, ClimateEntity):
    """Climate entity for Midea AC device."""

    _attr_translation_key = DOMAIN
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self,
                 hass: HomeAssistant,
                 coordinator: MideaDeviceUpdateCoordinator,
                 options: dict
                 ) -> None:
        """Initialize the climate device."""
        MideaCoordinatorEntity.__init__(self, coordinator)

        self.hass = hass

        # Apply options
        self._device.beep = options.get(CONF_BEEP, False)
        self._target_temperature_step = options.get(CONF_TEMP_STEP)
        self._use_fan_only_workaround = options.get(
            CONF_USE_FAN_ONLY_WORKAROUND, False)

        # Setup default supported features
        self._supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.FAN_MODE |
            ClimateEntityFeature.PRESET_MODE
        )

        # Attempt to add new TURN_OFF/TURN_ON features in HA 2024.2
        try:
            self._supported_features |= ClimateEntityFeature.TURN_OFF
            self._supported_features |= ClimateEntityFeature.TURN_ON
        except AttributeError:
            pass

        # Setup supported presets
        if options.get(CONF_SHOW_ALL_PRESETS):
            # Add all presets
            self._preset_modes = [PRESET_NONE, PRESET_SLEEP, PRESET_AWAY,
                                  PRESET_ECO, PRESET_BOOST]
        else:
            # Get supported preset list
            self._preset_modes = [
                PRESET_NONE,
                PRESET_SLEEP
            ]

            # Only add presets supported by device
            if self._device.supports_freeze_protection:
                self._preset_modes.append(PRESET_AWAY)

            if self._device.supports_eco:
                self._preset_modes.append(PRESET_ECO)

            if self._device.supports_turbo:
                self._preset_modes.append(PRESET_BOOST)

            if self._device.supports_ieco:
                self._preset_modes.append(PRESET_IECO)

        # Fetch supported operational modes
        supported_op_modes = self._device.supported_operation_modes

        # Convert from Midea operational modes to HA HVAC mode
        self._hvac_modes = [
            _OPERATIONAL_MODE_TO_HVAC_MODE[m]
            for m in supported_op_modes
            # Don't include smart dry, we will try to automatically use this mode when supported
            if m != AC.OperationalMode.SMART_DRY
        ]
        self._hvac_modes.append(HVACMode.OFF)

        # Append additional operation modes as needed
        additional_modes = options.get(CONF_ADDITIONAL_OPERATION_MODES) or ""
        for mode in filter(None, additional_modes.split(" ")):
            if mode not in self._hvac_modes:
                _LOGGER.info("Adding additional mode '%s'.", mode)
                self._hvac_modes.append(mode)

        # Convert fan speeds to strings
        self._fan_modes = [m.name.lower()
                           for m in self._device.supported_fan_speeds]

        # If device supports any swing mode, add it to supported features
        if self._device.supported_swing_modes != [AC.SwingMode.OFF]:
            self._supported_features |= ClimateEntityFeature.SWING_MODE

        # Convert Midea swing modes to strings
        self._swing_modes = [m.name.lower()
                             for m in self._device.supported_swing_modes]

        # Dump all supported modes for debug
        _LOGGER.debug("Supported operational modes: '%s'.",
                      self._hvac_modes)
        _LOGGER.debug("Supported preset modes: '%s'.", self._preset_modes)
        _LOGGER.debug("Supported fan modes: '%s'.", self._fan_modes)
        _LOGGER.debug("Supported swing modes: '%s'.", self._swing_modes)

        # Set min and max temperatures
        self._min_temperature = self._device.min_target_temperature
        self._max_temperature = self._device.max_target_temperature

    async def _apply(self) -> None:
        """Apply changes to the device."""

        # Display on the AC should use the same unit as homeassistant
        self._device.fahrenheit = (
            self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT)

        # Apply via the coordinator
        await self.coordinator.apply()

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        return {
            "identifiers": {
                (DOMAIN, self._device.id)
            },
            "name": f"Midea AC {self._device.id}",
            "manufacturer": "Midea",
        }

    @property
    def has_entity_name(self) -> bool:
        """Indicates if entity follows naming conventions."""
        return True

    @property
    def name(self) -> None:
        """Return the name of the climate device."""
        # Return None to use device name
        return None

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this device."""
        return f"{self._device.id}"

    @property
    def assumed_state(self) -> bool:
        """Assume state rather than refresh to workaround fan_only bug."""
        return self._use_fan_only_workaround

    @property
    def should_poll(self) -> bool:
        """Poll the appliance for changes, there is no notification capability in the Midea API"""
        return not self._use_fan_only_workaround

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return device specific state attributes."""

        return {
            "follow_me": self._device.follow_me
        }

    async def async_set_follow_me(self, enabled: bool) -> None:
        """Set 'follow me' mode."""
        self._device.follow_me = enabled
        await self._apply()

    @property
    def supported_features(self) -> int:
        """Return the supported features."""

        if (self._device.operational_mode in [AC.OperationalMode.DRY,
                                              AC.OperationalMode.SMART_DRY]
                and self._device.supports_target_humidity):
            return self._supported_features | ClimateEntityFeature.TARGET_HUMIDITY

        return self._supported_features

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported target temperature step."""
        return self._target_temperature_step

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._min_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._max_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.indoor_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the current target temperature."""
        return self._device.target_temperature

    async def async_set_temperature(self, **kwargs) -> None:
        """Set a new target temperatures."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        # Round temperature to nearest .5
        self._device.target_temperature = round(temperature * 2) / 2
        await self._apply()

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._device.indoor_humidity

    @property
    def target_humidity(self) -> float | None:
        """Return the current target humidity."""
        return self._device.target_humidity

    async def async_set_humidity(self, humidity) -> None:
        """Set a new target humidity."""
        self._device.target_humidity = int(humidity)
        await self._apply()

    @property
    def swing_modes(self) -> list[str]:
        """Return the supported swing modes."""
        return self._swing_modes

    @property
    def swing_mode(self) -> str:
        """Return the current swing mode."""
        return self._device.swing_mode.name.lower()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        self._device.swing_mode = AC.SwingMode.get_from_name(
            swing_mode.upper(), self._device.swing_mode)

        await self._apply()

    @property
    def fan_modes(self) -> list[str]:
        """Return the supported fan modes."""

        # Add "Custom" to the list if a device supports custom fan speeds, and is using a custom speed
        if (self._device.supports_custom_fan_speed
                and not isinstance(self._device.fan_speed, AC.FanSpeed)):
            return [_FAN_CUSTOM] + self._fan_modes

        return self._fan_modes

    @property
    def fan_mode(self) -> str:
        """Return the current fan speed mode."""
        fan_speed = self._device.fan_speed

        if isinstance(fan_speed, AC.FanSpeed):
            return fan_speed.name.lower()
        elif isinstance(fan_speed, int):
            return _FAN_CUSTOM

        # Never expect to get here
        assert False, "fan_mode is neither int or AC.FanSpeed"

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""

        # Don't override custom fan speeds
        if fan_mode == _FAN_CUSTOM:
            return

        self._device.fan_speed = AC.FanSpeed.get_from_name(fan_mode.upper())
        await self._apply()

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the supported operation modes."""
        return self._hvac_modes

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if not self._device.power_state:
            return HVACMode.OFF

        mode = self._device.operational_mode

        if mode == AC.OperationalMode.SMART_DRY:
            mode = AC.OperationalMode.DRY

        return _OPERATIONAL_MODE_TO_HVAC_MODE.get(mode, HVACMode.OFF)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            self._device.power_state = False
        else:
            self._device.power_state = True

            mode = _HVAC_MODE_TO_OPERATIONAL_MODE.get(
                hvac_mode, self._device.operational_mode)

            if (mode == AC.OperationalMode.DRY and self._device.supports_target_humidity):
                mode = AC.OperationalMode.SMART_DRY

            self._device.operational_mode = mode

        await self._apply()

    @property
    def preset_modes(self) -> list[str]:
        """Return the supported preset modes."""
        modes = [PRESET_NONE]

        # Add away preset in heat if supported
        if self._device.operational_mode == AC.OperationalMode.HEAT:
            if PRESET_AWAY in self._preset_modes:
                modes.append(PRESET_AWAY)

        # Add eco & ieco preset in cool, dry and auto if supported
        if self._device.operational_mode in [AC.OperationalMode.AUTO,
                                             AC.OperationalMode.COOL,
                                             AC.OperationalMode.DRY]:
            if PRESET_ECO in self._preset_modes:
                modes.append(PRESET_ECO)

            if PRESET_IECO in self._preset_modes:
                modes.append(PRESET_IECO)

        # Add sleep and/or turbo preset in heat, cool or auto
        if self._device.operational_mode in [AC.OperationalMode.AUTO,
                                             AC.OperationalMode.COOL,
                                             AC.OperationalMode.HEAT]:
            modes.append(PRESET_SLEEP)

            # Add turbo/boost if supported by the device
            if PRESET_BOOST in self._preset_modes:
                modes.append(PRESET_BOOST)

        return modes

    @property
    def preset_mode(self) -> str:
        """Get the current preset mode."""
        if self._device.eco:
            return PRESET_ECO
        elif self._device.ieco:
            return PRESET_IECO
        elif self._device.turbo:
            return PRESET_BOOST
        elif self._device.freeze_protection:
            return PRESET_AWAY
        elif self._device.sleep:
            return PRESET_SLEEP
        else:
            return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        self._device.eco = False
        self._device.ieco = False
        self._device.turbo = False
        self._device.freeze_protection = False
        self._device.sleep = False

        # Enable proper mode
        if preset_mode == PRESET_BOOST:
            self._device.turbo = True
        elif preset_mode == PRESET_ECO:
            self._device.eco = True
        elif preset_mode == PRESET_IECO:
            self._device.ieco = True
        elif preset_mode == PRESET_AWAY:
            self._device.freeze_protection = True
        elif preset_mode == PRESET_SLEEP:
            self._device.sleep = True

        await self._apply()

    async def async_turn_off(self) -> None:
        """Turn the device off."""

        self._device.power_state = False
        await self._apply()

    async def async_turn_on(self) -> None:
        """Turn the device on."""

        self._device.power_state = True
        await self._apply()
