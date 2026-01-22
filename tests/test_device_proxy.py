"""Tests for the device proxy."""


import logging
from unittest.mock import patch

import pytest
from msmart.device import AirConditioner as AC
from msmart.device import CommercialAirConditioner as CC

from custom_components.midea_ac.coordinator import MideaDeviceProxy

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


async def test_device_proxy() -> None:
    """Test basic device proxy features"""

    # Create dummy device
    device = AC("0.0.0.0", 0, 0)

    # Create proxy
    proxy = MideaDeviceProxy(device)

    # Check basic proxy attributes
    assert proxy._device == device
    assert proxy._staged == {}

    # Assert proxy prevents setting nonexistent attributes
    with pytest.raises(AttributeError, match="Cannot set attribute"):
        proxy.some_nonexistent_attribute = 2

    # Assert proxy prevents setting read-only attributes
    with pytest.raises(AttributeError, match="Cannot set read-only property"):
        proxy.indoor_humidity = 2

    # Assert that accessing a nonexist attribute still throws
    with pytest.raises(AttributeError, match="object has no attribute"):
        assert proxy.another_nonexistent_attribute == None


async def test_device_proxy_staging() -> None:
    """Test the staging behavior of the proxy"""

    # Create dummy device
    device = AC("0.0.0.0", 0, 0)

    # Create proxy
    proxy = MideaDeviceProxy(device)

    # Set a device attribute
    device.target_temperature = 25

    # Assert proxy mirrors device
    assert proxy.target_temperature == device.target_temperature

    # Set attribute via proxy
    proxy.target_temperature = 10

    # Verify setting an attribute stages it
    assert "target_temperature" in proxy._staged
    assert proxy._staged["target_temperature"] == 10

    # Verify staged attributes is returned by proxy
    assert proxy.target_temperature == 10

    # Assert value hasn't applied to device
    assert device.target_temperature == 25

    # Apply via proxy
    with patch("custom_components.midea_ac.config_flow.AC.apply") as apply_mock:
        await proxy.apply()
        apply_mock.assert_awaited_once()

    # Verify attributes is no longer staged
    assert "target_temperature" not in proxy._staged

    # Assert device has updated value
    assert device.target_temperature == 10

    # Assert proxy mirrors device
    assert proxy.target_temperature == device.target_temperature


async def test_device_proxy_enum() -> None:
    """Test that enum classes are also proxied"""

    # Create dummy device
    device = CC("0.0.0.0", 0, 0)

    # Create proxy
    proxy = MideaDeviceProxy(device)

    # Assert that enum classes proxy
    assert device.FanSpeed == proxy.FanSpeed
    assert device.OperationalMode == proxy.OperationalMode

    assert device.FanSpeed.AUTO == proxy.FanSpeed.AUTO
    assert device.OperationalMode.DRY == proxy.OperationalMode.DRY
