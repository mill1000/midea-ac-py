"""Switch platform for Midea Smart AC."""
from __future__ import annotations

import logging
from typing import Any, Mapping

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
    """Setup the switch platform for Midea Smart AC."""

    _LOGGER.info("Setting up switch platform.")

    # Fetch coordinator from global data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    device = coordinator.device

    # Create switches for supported features
    entities = []
    if hasattr(device, "toggle_display"):
        # TODO Check supports_display_control ?
        entities.append(MideaDisplaySwitch(coordinator))
        entities.append(MideaFollowMeSwitch(coordinator))

    if hasattr(device, "breeze_away") and getattr(device, "supports_breeze_away", False):
        entities.append(MideaSwitch(coordinator, "breeze_away"))

    if hasattr(device, "breeze_mild") and getattr(device, "supports_breeze_mild_away", False):
        entities.append(MideaSwitch(coordinator, "breeze_mild"))

    if hasattr(device, "breezeless") and getattr(device, "supports_breezeless", False):
        entities.append(MideaSwitch(coordinator, "breezeless"))

    if hasattr(device, "flash_cool") and getattr(device, "supports_flash_cool", False):
        entities.append(MideaSwitch(coordinator, "flash_cool"))

    if hasattr(device, "purifier"):
        # AC has on/off purifier
        if getattr(device, "supports_purifier", False):
            entities.append(MideaSwitch(coordinator,
                                        "purifier",
                                        entity_category=EntityCategory.CONFIG))

        # Create switch for CC purifier if only 2 modes supported
        if len(getattr(device, "supported_purifier_modes", [])) == 2:
            device_class = type(device)
            entities.append(MideaSwitch(coordinator,
                                        "purifier",
                                        entity_category=EntityCategory.CONFIG,
                                        state_map={
                                            False: device_class.PurifierMode.OFF,
                                            True: device_class.PurifierMode.ON,
                                        }))

    add_entities(entities)


class MideaDisplaySwitch(MideaCoordinatorEntity, SwitchEntity):
    """Display switch for Midea AC."""

    _attr_translation_key = "display"

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
            
            
class MideaFollowMeSwitch(MideaCoordinatorEntity, SwitchEntity):
    """follow_me switch for Midea AC."""

    _attr_translation_key = "follow_me"

    def __init__(self, coordinator: MideaDeviceUpdateCoordinator) -> None:
        MideaCoordinatorEntity.__init__(self, coordinator)

    async def _set_state(self, state) -> None:
        """Set the state of the property controlled by the switch."""

        # Update device property
        #setattr(self._device, "follow_me", state)
        self._device.follow_me = state

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
    def unique_id(self) -> str:
        """Return the unique ID of this entity."""
        return f"{self._device.id}-follow_me"

    @property
    def entity_category(self) -> str:
        """Return the entity category of this entity."""
        return EntityCategory.CONFIG

    @property
    def is_on(self) -> bool | None:
        """Return the on state of the switch."""
        #return getattr(self._device, "follow_me", None)
        return self._device.follow_me

    async def async_turn_on(self) -> None:
        """Turn the switch on."""
        await self._set_state(True)

    async def async_turn_off(self) -> None:
        """Turn the switch off."""
        await self._set_state(False)            
            


class MideaSwitch(MideaCoordinatorEntity, SwitchEntity):
    """Generic switch for Midea AC."""

    def __init__(self,
                 coordinator: MideaDeviceUpdateCoordinator,
                 prop: str,
                 translation_key: str | None = None,
                 *,
                 entity_category: EntityCategory | None = None,
                 state_map: Mapping[bool, Any] | None = None
                 ) -> None:

        MideaCoordinatorEntity.__init__(self, coordinator)

        self._prop = prop
        self._entity_category = entity_category
        self._attr_translation_key = translation_key if translation_key is not None else prop
        self._state_map = state_map

    async def _set_state(self, state: bool) -> None:
        """Set the state of the property controlled by the switch."""

        # Convert state if necessary
        if self._state_map:
            prop_state = self._state_map.get(state)
        else:
            prop_state = state

        # Update device property
        setattr(self._device, self._prop, prop_state)

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
    def unique_id(self) -> str:
        """Return the unique ID of this entity."""
        return f"{self._device.id}-{self._prop}"

    @property
    def entity_category(self) -> str:
        """Return the entity category of this entity."""
        return self._entity_category

    @property
    def available(self) -> bool:
        """Check device availability."""
        return super().available and self._device.power_state

    @property
    def is_on(self) -> bool | None:
        """Return the on state of the switch."""
        state = getattr(self._device, self._prop, None)
        if state is None:
            return None

        # Convert state if necessary
        if self._state_map:
            state = (state == self._state_map.get(True))

        return state

    async def async_turn_on(self) -> None:
        """Turn the switch on."""
        await self._set_state(True)

    async def async_turn_off(self) -> None:
        """Turn the switch off."""
        await self._set_state(False)
