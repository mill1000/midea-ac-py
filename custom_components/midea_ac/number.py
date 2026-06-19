"""Platform for number integration."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_FAN_SPEED_STEP, DOMAIN
from .coordinator import MideaCoordinatorEntity, MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Relative countdown timers are expressed in minutes, max 24 hours, 15 minute steps
_TIMER_MAX_MINUTES = 24 * 60
_TIMER_STEP_MINUTES = 15


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup the number platform for Midea Smart AC."""

    _LOGGER.info("Setting up number platform.")

    # Fetch coordinator from global data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    device = coordinator.device

    entities = []

    # Create entity if supported
    if getattr(device, "supports_custom_fan_speed", False):
        entities.append(MideaFanSpeedNumber(
            coordinator,
            config_entry.options.get(CONF_FAN_SPEED_STEP, 1)
        ))

    # Create timer entities for devices that support relative countdown timers
    if hasattr(device, "on_timer"):
        entities.append(MideaPowerOnTimerNumber(coordinator))
    if hasattr(device, "off_timer"):
        entities.append(MideaPowerOffTimerNumber(coordinator))

    add_entities(entities)


class MideaFanSpeedNumber(MideaCoordinatorEntity, NumberEntity):
    """Fan speed number for Midea AC."""

    _attr_translation_key = "fan_speed"

    def __init__(self,
                 coordinator: MideaDeviceUpdateCoordinator,
                 step_size: float = 1
                 ) -> None:
        MideaCoordinatorEntity.__init__(self, coordinator)

        self._step_size = step_size

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        return {
            "identifiers": {
                (DOMAIN, self._device.id)
            },
        }

    @property
    def has_entity_name(self) -> bool:
        """Indicates if entity follows naming conventions."""
        return True

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this entity."""
        return f"{self._device.id}-fan_speed"

    @property
    def available(self) -> bool:
        """Check device availability."""
        return super().available and self._device.power_state

    @property
    def native_unit_of_measurement(self) -> str:
        return PERCENTAGE

    @property
    def native_max_value(self) -> float:
        return 100

    @property
    def native_min_value(self) -> float:
        # Use step size as minimum to ensure steps are nice and round
        return self._step_size

    @property
    def native_step(self) -> float:
        return self._step_size

    @property
    def native_value(self) -> float:

        speed = self._device.fan_speed

        # Convert enum to integer
        if isinstance(speed, self._device.FanSpeed):
            speed = speed.value

        return speed

    async def async_set_native_value(self, value: float) -> None:
        """Set a new fan speed value."""

        self._device.fan_speed = value

        # Apply via the coordinator
        await self.coordinator.apply()


class _MideaTimerNumber(MideaCoordinatorEntity, NumberEntity):
    """Base class for relative countdown timer numbers."""

    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 0
    _attr_native_max_value = _TIMER_MAX_MINUTES
    _attr_native_step = _TIMER_STEP_MINUTES
    _attr_mode = NumberMode.BOX

    # Attribute on the device that backs this timer, e.g. "on_timer"
    _timer_attr: str

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        return {
            "identifiers": {
                (DOMAIN, self._device.id)
            },
        }

    @property
    def has_entity_name(self) -> bool:
        """Indicates if entity follows naming conventions."""
        return True

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this entity."""
        return f"{self._device.id}-{self._timer_attr}"

    @property
    def native_value(self) -> float:
        """Return the timer value in minutes (0 = disabled)."""
        return getattr(self._device, self._timer_attr)

    async def async_set_native_value(self, value: float) -> None:
        """Set a new timer value in minutes."""

        setattr(self._device, self._timer_attr, int(value))

        # Apply via the coordinator
        await self.coordinator.apply()


class MideaPowerOnTimerNumber(_MideaTimerNumber):
    """Power-on countdown timer for Midea AC."""

    _attr_translation_key = "power_on_timer"
    _timer_attr = "on_timer"

    # A power-on timer is meaningful while the device is off, so remain
    # available regardless of power state.


class MideaPowerOffTimerNumber(_MideaTimerNumber):
    """Power-off countdown timer for Midea AC."""

    _attr_translation_key = "power_off_timer"
    _timer_attr = "off_timer"

    @property
    def available(self) -> bool:
        """A power-off timer only applies while the device is running."""
        return super().available and self._device.power_state
