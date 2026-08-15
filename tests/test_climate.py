"""Tests for the climate platform."""

import logging
from enum import Flag
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate.const import (PRESET_AWAY, PRESET_BOOST,
                                                    PRESET_ECO, PRESET_NONE,
                                                    PRESET_SLEEP,
                                                    ClimateEntityFeature,
                                                    HVACMode)
from homeassistant.core import HomeAssistant
from msmart.device import AirConditioner as AC
from msmart.device import CommercialAirConditioner as CC
from msmart.utils import MideaIntEnum

from custom_components.midea_ac.climate import (ClimateConfig,
                                                MideaClimateACDevice,
                                                MideaClimateCCDevice,
                                                MideaClimateDevice)
from custom_components.midea_ac.const import PRESET_IECO, PRESET_SILENT

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


async def test_base_config(
    hass: HomeAssistant,
):
    """Test basic config is properly configured"""

    # Mock the device
    mock_device = AC("0.0.0.0", 0, 0)

    # Mock the coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.apply = AsyncMock()
    mock_coordinator.device = mock_device

    # Create climate device with config
    config = ClimateConfig(
        temperature_step=1,
        min_target_temperature=17,
        max_target_temperature=30,
        supported_operation_modes=[],
        supported_fan_speeds=[],
        supported_swing_modes=[],
        supported_preset_modes=[],
    )
    climate_device = MideaClimateDevice(hass, mock_coordinator, config)

    assert climate_device

    # Assert target temperature setting match
    assert climate_device.target_temperature_step == config.temperature_step
    assert climate_device.min_temp == config.min_target_temperature
    assert climate_device.max_temp == config.max_target_temperature

    # Assert HVAC modes is defined and OFF is always present
    assert climate_device.hvac_modes is not None
    assert HVACMode.OFF in climate_device.hvac_modes

    # Fan modes should be defined and empty
    assert climate_device.fan_modes is not None
    assert climate_device.fan_modes == []

    # Swing modes should be defined and empty
    assert climate_device.swing_modes is not None
    assert climate_device.swing_modes == []

    # Preset modes should be defined and empty
    assert climate_device.preset_modes is not None
    assert climate_device.preset_modes == []

    # Create climate device with config
    config = ClimateConfig(
        temperature_step=1,
        min_target_temperature=17,
        max_target_temperature=30,
        supported_operation_modes=[],
        supported_fan_speeds=[AC.FanSpeed.AUTO],
        supported_swing_modes=[AC.SwingMode.BOTH],
        supported_preset_modes=[PRESET_ECO],
    )
    climate_device = MideaClimateDevice(hass, mock_coordinator, config)

    assert climate_device

    # Assert fan modes are supported
    assert climate_device.supported_features & ClimateEntityFeature.FAN_MODE
    assert climate_device.fan_modes == ["auto"]

    # Assert swing modes are supported
    assert climate_device.supported_features & ClimateEntityFeature.SWING_MODE
    assert climate_device.swing_modes == ["both"]

    # Assert preset modes are supported
    assert climate_device.supported_features & ClimateEntityFeature.PRESET_MODE
    assert climate_device.preset_modes == ["eco"]


@pytest.mark.parametrize(
    ("device_class", "config_modes"),
    [
        (AC, []),
        (AC, [AC.SwingMode.OFF]),
        (AC, [AC.SwingMode.OFF, AC.SwingMode.BOTH]),
        (CC, []),
        (CC, [CC.SwingMode.OFF]),
        (CC, [CC.SwingMode.OFF, CC.SwingMode.VERTICAL]),
    ],
)
async def test_swing_mode_config(
    hass: HomeAssistant,
    device_class: type[AC | CC],
    config_modes: list[MideaIntEnum],
):
    """Test swing modes are properly configured"""

    # Mock the device
    mock_device = device_class("0.0.0.0", 0, 0)
    mock_device._supported_swing_modes = config_modes

    # Mock the coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.apply = AsyncMock()
    mock_coordinator.device = mock_device

    # Create climate device with config
    climate_device = None
    if device_class == AC:
        climate_device = MideaClimateACDevice(hass, mock_coordinator, {})
    elif device_class == CC:
        climate_device = MideaClimateCCDevice(hass, mock_coordinator, {})

    assert climate_device

    # Assert feature flag is set if modes are present
    if config_modes and config_modes != [device_class.SwingMode.OFF]:
        assert ClimateEntityFeature.SWING_MODE & climate_device.supported_features

    # Climate device should always have the property defined
    assert climate_device.swing_modes is not None

    # Assert configured modes are present
    assert climate_device.swing_modes == [m.name.lower()
                                          for m in config_modes]


@pytest.mark.parametrize(
    ("device_class", "config_modes"),
    [
        (AC, []),
        (AC, [AC.FanSpeed.AUTO]),
        (CC, []),
        (CC, [CC.FanSpeed.L4]),
    ],
)
async def test_fan_speed_config(
    hass: HomeAssistant,
    device_class: type[AC | CC],
    config_modes: list[MideaIntEnum],
):
    """Test fan speeds are properly configured"""

    # Mock the device
    mock_device = device_class("0.0.0.0", 0, 0)
    mock_device._supported_fan_speeds = config_modes

    # Mock the coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.apply = AsyncMock()
    mock_coordinator.device = mock_device

    # Create climate device with config
    climate_device = None
    if device_class == AC:
        climate_device = MideaClimateACDevice(hass, mock_coordinator, {})
    elif device_class == CC:
        climate_device = MideaClimateCCDevice(hass, mock_coordinator, {})

    assert climate_device

    # Assert feature flag is set if modes are present
    if config_modes:
        assert ClimateEntityFeature.FAN_MODE & climate_device.supported_features

    # Climate device should always have the property defined
    assert climate_device.fan_modes is not None

    # Assert configured modes are present
    assert climate_device.fan_modes == [m.name.lower()
                                        for m in config_modes]


@pytest.mark.parametrize(
    ("device_class", "config_modes"),
    [
        (AC, (True, None, PRESET_NONE)),  # Always supported
        (AC, (True, None, PRESET_SLEEP)),  # Always supported
        (AC, (False, AC.Capability.ECO, PRESET_ECO)),  # Defaults to supported
        (AC, (True, AC.Capability.IECO, PRESET_IECO)),
        (CC, (True, None, PRESET_NONE)),  # Always supported
        (CC, (False, CC.Capability.ECO, PRESET_ECO)),  # Defaults to supported
        (CC, (False, CC.Capability.SLEEP, PRESET_SLEEP)),  # Defaults to supported

    ],
)
async def test_preset_modes(
    hass: HomeAssistant,
    device_class: type[AC | CC],
    config_modes: tuple[bool, Flag, str],
):
    """Test preset modes are properly configured"""

    support, capability, preset = config_modes

    # Mock the device & it's capbilities
    mock_device = device_class("0.0.0.0", 0, 0)
    if capability:
        mock_device._capabilities.set(capability, support)

    # Mock the coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.apply = AsyncMock()
    mock_coordinator.device = mock_device

    # Create climate device with config
    climate_device = None
    if device_class == AC:
        climate_device = MideaClimateACDevice(hass, mock_coordinator, {})
    elif device_class == CC:
        climate_device = MideaClimateCCDevice(hass, mock_coordinator, {})

    assert climate_device

    # Assert feature flag is set
    assert ClimateEntityFeature.PRESET_MODE & climate_device.supported_features

    # Climate device should always have the property defined
    assert climate_device.preset_modes is not None

    # Assert configured modes are present
    if support:
        assert preset in climate_device.preset_modes
    else:
        assert preset not in climate_device.preset_modes


@pytest.mark.parametrize(
    ("device_class", "config_modes"),
    [
        (AC, (PRESET_ECO, "eco", AC.Capability.ECO)),
        (AC, (PRESET_IECO, "ieco", AC.Capability.IECO)),
        (AC, (PRESET_BOOST, "turbo", AC.Capability.TURBO)),
        (AC, (PRESET_AWAY, "freeze_protection", AC.Capability.FREEZE_PROTECTION)),
        (CC, (PRESET_ECO, "eco", CC.Capability.ECO)),
        (CC, (PRESET_SILENT, "silent", CC.Capability.SILENT)),
        (CC, (PRESET_SLEEP, "sleep", CC.Capability.SLEEP)),

    ],
)
async def test_preset_mode_requires_capability(
    hass: HomeAssistant,
    device_class: type[AC | CC],
    config_modes: tuple[str, str, Flag],
):
    """Test preset mode is gated by support for that preset"""

    # Mock the device
    mock_device = device_class("0.0.0.0", 0, 0)

    # Mock the coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.apply = AsyncMock()
    mock_coordinator.device = mock_device

    # Create climate device with config
    climate_device = None
    if device_class == AC:
        climate_device = MideaClimateACDevice(hass, mock_coordinator, {})
    elif device_class == CC:
        climate_device = MideaClimateCCDevice(hass, mock_coordinator, {})

    preset, attr, capability = config_modes

    for support in [True, False]:
        # Enable/disable the capability for the target preset
        mock_device._capabilities.set(capability, support)

        # Assert device reports preset mode when active AND supported
        setattr(mock_device, attr, True)
        if support:
            assert climate_device.preset_mode == preset
        else:
            assert climate_device.preset_mode != preset

        # Assert device doesnt report preset mode when its inactive
        setattr(mock_device, attr, False)
        assert climate_device.preset_mode != preset
