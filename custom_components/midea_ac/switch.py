"""Switch platform for Midea Smart AC."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import helpers
from .const import DOMAIN
from .coordinator import MideaCoordinatorEntity, MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup the switch platform for Midea Smart AC."""

    _LOGGER.info("Setting up switch platform.")

    # Fetch coordinator from global data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Add supported switch entities
    if helpers.method_exists(coordinator.device, "toggle_display"):
        add_entities([MideaDisplaySwitch(coordinator), ])


class MideaDisplaySwitch(MideaCoordinatorEntity, SwitchEntity):
    """Display switch for Midea AC."""

    def __init__(self, coordinator: MideaDeviceUpdateCoordinator) -> None:
        MideaCoordinatorEntity.__init__(self, coordinator)

    async def _toggle_display(self) -> None:
        await self._device.toggle_display()

        await self.coordinator.async_request_refresh()

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
    def name(self) -> str:
        """Return the name of this entity."""
        return "Display"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this entity."""
        return f"{self._device.id}-display"

    @property
    def entity_category(self) -> str:
        """Return the entity category of this entity."""
        return EntityCategory.CONFIG

    @property
    def is_on(self) -> bool | None:
        """Return the on state of the display."""
        return self._device.display_on

    async def async_turn_on(self) -> None:
        """Turn the display on."""
        if not self.is_on:
            await self._toggle_display()

    async def async_turn_off(self) -> None:
        """Turn the display off."""
        if self.is_on:
            await self._toggle_display()


class MideaSwitch(MideaCoordinatorEntity, SwitchEntity):
    """Generic switch for Midea AC."""

    def __init__(self,
                 coordinator: MideaDeviceUpdateCoordinator,
                 prop: str,
                 entity_category: str
                 ) -> None:
        MideaCoordinatorEntity.__init__(self, coordinator)

        self._prop = prop
        self._name = prop.replace("_", " ").capitalize()
        self._entity_category = entity_category

    async def _set_state(self, state) -> None:
        """Set the state of the property controlled by the switch."""

        # Update device property
        setattr(self._device, self._prop, state)

        # Apply via coordinator
        await self.coordinator.apply()

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
    def name(self) -> str:
        """Return the name of this entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this entity."""
        return f"{self._device.id}-{self._prop}"

    @property
    def entity_category(self) -> str:
        """Return the entity category of this entity."""
        return self._entity_category

    @property
    def is_on(self) -> bool | None:
        """Return the on state of the switch."""
        return getattr(self._device, self._prop, None)

    async def async_turn_on(self) -> None:
        """Turn the switch on."""
        await self._set_state(True)

    async def async_turn_off(self) -> None:
        """Turn the switch off."""
        await self._set_state(False)
