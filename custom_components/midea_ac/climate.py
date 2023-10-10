"""Climate platform from Midea Smart AC."""
from __future__ import annotations

import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (PRESET_AWAY, PRESET_BOOST,
                                                    PRESET_ECO, PRESET_NONE,
                                                    PRESET_SLEEP,
                                                    SUPPORT_FAN_MODE,
                                                    SUPPORT_PRESET_MODE,
                                                    SUPPORT_SWING_MODE,
                                                    SUPPORT_TARGET_TEMPERATURE,
                                                    HVACMode)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from msmart.device import AirConditioner as AC

from . import helpers
from .const import (CONF_ADDITIONAL_OPERATION_MODES, CONF_BEEP,
                    CONF_INCLUDE_OFF_AS_STATE, CONF_SHOW_ALL_PRESETS,
                    CONF_TEMP_STEP, CONF_USE_FAN_ONLY_WORKAROUND, DOMAIN)
from .coordinator import MideaCoordinatorEntity, MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

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


class MideaClimateACDevice(MideaCoordinatorEntity, ClimateEntity):
    """Climate entity for Midea AC device."""

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
        self._include_off_as_state = options.get(CONF_INCLUDE_OFF_AS_STATE)
        self._use_fan_only_workaround = options.get(
            CONF_USE_FAN_ONLY_WORKAROUND, False)

        if options.get(CONF_SHOW_ALL_PRESETS):
            # Add all presets
            self._preset_modes = [PRESET_NONE, PRESET_SLEEP, PRESET_AWAY,
                                  PRESET_ECO, PRESET_BOOST]
        else:
            # Get supported preset list
            self._preset_modes = [
                PRESET_NONE,
                PRESET_SLEEP,  # TODO Always add sleep
            ]

            # Only add presets supported by device
            if getattr(self._device, "supports_freeze_protection_mode", False):
                self._preset_modes.append(PRESET_AWAY)

            if getattr(self._device, "supports_eco_mode", False):
                self._preset_modes.append(PRESET_ECO)

            if getattr(self._device, "supports_turbo_mode", False):
                self._preset_modes.append(PRESET_BOOST)

        # Fetch supported operational modes
        supported_op_modes = getattr(
            self._device, "supported_operation_modes",  AC.OperationalMode.list())

        # Convert from Midea operational modes to HA HVAC mode
        self._hvac_modes = [_OPERATIONAL_MODE_TO_HVAC_MODE[m]
                            for m in supported_op_modes]

        # Include off mode if requested
        if self._include_off_as_state:
            self._hvac_modes.append(HVACMode.OFF)

        # Append additional operation modes as needed
        additional_modes = options.get(CONF_ADDITIONAL_OPERATION_MODES) or ""
        for mode in filter(None, additional_modes.split(" ")):
            if mode not in self._hvac_modes:
                _LOGGER.info(f"Adding additional mode '{mode}'.")
                self._hvac_modes.append(mode)

        # Fetch supported fan speeds
        supported_fan_speeds = getattr(
            self._device, "supported_fan_speeds", AC.FanSpeed.list())

        # Convert Midea swing modes to strings
        self._fan_modes = [m.name.capitalize()
                           for m in supported_fan_speeds]
        
        if getattr(self._device, "supports_custom_fan_speed", False):
            self._fan_modes.append("Custom")

        # Fetch supported swing modes
        supported_swing_modes = getattr(
            self._device, "supported_swing_modes", AC.SwingMode.list())

        # Convert Midea swing modes to strings
        self._swing_modes = [m.name.capitalize()
                             for m in supported_swing_modes]

        # Dump all supported modes for debug
        _LOGGER.debug("Supported operational modes: '%s'.",
                      self._hvac_modes)
        _LOGGER.debug("Supported preset modes: '%s'.", self._preset_modes)
        _LOGGER.debug("Supported fan modes: '%s'.", self._fan_modes)
        _LOGGER.debug("Supported swing modes: '%s'.", self._swing_modes)

        # Attempt to load min/max target temperatures
        self._min_temperature = getattr(
            self._device, "min_target_temperature", 16)
        self._max_temperature = getattr(
            self._device, "max_target_temperature", 30)

    async def _apply(self) -> None:
        """Apply changes to the device."""

        # Display on the AC should use the same unit as homeassistant
        helpers.set_properties(self._device, ["fahrenheit", "fahrenheit_unit"],
                               self.hass.config.units.temperature_unit == TEMP_FAHRENHEIT)

        # Apply via the coordinator
        await self.coordinator.apply()

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        return {
            "identifiers": {
                (DOMAIN, self._device.id)
            },
            "name": self.name,
            "manufacturer": "Midea",
        }

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return f"{DOMAIN}_{self._device.id}"

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
    def supported_features(self) -> int:
        """Return the supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE | SUPPORT_PRESET_MODE

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported target temperature step."""
        return self._target_temperature_step

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @ property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._min_temperature

    @ property
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
    def swing_modes(self) -> list:
        """Return the supported swing modes."""
        return self._swing_modes

    @property
    def swing_mode(self) -> str:
        """Return the current swing mode."""
        return self._device.swing_mode.name.capitalize()

    async def async_set_swing_mode(self, swing_mode) -> None:
        """Set the swing mode."""
        self._device.swing_mode = AC.SwingMode.get_from_name(
            swing_mode.upper(), self._device.swing_mode)

        await self._apply()

    @property
    def fan_modes(self) -> list:
        """Return the supported fan modes."""
        return self._fan_modes

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan speed mode."""
        fan_speed = self._device.fan_speed
        _LOGGER.info("Got fan mode %s", fan_speed)
        _LOGGER.info("Got fan mode type %s", type(fan_speed))
        if isinstance(fan_speed, AC.FanSpeed):
            return fan_speed.name.capitalize()
        elif isinstance(fan_speed, int):
            return "Custom"
        
        _LOGGER.info("Return fan mode none")
        return None

    async def async_set_fan_mode(self, fan_mode) -> None:
        """Set the fan mode."""
        _LOGGER.info("Set fan mode %s", fan_mode)
        _LOGGER.info("Set fan mode type %s", type(fan_mode))
        if fan_mode == "Custom":
            return
        try:
            self._device.fan_speed  = AC.FanSpeed[fan_mode.upper()]
        except KeyError:
            self._device.fan_speed = int(fan_mode)

        await self._apply()

    @property
    def hvac_modes(self) -> list:
        """Return the supported operation modes."""
        return self._hvac_modes

    @property
    def hvac_mode(self) -> str:
        """Return current HVAC mode."""
        if self._include_off_as_state and not self._device.power_state:
            return HVACMode.OFF

        # TODO What else to default to?
        return _OPERATIONAL_MODE_TO_HVAC_MODE.get(self._device.operational_mode, HVACMode.OFF)

    async def async_set_hvac_mode(self, hvac_mode) -> None:
        """Set the HVAC mode."""
        if self._include_off_as_state and hvac_mode == HVACMode.OFF:
            self._device.power_state = False
        else:
            if self._include_off_as_state:
                self._device.power_state = True

            self._device.operational_mode = _HVAC_MODE_TO_OPERATIONAL_MODE.get(
                hvac_mode, self._device.operational_mode)

        await self._apply()

    @property
    def preset_modes(self) -> list:
        """Return the supported preset modes."""
        modes = [PRESET_NONE]

        # Add away preset in heat if supported
        if self._device.operational_mode == AC.OperationalMode.HEAT:
            if PRESET_AWAY in self._preset_modes:
                modes.append(PRESET_AWAY)

        # Add eco preset in cool, dry and auto if supported
        if self._device.operational_mode in [AC.OperationalMode.AUTO,
                                             AC.OperationalMode.COOL,
                                             AC.OperationalMode.DRY]:
            if PRESET_ECO in self._preset_modes:
                modes.append(PRESET_ECO)

        # Add sleep and/or turbo preset in heat, cool or auto
        if self._device.operational_mode in [AC.OperationalMode.AUTO,
                                             AC.OperationalMode.COOL,
                                             AC.OperationalMode.HEAT]:
            # TODO Always add sleep
            modes.append(PRESET_SLEEP)

            # Add turbo/boost if supported by the device
            if PRESET_BOOST in self._preset_modes:
                modes.append(PRESET_BOOST)

        return modes

    @ property
    def preset_mode(self) -> str:
        """Get the current preset mode."""
        if self._device.eco_mode:
            return PRESET_ECO
        elif self._device.turbo_mode:
            return PRESET_BOOST
        elif getattr(self._device, "freeze_protection_mode", False):
            return PRESET_AWAY
        elif getattr(self._device, "sleep_mode", False):
            return PRESET_SLEEP
        else:
            return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        # TODO Assuming these are all mutually exclusive
        self._device.eco_mode = False
        self._device.turbo_mode = False
        self._device.freeze_protection_mode = False
        self._device.sleep_mode = False

        # Enable proper mode
        if preset_mode == PRESET_BOOST:
            self._device.turbo_mode = True
        elif preset_mode == PRESET_ECO:
            self._device.eco_mode = True
        elif preset_mode == PRESET_AWAY:
            self._device.freeze_protection_mode = True
        elif preset_mode == PRESET_SLEEP:
            self._device.sleep_mode = True

        await self._apply()
