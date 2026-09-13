"""Tests for the number platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from msmart.device import AirConditioner as AC

from custom_components.midea_ac.climate import MideaClimateACDevice
from custom_components.midea_ac.device_proxy import MideaDeviceProxy
from custom_components.midea_ac.number import MideaFanSpeedNumber


@pytest.mark.parametrize("value", [1.0, 22.0, 23.0, 99.0, 100.0])
async def test_custom_fan_speed_float(
    hass: HomeAssistant,
    value: float,
) -> None:
    """Number writes must leave climate fan mode readable before a refresh."""
    device = MideaDeviceProxy(AC("0.0.0.0", 0, 0))
    coordinator = MagicMock()
    coordinator.device = device
    coordinator.apply = AsyncMock()
    number = MideaFanSpeedNumber(coordinator)
    climate = MideaClimateACDevice(hass, coordinator, {})

    await number.async_set_native_value(value)

    assert isinstance(device.fan_speed, int)
    assert device.fan_speed == value
    assert number.native_value == value
    expected_mode = (
        device.fan_speed.name.lower()
        if isinstance(device.fan_speed, AC.FanSpeed) else "custom"
    )
    assert climate.fan_mode == expected_mode
    coordinator.apply.assert_awaited_once_with()
