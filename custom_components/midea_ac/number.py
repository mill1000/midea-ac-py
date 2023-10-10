"""Platform for switch integration."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from msmart.device import AirConditioner as AC

# Local constants
from .const import DOMAIN
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

    # Create sensor entities from device if supported
    if getattr(coordinator.device, "supports_custom_fan_speed", False):
        add_entities([MideaFanSpeedNumber(coordinator)])


class MideaFanSpeedNumber(MideaCoordinatorEntity, NumberEntity):
    """Fan speed number for Midea AC."""

    def __init__(self, coordinator: MideaDeviceUpdateCoordinator) -> None:
        MideaCoordinatorEntity.__init__(self, coordinator)

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        return {
            "identifiers": {
                (DOMAIN, self._device.id)
            },
        }

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        return f"{DOMAIN}_fan_speed_{self._device.id}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this entity."""
        return f"{self._device.id}-fan_speed"

    @property
    def available(self) -> bool:
        """Check device availability."""
        return self._device.online and self._device.power_state

    @property
    def native_unit_of_measurement(self) -> str:
        return PERCENTAGE

    @property
    def native_max_value(self) -> float:
        return 100

    @property
    def native_min_value(self) -> float:
        return 1

    @property
    def native_value(self) -> float:

        speed = self._device.fan_speed

        # Convert enum to integer
        if isinstance(speed, AC.FanSpeed):
            speed = speed.value

        _LOGGER.info("Got value %s.", speed)
        return speed

    async def async_set_native_value(self, value: float) -> None:
        """Set a new fan speed value."""

        self._device.fan_speed = value
        _LOGGER.info("Set value %s.", value)

        # Apply via the coordinator
        await self.coordinator.apply()
