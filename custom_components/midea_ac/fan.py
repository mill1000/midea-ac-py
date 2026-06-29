"""Fan platform for Midea Smart AC."""
from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (ordered_list_item_to_percentage,
                                           percentage_to_ordered_list_item)
from msmart.device import AirConditioner as AC

from .const import DOMAIN
from .coordinator import MideaCoordinatorEntity, MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup the fan platform for Midea Smart AC."""

    _LOGGER.info("Setting up fan platform.")

    # Fetch coordinator from global data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    device = coordinator.device

    # Create fans for supported features
    entities = []
    if hasattr(device, "fresh_air_fan_speed") and getattr(device, "supports_fresh_air", False):
        entities.append(MideaFreshAirFan(coordinator))

    add_entities(entities)


class MideaFreshAirFan(MideaCoordinatorEntity, FanEntity):
    """Fresh air (ventilation) fan for Midea AC."""

    _attr_translation_key = "fresh_air"
    _enable_turn_on_off_backwards_compatibility = False

    # List of selectablespeed levels excluding off
    _SPEEDS = [s for s in AC.FreshAirFanSpeed.list()
               if s != AC.FreshAirFanSpeed.OFF]

    def __init__(self, coordinator: MideaDeviceUpdateCoordinator) -> None:
        MideaCoordinatorEntity.__init__(self, coordinator)

        self._supported_features = FanEntityFeature.SET_SPEED

        # Attempt to add new TURN_OFF/TURN_ON features in HA 2024.8
        try:
            self._supported_features |= FanEntityFeature.TURN_OFF
            self._supported_features |= FanEntityFeature.TURN_ON
        except AttributeError:
            pass

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
        return f"{self._device.id}-fresh_air"

    @property
    def supported_features(self) -> FanEntityFeature:
        """Return the supported features."""
        return self._supported_features

    @property
    def available(self) -> bool:
        """Check device availability."""
        return super().available and self._device.power_state

    @property
    def is_on(self) -> bool:
        """Return whether fresh air is on."""
        return self._device.fresh_air_fan_speed != AC.FreshAirFanSpeed.OFF

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(self._SPEEDS)

    @property
    def percentage(self) -> int:
        """Return the current speed as a percentage."""
        speed = self._device.fresh_air_fan_speed
        if speed == AC.FreshAirFanSpeed.OFF:
            return 0

        return ordered_list_item_to_percentage(self._SPEEDS, speed)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        speed = AC.FreshAirFanSpeed.OFF
        if percentage > 0:
            speed = percentage_to_ordered_list_item(self._SPEEDS, percentage)

        self._device.fresh_air_fan_speed = speed
        await self.coordinator.apply()

    async def async_turn_on(self, percentage: Optional[int] = None, preset_mode: Optional[str] = None, **kwargs: Any) -> None:
        """Turn the fan on."""
        if percentage is not None:
            return await self.async_set_percentage(percentage)

        # Default to the lowest supported speed when turning on from off
        if self._device.fresh_air_fan_speed == AC.FreshAirFanSpeed.OFF:
            self._device.fresh_air_fan_speed = self._SPEEDS[0]

        await self.coordinator.apply()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self._device.fresh_air_fan_speed = AC.FreshAirFanSpeed.OFF
        await self.coordinator.apply()
