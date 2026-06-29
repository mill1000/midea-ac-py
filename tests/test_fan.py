"""Tests for the fan platform."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from msmart.device import AirConditioner as AC
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.midea_ac.const import DOMAIN
from custom_components.midea_ac.coordinator import MideaDeviceUpdateCoordinator

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

# Fresh air fan requires a msmart-ng with Fresh Air support (> 2026.4.1)
pytestmark = pytest.mark.skipif(
    not hasattr(AC, "FreshAirFanSpeed"),
    reason="msmart-ng without Fresh Air support",
)


async def test_fresh_air_fan(
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        mock_config_entry: MockConfigEntry,
) -> None:
    """Test an AC device that supports fresh air creates a fresh air fan."""

    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    mock_config_entry.add_to_hass(hass)

    # Create a dummy AC device and force fresh air support
    mock_device = AC("0.0.0.0", 0, 0)
    mock_device._online = True
    mock_device.power_state = True
    mock_device._capabilities.set(AC.Capability.FRESH_AIR, True)

    # Create a mock coordinator
    coordinator = MagicMock(spec=MideaDeviceUpdateCoordinator)
    coordinator.device = mock_device
    coordinator.apply = AsyncMock()

    # Store coordinator in global data
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = coordinator

    # Setup climate (to name the device) and fan platforms
    await hass.config_entries.async_forward_entry_setups(
        mock_config_entry, [Platform.CLIMATE]
    )
    await hass.async_block_till_done()

    await hass.config_entries.async_forward_entry_setups(
        mock_config_entry, [Platform.FAN]
    )
    await hass.async_block_till_done()

    # Verify the fresh air fan exists and is off by default
    entity_id = "fan.midea_ac_0_fresh_air"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"
    assert state.attributes["percentage"] == 0

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "0-fresh_air"

    # Setting a percentage turns it on. With 4 speeds the ordered-list buckets
    # are 25/50/75/100, so 75% maps to the 3rd level (High).
    await hass.services.async_call(
        Platform.FAN, "set_percentage",
        {"entity_id": entity_id, "percentage": 75}, blocking=True
    )
    assert mock_device.fresh_air_fan_speed == AC.FreshAirFanSpeed.HIGH
    coordinator.apply.assert_awaited()

    # Turning the fan off sets the speed to OFF
    await hass.services.async_call(
        Platform.FAN, "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert mock_device.fresh_air_fan_speed == AC.FreshAirFanSpeed.OFF
