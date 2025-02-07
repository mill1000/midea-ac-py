"""Tests for the data update coordinator flow."""

import logging
import asyncio
from unittest.mock import patch, AsyncMock, PropertyMock, MagicMock

import pytest
from homeassistant import config_entries
from homeassistant.const import (CONF_HOST, CONF_ID,
                                 CONF_PORT, CONF_TOKEN)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from msmart.lan import AuthenticationError, _LanProtocol
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.config_entries import ConfigEntryState
from custom_components.midea_ac.const import CONF_KEY, DOMAIN

async def _setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration with a mock config entry."""

    # Create a mock config entry
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ID: "1234",
            CONF_HOST: "localhost",
            CONF_PORT: 6444,
            CONF_TOKEN: None,
            CONF_KEY: None,
        }
    )

    # Patch refresh and get_capabilities calls to allow integration to setup
    with (patch("custom_components.midea_ac.config_flow.AC.get_capabilities"),
          patch("custom_components.midea_ac.config_flow.AC.refresh")):
        # Add mock config entry to HASS and setup integration
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    return mock_config_entry


async def test_concurrent_refresh_exception(
    hass: HomeAssistant,
) -> None:
    """Test concurrent refreshes can cause an exception."""

    # Setup the integration
    mock_config_entry = await _setup_integration(hass)
    assert mock_config_entry

    # Fetch the coordinator
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    device = coordinator.device
    lan = device._lan

    # Mock the read_available method so send() will be reached
    lan._read_available = MagicMock()
    lan._read_available.__aiter__.return_value = None

    # Mock connect and protocol objects so network won't be used
    lan._connect = AsyncMock()
    lan._protocol = _LanProtocol()
    lan._protocol._peer = "127.0.0.1:6444"
    
    # Mock the transport so connection wil be seen as alive
    lan._protocol._transport = MagicMock()
    lan._protocol._transport.is_closing = MagicMock(return_value=False)

    logging.getLogger("msmart").setLevel(logging.DEBUG)
    
    # Check that concurrent calls to the refresh function can throw an attribute error
    # with pytest.raises(AttributeError):
    #     task1 = asyncio.create_task(coordinator._async_update_data()) 
    #     await asyncio.sleep(3)
    #     task2 = asyncio.create_task(coordinator._async_update_data()) 
    #     await asyncio.gather(task1, task2)
    

    lan._protocol = _LanProtocol()
    lan._protocol._peer = "127.0.0.1:6444"
    
    # Mock the transport so connection wil be seen as alive
    lan._protocol._transport = MagicMock()
    lan._protocol._transport.is_closing = MagicMock(return_value=False)

    task1 = asyncio.create_task(coordinator.async_request_refresh()) 
    await asyncio.sleep(3)
    task2 = asyncio.create_task(coordinator.apply()) 
    await asyncio.gather(task1, task2)
