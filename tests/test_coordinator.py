"""Tests for the data update coordinator."""

import asyncio
import logging
from typing import NoReturn
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from msmart.device import AirConditioner as AC
from msmart.lan import _LanProtocol

from custom_components.midea_ac.coordinator import MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _mock_lan_protocol(lan) -> None:
    """ Mock the LAN protocol object to enable testing."""

    # Mock the read_available method so send() will be reached
    lan._read_available = MagicMock()
    lan._read_available.__aiter__.return_value = None

    # Mock connect and protocol objects so network won't be used
    async def mock_connect() -> None:
        lan._protocol = _LanProtocol()
        lan._protocol._peer = "127.0.0.1:6444"

        # Mock the transport so connection wil be seen as alive
        lan._protocol._transport = MagicMock()
        lan._protocol._transport.is_closing = MagicMock(return_value=False)

        async def _read_timeout() -> NoReturn:
            await asyncio.sleep(.25)
            raise TimeoutError

        lan._protocol.read = AsyncMock(side_effect=_read_timeout)

    lan._connect = mock_connect


async def test_concurrent_network_access_exception(
    hass: HomeAssistant,
) -> None:
    """Test concurrent network access can cause an exception."""

    # Create dummy device
    device = AC("0.0.0.0", 0, 0)

    # Create coordinator
    coordinator = MideaDeviceUpdateCoordinator(hass, device)

    # Setup a mock LAN protocol
    _mock_lan_protocol(device._lan)

    # logging.getLogger("msmart").setLevel(logging.DEBUG)
    # logging.getLogger("custom_components.midea_ac").setLevel(logging.DEBUG)

    # Patch the asyncio Lock object to be non-functional
    with (
            patch.object(coordinator._lock, "acquire",
                         AsyncMock(return_value=True)),
            patch.object(coordinator._lock, "locked",
                         MagicMock(return_value=False)),
            patch.object(coordinator._lock, "release",
                         MagicMock(return_value=None))
    ):
        # Assert exception is thrown when concurrent access occurs
        # An exception is thrown when the timed out refresh() destroys the protocol
        # and the still running apply() attempts to reference it
        with pytest.raises(AttributeError):
            # Start refresh()
            refresh_task = asyncio.create_task(
                coordinator.async_request_refresh())

            # Start concurrent apply()
            await asyncio.sleep(.5)
            await coordinator.apply()

            # Wait for refresh to finish
            await refresh_task


async def test_concurrent_network_access_with_lock(
    hass: HomeAssistant,
) -> None:
    """Test concurrent network access is prevented via the lock."""

    # Create dummy device
    device = AC("0.0.0.0", 0, 0)

    # Create coordinator
    coordinator = MideaDeviceUpdateCoordinator(hass, device)

    # Setup a mock LAN protocol
    _mock_lan_protocol(device._lan)

    # Check that concurrent calls to network actions don't throw when protected with a lock
    refresh_task = asyncio.create_task(coordinator.async_request_refresh())

    # Start concurrent apply()
    await asyncio.sleep(.5)
    await coordinator.apply()

    # Wait for refresh to finish
    await refresh_task


async def test_refresh_apply_race_condition(
    hass: HomeAssistant,
) -> None:
    """Test that a race conditions exists between refresh() and apply()."""

    async def _slow_refresh() -> None:
        await asyncio.sleep(1)
        mock_device.target_temperature = 20

    # Create a dummy device with a slow refresh
    mock_device = MagicMock()
    mock_device.refresh = _slow_refresh
    mock_device.apply = AsyncMock()
    mock_device.target_temperature = 17

    # Create our coordinator without using a device proxy
    with patch("custom_components.midea_ac.coordinator.MideaDeviceProxy") as mock_proxy:
        mock_proxy.return_value = mock_device
        coordinator = MideaDeviceUpdateCoordinator(hass, mock_device)

    # Start a slow refresh
    refresh_task = asyncio.create_task(coordinator.async_request_refresh())
    await asyncio.sleep(0.5)

    # Attempt to set an attribute during slow refresh
    coordinator.device.target_temperature = 10
    assert coordinator.device.target_temperature == 10
    await coordinator.apply()

    # Wait for refresh to complete
    await refresh_task

    # Assert that set attribute was replaced by teh refresh value
    assert coordinator.device.target_temperature == 20


async def test_refresh_apply_race_condition_with_proxy(
    hass: HomeAssistant,
) -> None:
    """Test that no race conditions exsits refresh() and apply() when using a device proxy."""

    async def _slow_refresh() -> None:
        await asyncio.sleep(1)
        mock_device.target_temperature = 20

    # Create a dummy device with a slow refresh
    mock_device = MagicMock()
    mock_device.refresh = _slow_refresh
    mock_device.apply = AsyncMock()
    mock_device.target_temperature = 17

    # Create coordinator with proxy object
    coordinator = MideaDeviceUpdateCoordinator(hass, mock_device)

    # Start a slow refresh
    refresh_task = asyncio.create_task(coordinator.async_request_refresh())
    await asyncio.sleep(0.5)

    # Attempt to set an attribute during slow refresh
    coordinator.device.target_temperature = 10
    assert coordinator.device.target_temperature == 10
    await coordinator.apply()

    # Wait for refresh to complete
    await refresh_task

    # Assert that attribute was set correctly
    assert coordinator.device.target_temperature == 10
