"""Tests for the climate platform."""

import logging
from typing import Mapping
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate.const import (PRESET_ECO, PRESET_SLEEP,
                                                    ClimateEntityFeature,
                                                    HVACAction, HVACMode)
from homeassistant.core import HomeAssistant
from msmart.device import AirConditioner as AC
from msmart.device import CommercialAirConditioner as CC
from msmart.utils import MideaIntEnum

from custom_components.midea_ac.climate import (ClimateConfig,
                                                MideaClimateACDevice,
                                                MideaClimateCCDevice,
                                                MideaClimateDevice)

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
        (AC, {}),
        (AC, {PRESET_ECO: "_supports_eco"}),
        (CC, {}),
        (CC, {PRESET_SLEEP: "_supports_sleep"}),
    ],
)
async def test_preset_modes(
    hass: HomeAssistant,
    device_class: type[AC | CC],
    config_modes: Mapping[str, str],
):
    """Test preset modes are properly configured"""

    # Mock the device
    mock_device = device_class("0.0.0.0", 0, 0)
    for _, v in config_modes.items():
        setattr(mock_device, v, True)

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
        assert ClimateEntityFeature.PRESET_MODE & climate_device.supported_features

    # Climate device should always have the property defined
    assert climate_device.preset_modes is not None

    # Assert configured modes are present
    for k, _ in config_modes.items():
        assert k in climate_device.preset_modes


@pytest.mark.parametrize(
    ("power_state", "operational_mode", "expected_action"),
    [
        (False, AC.OperationalMode.COOL, HVACAction.OFF),
        (True, AC.OperationalMode.COOL, HVACAction.COOLING),
        (True, AC.OperationalMode.HEAT, HVACAction.HEATING),
        (True, AC.OperationalMode.DRY, HVACAction.DRYING),
        (True, AC.OperationalMode.SMART_DRY, HVACAction.DRYING),
        (True, AC.OperationalMode.FAN_ONLY, HVACAction.FAN),
    ],
)
async def test_ac_hvac_action(
    hass: HomeAssistant,
    power_state: bool,
    operational_mode: AC.OperationalMode,
    expected_action: HVACAction,
):
    """Test hvac_action reflects the mode for the AC device."""

    mock_device = AC("0.0.0.0", 0, 0)
    mock_device._power_state = power_state
    mock_device._operational_mode = operational_mode

    mock_coordinator = MagicMock()
    mock_coordinator.apply = AsyncMock()
    mock_coordinator.device = mock_device

    climate_device = MideaClimateACDevice(hass, mock_coordinator, {})

    assert climate_device.hvac_action == expected_action


@pytest.mark.parametrize(
    ("indoor_temperature", "target_temperature", "expected_action"),
    [
        (None, 24, HVACAction.IDLE),
        (26, 24, HVACAction.COOLING),
        (22, 24, HVACAction.HEATING),
        (24, 24, HVACAction.IDLE),
    ],
)
async def test_ac_hvac_action_auto_mode(
    hass: HomeAssistant,
    indoor_temperature: float | None,
    target_temperature: float,
    expected_action: HVACAction,
):
    """Test hvac_action is estimated from the temperature delta in auto mode."""

    mock_device = AC("0.0.0.0", 0, 0)
    mock_device._power_state = True
    mock_device._operational_mode = AC.OperationalMode.AUTO
    mock_device._indoor_temperature = indoor_temperature
    mock_device._target_temperature = target_temperature

    mock_coordinator = MagicMock()
    mock_coordinator.apply = AsyncMock()
    mock_coordinator.device = mock_device

    climate_device = MideaClimateACDevice(hass, mock_coordinator, {})

    assert climate_device.hvac_action == expected_action


async def test_ac_hvac_action_defrosting(
    hass: HomeAssistant,
):
    """Test hvac_action reports defrosting while heating with defrost active."""

    mock_device = AC("0.0.0.0", 0, 0)
    mock_device._power_state = True
    mock_device._operational_mode = AC.OperationalMode.HEAT
    mock_device._defrost_active = True

    mock_coordinator = MagicMock()
    mock_coordinator.apply = AsyncMock()
    mock_coordinator.device = mock_device

    climate_device = MideaClimateACDevice(hass, mock_coordinator, {})

    assert climate_device.hvac_action == HVACAction.DEFROSTING


@pytest.mark.parametrize(
    ("power_state", "operational_mode", "expected_action"),
    [
        (False, CC.OperationalMode.COOL, HVACAction.OFF),
        (True, CC.OperationalMode.COOL, HVACAction.COOLING),
        (True, CC.OperationalMode.HEAT, HVACAction.HEATING),
        (True, CC.OperationalMode.DRY, HVACAction.DRYING),
        (True, CC.OperationalMode.FAN, HVACAction.FAN),
    ],
)
async def test_cc_hvac_action(
    hass: HomeAssistant,
    power_state: bool,
    operational_mode: "CC.OperationalMode",
    expected_action: HVACAction,
):
    """Test hvac_action reflects the mode for the CC device."""

    mock_device = CC("0.0.0.0", 0, 0)
    mock_device._power_state = power_state
    mock_device._operational_mode = operational_mode

    mock_coordinator = MagicMock()
    mock_coordinator.apply = AsyncMock()
    mock_coordinator.device = mock_device

    climate_device = MideaClimateCCDevice(hass, mock_coordinator, {})

    assert climate_device.hvac_action == expected_action
