#!/usr/bin/env python3
"""Test script for external temperature sensor functionality."""

import asyncio
import sys
from unittest.mock import Mock, MagicMock

# Mock Home Assistant modules
sys.modules['homeassistant'] = Mock()
sys.modules['homeassistant.components'] = Mock()
sys.modules['homeassistant.components.climate'] = Mock()
sys.modules['homeassistant.components.climate.const'] = Mock()
sys.modules['homeassistant.config_entries'] = Mock()
sys.modules['homeassistant.const'] = Mock()
sys.modules['homeassistant.core'] = Mock()
sys.modules['homeassistant.exceptions'] = Mock()
sys.modules['homeassistant.helpers'] = Mock()
sys.modules['homeassistant.helpers.config_validation'] = Mock()
sys.modules['homeassistant.helpers.entity_platform'] = Mock()
sys.modules['msmart'] = Mock()
sys.modules['msmart.device'] = Mock()

# Now import our modules
from custom_components.midea_ac.climate import MideaClimateACDevice
from custom_components.midea_ac.coordinator import MideaDeviceUpdateCoordinator
from custom_components.midea_ac.const import CONF_EXTERNAL_TEMP_SENSOR

def test_external_temp_sensor():
    """Test external temperature sensor functionality."""
    print("Testing external temperature sensor functionality...")
    
    # Mock Home Assistant instance
    hass = Mock()
    
    # Mock device and coordinator
    mock_device = Mock()
    mock_device.indoor_temperature = 22.0
    mock_device.beep = False
    mock_device.min_target_temperature = 16.0
    mock_device.max_target_temperature = 30.0
    mock_device.supported_operation_modes = []
    mock_device.supported_fan_speeds = []
    mock_device.supported_swing_modes = []
    mock_device.supports_freeze_protection = False
    mock_device.supports_eco = False
    mock_device.supports_turbo = False
    mock_device.supports_ieco = False
    
    coordinator = Mock(spec=MideaDeviceUpdateCoordinator)
    coordinator.device = mock_device
    
    # Test without external sensor
    options_no_external = {
        CONF_EXTERNAL_TEMP_SENSOR: None
    }
    
    climate_device = MideaClimateACDevice(hass, coordinator, options_no_external)
    assert climate_device.current_temperature == 22.0
    print("✓ Internal temperature sensor works correctly")
    
    # Test with external sensor - valid state
    external_sensor_entity_id = "sensor.room_temperature"
    options_with_external = {
        CONF_EXTERNAL_TEMP_SENSOR: external_sensor_entity_id
    }
    
    # Mock external sensor state
    mock_sensor_state = Mock()
    mock_sensor_state.state = "25.5"
    hass.states.get.return_value = mock_sensor_state
    
    climate_device = MideaClimateACDevice(hass, coordinator, options_with_external)
    assert climate_device.current_temperature == 25.5
    print("✓ External temperature sensor works correctly")
    
    # Test with external sensor - unavailable state
    mock_sensor_state.state = "unavailable"
    climate_device = MideaClimateACDevice(hass, coordinator, options_with_external)
    assert climate_device.current_temperature == 22.0  # Falls back to internal
    print("✓ Fallback to internal sensor when external is unavailable")
    
    # Test with external sensor - invalid state
    mock_sensor_state.state = "invalid_temp"
    climate_device = MideaClimateACDevice(hass, coordinator, options_with_external)
    assert climate_device.current_temperature == 22.0  # Falls back to internal
    print("✓ Fallback to internal sensor when external has invalid state")
    
    # Test with external sensor - sensor not found
    hass.states.get.return_value = None
    climate_device = MideaClimateACDevice(hass, coordinator, options_with_external)
    assert climate_device.current_temperature == 22.0  # Falls back to internal
    print("✓ Fallback to internal sensor when external sensor not found")
    
    # Test state attributes
    hass.states.get.return_value = mock_sensor_state
    mock_sensor_state.state = "24.0"
    climate_device = MideaClimateACDevice(hass, coordinator, options_with_external)
    
    attributes = climate_device.extra_state_attributes
    assert "external_temp_sensor" in attributes
    assert attributes["external_temp_sensor"] == external_sensor_entity_id
    assert "external_temp_sensor_state" in attributes
    assert "internal_temperature" in attributes
    print("✓ State attributes include external sensor information")
    
    print("\nAll tests passed! ✓")

if __name__ == "__main__":
    test_external_temp_sensor()
