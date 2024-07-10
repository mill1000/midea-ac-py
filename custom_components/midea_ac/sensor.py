"""Sensor platform for Midea Smart AC."""
from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.sensor import (SensorDeviceClass, SensorEntity,
                                             SensorStateClass)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MideaCoordinatorEntity, MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup the sensor platform for Midea Smart AC."""

    _LOGGER.info("Setting up sensor platform.")

    # Fetch coordinator from global data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        MideaSensor(coordinator,
                               "indoor_temperature",
                               SensorDeviceClass.TEMPERATURE,
                               UnitOfTemperature.CELSIUS,
                               "indoor_temperature"),
        MideaSensor(coordinator,
                               "outdoor_temperature",
                               SensorDeviceClass.TEMPERATURE,
                               UnitOfTemperature.CELSIUS,
                               "outdoor_temperature"),
    ]

    # TODO missing in msmart-ng
    if getattr(coordinator.device, "supports_humidity", False):
        entities.append(MideaSensor(coordinator,
                            "indoor_humidity",
                             SensorDeviceClass.HUMIDITY,
                             PERCENTAGE,
                            "indoor_humidity"))

    add_entities(entities)


class MideaSensor(MideaCoordinatorEntity, SensorEntity):
    """Generic sensor class for Midea AC."""

    def __init__(self,
                 coordinator: MideaDeviceUpdateCoordinator,
                 prop: str,
                 device_class: SensorDeviceClass,
                 unit,
                 translation_key: Optional[str] = None) -> None:
        MideaCoordinatorEntity.__init__(self, coordinator)

        self._prop = prop
        self._device_class = device_class
        self._unit = unit
        self._attr_translation_key = translation_key

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
        return f"{self._device.id}-{self._prop}"

    @property
    def available(self) -> bool:
        """Check entity availability."""

        # Sensor is unavailable if device is offline or value is None
        return self._device.online and self.native_value is not None

    @property
    def device_class(self) -> str:
        """Return the device class of this entity."""
        return self._device_class
    
    @property
    def state_class(self) -> str:
        """Return the state class of this entity."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the native units of this entity."""
        return self._unit

    @property
    def native_value(self) -> float | None:
        """Return the current native value."""
        return getattr(self._device, self._prop, None)
