"""Tests for the switch platform."""

import logging
from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from msmart.device import CommercialAirConditioner as CC
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.midea_ac.const import DOMAIN
from custom_components.midea_ac.coordinator import MideaDeviceUpdateCoordinator
from custom_components.midea_ac.switch import MideaSwitch

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


async def test_state_map():
    """Test switch properly applies state map to convert device properties to switch state"""

    # Mock the device
    mock_device = MagicMock()
    mock_device.power_state = True

    # Mock the coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.apply = AsyncMock()
    mock_coordinator.device = mock_device

    # Create dummy property
    mock_device.purifier = None

    # Create the switch with a state map
    switch = MideaSwitch(
        coordinator=mock_coordinator,
        prop="purifier",
        state_map={
            False: 2,
            True: 1,
        }
    )

    # None should be None
    mock_device.purifier = None
    assert switch.is_on is None

    # Turn on switch
    await switch.async_turn_on()

    # Assert property is set as expected
    assert mock_device.purifier == 1
    mock_coordinator.apply.assert_awaited_once()
    assert switch.is_on is True

    mock_coordinator.apply.reset_mock()

    # Turn off
    await switch.async_turn_off()

    # Assert property is set as expected
    assert mock_device.purifier == 2
    mock_coordinator.apply.assert_awaited_once()
    assert switch.is_on is False

    # Verify invalid value defaults to false
    mock_device.purifier = 10
    assert switch.is_on is False


async def test_cc_purifier_switch(
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        mock_config_entry: MockConfigEntry,
) -> None:
    """Test CC device with 2 purifier modes creates a switch."""

    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    mock_config_entry.add_to_hass(hass)

    # Create a dummy device and force 2 purifier modes
    mock_device = CC("0.0.0.0", 0, 0)
    mock_device.power_state = True
    mock_device._supported_purifier_modes = ["Mode1", "Mode2"]
    mock_device.purifier = None

    # Create a mock coordinator
    coordinator = MagicMock(spec=MideaDeviceUpdateCoordinator)
    coordinator.device = mock_device
    coordinator.apply = AsyncMock()
    coordinator.last_update_success = True

    # Store coordinator in global data
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = coordinator

    # Setup climate and switch platforms
    await hass.config_entries.async_forward_entry_setups(
        mock_config_entry, [Platform.CLIMATE]
    )
    await hass.async_block_till_done()

    await hass.config_entries.async_forward_entry_setups(
        mock_config_entry, [Platform.SWITCH]
    )
    await hass.async_block_till_done()

    # Verify switch exists
    entity_id = "switch.midea_cc_0_purifier"
    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "0-purifier"


async def test_cc_purifier_no_switch(
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        mock_config_entry: MockConfigEntry,
) -> None:
    """Test CC device with 3 purifier modes does NOT create a switch."""

    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    mock_config_entry.add_to_hass(hass)

    # Create a dummy device and force 3 purifier modes
    mock_device = CC("0.0.0.0", 0, 0)
    mock_device.power_state = True
    mock_device._supported_purifier_modes = ["Mode1", "Mode2", "Mode3"]
    mock_device.purifier = None

    # Create a mock coordinator
    coordinator = MagicMock(spec=MideaDeviceUpdateCoordinator)
    coordinator.device = mock_device
    coordinator.apply = AsyncMock()

    # Store coordinator in global data
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = coordinator

    # Setup climate and switch platforms
    await hass.config_entries.async_forward_entry_setups(
        mock_config_entry, [Platform.CLIMATE]
    )
    await hass.async_block_till_done()

    await hass.config_entries.async_forward_entry_setups(
        mock_config_entry, [Platform.SWITCH]
    )
    await hass.async_block_till_done()

    # Verify switch doesn't exit
    entity_id = "switch.midea_cc_0_purifier"
    state = hass.states.get(entity_id)
    assert state is None

    entry = entity_registry.async_get(entity_id)
    assert entry is None
