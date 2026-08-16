"""Tests for the data update coordinator."""

import asyncio
import logging
from typing import NoReturn
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from msmart.device import AirConditioner as AC
from msmart.lan import _LanProtocol

from custom_components.midea_ac.binary_sensor import (MideaGroup2BinarySensor,
                                                      MideaGroup5BinarySensor)
from custom_components.midea_ac.coordinator import (
    MideaCoordinatorEntity, MideaDeviceUpdateCoordinator)
from custom_components.midea_ac.sensor import (MideaGroup1Sensor,
                                               MideaGroup2Sensor,
                                               MideaGroup5Sensor,
                                               MideaGroup7Sensor,
                                               MideaGroup11Sensor)

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

        # Clean up coordinator
        await coordinator.async_shutdown()


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

    # Clean up coordinator
    await coordinator.async_shutdown()


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

    # Assert that set attribute was replaced by the refresh value
    assert coordinator.device.target_temperature == 20

    # Clean up coordinator
    await coordinator.async_shutdown()


async def test_refresh_apply_race_condition_with_proxy(
    hass: HomeAssistant,
) -> None:
    """Test that no race condition exists between refresh() and apply() when using a device proxy."""

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

    # Clean up coordinator
    await coordinator.async_shutdown()


async def test_group5_entity_request_enable(
    hass: HomeAssistant
) -> None:
    """Test AC device group5 entities enable requests when added to HA."""

    # Create a dummy device and coordinator
    device = AC("0.0.0.0", 0, 0)
    coordinator = MideaDeviceUpdateCoordinator(hass, device)

    # Create entities
    entities = [
        MideaGroup5Sensor(
            coordinator,
            "outdoor_fan_speed",
            None,
            None,
            "outdoor_fan_speed",
        ),
        MideaGroup5BinarySensor(
            coordinator,
            "defrost_active",
            None,
            "defrost"
        )
    ]

    # Add each sensor to HA
    for entity in entities:
        await entity.async_added_to_hass()

    # Verify group 5 requests are enabled when entity is added to HA
    assert coordinator._group5_entities == len(entities)
    assert device.enable_group5_data_requests == True

    # Remove 1 entity from HA
    await entities[0].async_will_remove_from_hass()
    assert coordinator._group5_entities == 1
    assert device.enable_group5_data_requests == True

    # Verify group 5 requests are disabled when last entity is removed
    await entities[1].async_will_remove_from_hass()
    assert coordinator._group5_entities == 0
    assert device.enable_group5_data_requests == False

    await coordinator.async_shutdown()


async def test_entity_availability(
    hass: HomeAssistant
) -> None:
    """Test entity availability depends on both the device and the coordinator refresh."""

    # Create a mock device so online can be controlled directly
    mock_device = MagicMock()
    mock_device.online = True

    coordinator = MideaDeviceUpdateCoordinator(hass, mock_device)
    entity = MideaCoordinatorEntity(coordinator)

    # Online device with a successful refresh is available
    coordinator.last_update_success = True
    assert entity.available == True

    # Online device with a failed refresh is not available
    coordinator.last_update_success = False
    assert entity.available == False

    # Offline device is not available, even after a successful refresh
    mock_device.online = False
    coordinator.last_update_success = True
    assert entity.available == False

    await coordinator.async_shutdown()


async def test_group1_entity_request_enable(
    hass: HomeAssistant
) -> None:
    """Test AC device group1 entities enable requests when added to HA."""

    # Create a dummy device and coordinator
    device = AC("0.0.0.0", 0, 0)
    coordinator = MideaDeviceUpdateCoordinator(hass, device)

    # Create entities
    entities = [
        MideaGroup1Sensor(
            coordinator,
            "outdoor_coil_temperature",
            None,
            None,
            "outdoor_coil_temperature",
        )
    ]

    # Add each sensor to HA
    for entity in entities:
        await entity.async_added_to_hass()

    # Verify group 1 requests are enabled when entity is added to HA
    assert coordinator._group1_entities == len(entities)
    assert device.enable_group1_data_requests == True

    # Remove 1 entity from HA
    await entities[0].async_will_remove_from_hass()
    assert coordinator._group1_entities == 0
    assert device.enable_group1_data_requests == False

    await coordinator.async_shutdown()


async def test_group2_entity_request_enable(
    hass: HomeAssistant
) -> None:
    """Test AC device group2 entities enable requests when added to HA."""

    # Create a dummy device and coordinator
    device = AC("0.0.0.0", 0, 0)
    coordinator = MideaDeviceUpdateCoordinator(hass, device)

    # Create entities
    entities = [
        MideaGroup2Sensor(
            coordinator,
            "indoor_fan_speed",
            None,
            None,
            "indoor_fan_speed",
        ),
        MideaGroup2BinarySensor(
            coordinator,
            "water_pump_running",
            None,
            "water_pump"
        )
    ]

    # Add each sensor to HA
    for entity in entities:
        await entity.async_added_to_hass()

    # Verify group 2 requests are enabled when entity is added to HA
    assert coordinator._group2_entities == len(entities)
    assert device.enable_group2_data_requests == True

    # Remove 1 entity from HA
    await entities[0].async_will_remove_from_hass()
    assert coordinator._group2_entities == 1
    assert device.enable_group2_data_requests == True

    # Verify group 2 requests are disabled when last entity is removed
    await entities[1].async_will_remove_from_hass()
    assert coordinator._group2_entities == 0
    assert device.enable_group2_data_requests == False

    await coordinator.async_shutdown()


async def test_group7_entity_request_enable(
    hass: HomeAssistant
) -> None:
    """Test AC device group7 entities enable requests when added to HA."""

    # Create a dummy device and coordinator
    device = AC("0.0.0.0", 0, 0)
    coordinator = MideaDeviceUpdateCoordinator(hass, device)

    # Create entities
    entities = [
        MideaGroup7Sensor(
            coordinator,
            "outdoor_unit_power",
            None,
            None,
            "outdoor_unit_power",
        )
    ]

    # Add each sensor to HA
    for entity in entities:
        await entity.async_added_to_hass()

    # Verify group 7 requests are enabled when entity is added to HA
    assert coordinator._group7_entities == len(entities)
    assert device.enable_group7_data_requests == True

    # Remove 1 entity from HA
    await entities[0].async_will_remove_from_hass()
    assert coordinator._group7_entities == 0
    assert device.enable_group7_data_requests == False

    await coordinator.async_shutdown()


async def test_group11_entity_request_enable(
    hass: HomeAssistant
) -> None:
    """Test AC device group11 entities enable requests when added to HA."""

    # Create a dummy device and coordinator
    device = AC("0.0.0.0", 0, 0)
    coordinator = MideaDeviceUpdateCoordinator(hass, device)

    # Create entities
    entities = [
        MideaGroup11Sensor(
            coordinator,
            "horizontal_louvers_angle",
            None,
            None,
            "horizontal_louvers_angle",
        )
    ]

    # Add each sensor to HA
    for entity in entities:
        await entity.async_added_to_hass()

    # Verify group 11 requests are enabled when entity is added to HA
    assert coordinator._group11_entities == len(entities)
    assert device.enable_group11_data_requests == True

    # Remove 1 entity from HA
    await entities[0].async_will_remove_from_hass()
    assert coordinator._group11_entities == 0
    assert device.enable_group11_data_requests == False

    await coordinator.async_shutdown()
