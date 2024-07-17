"""Binary platform for Midea Smart AC."""
from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.binary_sensor import (BinarySensorDeviceClass,
                                                    BinarySensorEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MideaCoordinatorEntity, MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup the binary sensor platform for Midea Smart AC."""

    _LOGGER.info("Setting up binary sensor platform.")

    # Fetch coordinator from global data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create sensor entities from device if supported
    if getattr(coordinator.device, "supports_filter_reminder", False):
        add_entities([MideaBinarySensor(coordinator,
                                        "filter_alert",
                                        BinarySensorDeviceClass.PROBLEM,
                                        "filter_alert"
                                        )])


class MideaBinarySensor(MideaCoordinatorEntity, BinarySensorEntity):
    """Binary sensor for Midea AC."""

    def __init__(self,
                 coordinator: MideaDeviceUpdateCoordinator,
                 prop: str,
                 device_class: BinarySensorDeviceClass,
                 translation_key: Optional[str] = None,
                 *,
                 entity_category: EntityCategory = None) -> None:
        MideaCoordinatorEntity.__init__(self, coordinator)

        self._prop = prop
        self._device_class = device_class
        self._entity_category = entity_category
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
    def device_class(self) -> str:
        """Return the device class of this entity."""
        return self._device_class

    @property
    def entity_category(self) -> str:
        """Return the entity category of this entity."""
        return self._entity_category

    @property
    def is_on(self) -> bool | None:
        """Return the on state of this entity."""
        return getattr(self._device, self._prop, None)
