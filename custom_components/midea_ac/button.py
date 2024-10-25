"""Button platform for Midea Smart AC."""
from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.button import ButtonEntity
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
    """Setup the button platform for Midea Smart AC."""

    _LOGGER.info("Setting up button platform.")

    # Fetch coordinator from global data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create entities for supported features
    entities = []
    if coordinator.device.supports_self_clean:
        entities.append(MideaButton(coordinator,
                                    "start_self_clean",
                                    "self_clean",
                                    entity_category=EntityCategory.DIAGNOSTIC,
                                    ))
    add_entities(entities)


class MideaButton(MideaCoordinatorEntity, ButtonEntity):
    """Button for Midea AC."""

    def __init__(self,
                 coordinator: MideaDeviceUpdateCoordinator,
                 method: str,
                 translation_key: Optional[str] = None,
                 *,
                 entity_category: EntityCategory = None) -> None:
        MideaCoordinatorEntity.__init__(self, coordinator)

        self._method = method
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
        return f"{self._device.id}-{self._method}"

    @property
    def entity_category(self) -> str:
        """Return the entity category of this entity."""
        return self._entity_category

    async def async_press(self) -> None:
        """Handle the button press."""
        # Call the buttons method
        if method := getattr(self._device, self._method, None):
            await method()
