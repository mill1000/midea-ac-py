"""Platform for number integration."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from msmart.device import AirConditioner as AC

from .const import CONF_FAN_SPEED_STEP, DOMAIN
from .coordinator import MideaCoordinatorEntity, MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup the number platform for Midea Smart AC."""

    _LOGGER.info("Setting up number platform.")

    # Fetch coordinator from global data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create entity if supported
    if coordinator.device.supports_custom_fan_speed:
        add_entities([MideaFanSpeedNumber(
            coordinator,
            config_entry.options.get(CONF_FAN_SPEED_STEP, 1)
        )])


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
        if isinstance(speed, AC.FanSpeed):
            speed = speed.value

        return speed

    async def async_set_native_value(self, value: float) -> None:
        """Set a new fan speed value."""

        self._device.fan_speed = value

        # Apply via the coordinator
        await self.coordinator.apply()
