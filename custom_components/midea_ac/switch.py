"""Platform for switch integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

# Local constants
from .const import DOMAIN
from . import helpers

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup the switch platform for Midea Smart AC."""

    _LOGGER.info("Setting up switch platform.")

    # Get config data from entry
    config = config_entry.data

    # Fetch device from global data
    id = config.get(CONF_ID)
    device = hass.data[DOMAIN][id]

    # Add supported switch entities
    if helpers.method_exists(device, "toggle_display"):
        add_entities([MideaDisplaySwitch(device), ])


class MideaDisplaySwitch(SwitchEntity, RestoreEntity):
    """Display switch for Midea AC."""

    def __init__(self, device):
        self._device = device
        self._on = False

    async def _toggle_display(self) -> None:
        await self.hass.async_add_executor_job(self._device.toggle_display)
        await self.async_update_ha_state()
        self._on = not self._on

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is None:
            return

        # Restore previous state
        if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._on = last_state.state == STATE_ON

    async def async_update(self) -> None:
        # Grab the display on status
        if self.available:
            self._on = self._device.display_on

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {
                (DOMAIN, self._device.id)
            },
        }

    @property
    def entity_category(self) -> dict:
        return EntityCategory.CONFIG

    @property
    def name(self) -> str:
        return f"{DOMAIN}_display_{self._device.id}"

    @property
    def unique_id(self) -> str:
        return f"{self._device.id}-display"

    @property
    def available(self) -> bool:
        return self._device.online

    @property
    def is_on(self) -> bool:
        return self._on

    async def async_turn_on(self) -> None:
        if not self.is_on:
            await self._toggle_display()

    async def async_turn_off(self) -> None:
        if self.is_on:
            await self._toggle_display()
