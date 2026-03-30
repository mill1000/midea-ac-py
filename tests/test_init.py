"""Tests for the integration init."""

import logging
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from msmart.const import DeviceType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.midea_ac.const import (CONF_ADDITIONAL_OPERATION_MODES,
                                              CONF_CAPABILITY_OVERRIDES,
                                              CONF_DEVICE_TYPE,
                                              CONF_ENERGY_DATA_FORMAT,
                                              CONF_ENERGY_DATA_SCALE,
                                              CONF_ENERGY_SENSOR,
                                              CONF_POWER_SENSOR,
                                              CONF_SHOW_ALL_PRESETS,
                                              CONF_USE_FAN_ONLY_WORKAROUND,
                                              CONF_WORKAROUNDS, DOMAIN,
                                              EnergyFormat)

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

_MIGRATED_ENERGY_CONFIGS = {
    EnergyFormat._DEFAULT: {
        CONF_ENERGY_SENSOR: {CONF_ENERGY_DATA_FORMAT: EnergyFormat.BCD, CONF_ENERGY_DATA_SCALE: 1.0},
        CONF_POWER_SENSOR: {CONF_ENERGY_DATA_FORMAT: EnergyFormat.BCD, CONF_ENERGY_DATA_SCALE: 1.0},
    },
    EnergyFormat._ALTERNATE_A: {
        CONF_ENERGY_SENSOR: {CONF_ENERGY_DATA_FORMAT: EnergyFormat.BINARY, CONF_ENERGY_DATA_SCALE: 1.0},
        CONF_POWER_SENSOR: {CONF_ENERGY_DATA_FORMAT: EnergyFormat.BINARY, CONF_ENERGY_DATA_SCALE: 1.0},
    },
    EnergyFormat._ALTERNATE_B: {
        CONF_ENERGY_SENSOR: {CONF_ENERGY_DATA_FORMAT: EnergyFormat.BINARY, CONF_ENERGY_DATA_SCALE: 0.1},
        CONF_POWER_SENSOR: {CONF_ENERGY_DATA_FORMAT: EnergyFormat.BINARY, CONF_ENERGY_DATA_SCALE: 1.0},
    }
}


async def test_config_entry_migration_from_5(hass: HomeAssistant) -> None:
    """Test basic migration of config entry from 1.5"""

    # Create a mock v1.4 config entry
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=4,
        data={},  # Data is unchanged
        options={
            CONF_WORKAROUNDS: {
                CONF_ADDITIONAL_OPERATION_MODES: "dry heat",
                CONF_SHOW_ALL_PRESETS: True,
            }
        }
    )

    # Setup entry to trigger migration
    with patch(
        "custom_components.midea_ac.async_setup_entry",
        return_value=True,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Assert expected version
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 6

    # Grab options to test migration
    options = mock_config_entry.options

    # Verify old options are removed
    workarounds: dict[str, Any] = options.get(CONF_WORKAROUNDS)
    assert workarounds is not None
    assert CONF_ADDITIONAL_OPERATION_MODES not in workarounds
    assert CONF_SHOW_ALL_PRESETS not in workarounds

    # Verify expected overrides
    assert CONF_CAPABILITY_OVERRIDES in options
    assert """supported_modes: ["dry", "heat"]""" in options[CONF_CAPABILITY_OVERRIDES]
    assert """additional_capabilities: ["ECO", "FREEZE_PROTECTION", "TURBO"]""" in options[CONF_CAPABILITY_OVERRIDES]


async def test_config_entry_migration_from_4(hass: HomeAssistant) -> None:
    """Test migration of config entry from 1.4"""

    # Create a mock v1.4 config entry
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=4,
        data={},  # Expect data to include a device type after migration
        options={
        }
    )

    with patch(
        "custom_components.midea_ac.async_setup_entry",
        return_value=True,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 6
    assert mock_config_entry.data[CONF_DEVICE_TYPE] == DeviceType.AIR_CONDITIONER


async def test_config_entry_migration_from_3(hass: HomeAssistant) -> None:
    """Test basic migration of config entry from 1.3"""

    # Create a mock v1.3 config entry
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=3,
        data={},  # Data is unchanged
        options={
            "energy_format": EnergyFormat._ALTERNATE_A,
            CONF_USE_FAN_ONLY_WORKAROUND: False,
            CONF_SHOW_ALL_PRESETS: True,
        }
    )

    # Setup entry to trigger migration
    with patch(
        "custom_components.midea_ac.async_setup_entry",
        return_value=True,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Assert expected version
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 6

    # Grab options to test migration
    options = mock_config_entry.options

    # Assert certain keys were removed from options
    assert "energy_format" not in options
    assert CONF_USE_FAN_ONLY_WORKAROUND not in options
    assert CONF_SHOW_ALL_PRESETS not in options
    assert CONF_ADDITIONAL_OPERATION_MODES not in options

    # Assert new keys are present in options
    assert CONF_ENERGY_SENSOR in options
    assert CONF_POWER_SENSOR in options
    assert CONF_WORKAROUNDS in options

    # Assert energy/power sensor configs are present
    for key in [CONF_ENERGY_SENSOR, CONF_POWER_SENSOR]:
        config = options.get(key)
        assert config
        assert CONF_ENERGY_DATA_FORMAT in config
        assert CONF_ENERGY_DATA_SCALE in config

    # Assert workarounds were grouped
    for key in [CONF_USE_FAN_ONLY_WORKAROUND]:
        workarounds = options.get(CONF_WORKAROUNDS)
        assert workarounds
        assert key in workarounds

    # Verify expected overrides
    assert CONF_CAPABILITY_OVERRIDES in options
    assert """additional_capabilities: ["ECO", "FREEZE_PROTECTION", "TURBO"]""" in options[CONF_CAPABILITY_OVERRIDES]


@pytest.mark.parametrize(
    ("energy_format", "expected_configs"),
    [
        (EnergyFormat._DEFAULT,
         _MIGRATED_ENERGY_CONFIGS[EnergyFormat._DEFAULT]),
        (EnergyFormat._ALTERNATE_A,
         _MIGRATED_ENERGY_CONFIGS[EnergyFormat._ALTERNATE_A]),
        (EnergyFormat._ALTERNATE_B,
         _MIGRATED_ENERGY_CONFIGS[EnergyFormat._ALTERNATE_B]),
    ],
)
async def test_config_entry_migration_from_3_energy_formats(
    hass: HomeAssistant,
    energy_format: EnergyFormat,
    expected_configs: dict[str, Any],
) -> None:
    """Test handling of energy format when migrating 1.3"""

    # Create a mock v1.3 config entry
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=3,
        data={},  # Data is unchanged
        options={
            "energy_format": energy_format,
        }
    )

    # Setup entry to trigger migration
    with patch(
        "custom_components.midea_ac.async_setup_entry",
        return_value=True,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Assert expected version
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 6

    # Grab options to test migration
    options = mock_config_entry.options

    # Assert old key was removed from options
    assert "energy_format" not in options

    # Assert energy/power sensor configs match
    for key in [CONF_ENERGY_SENSOR, CONF_POWER_SENSOR]:
        config = options.get(key)
        assert config
        assert config == expected_configs[key]


@pytest.mark.parametrize(
    ("use_alternate", "expected_configs"),
    [
        (False, _MIGRATED_ENERGY_CONFIGS[EnergyFormat._DEFAULT]),
        (True,  _MIGRATED_ENERGY_CONFIGS[EnergyFormat._ALTERNATE_B]),
    ],
)
async def test_config_entry_migration_from_2(
    hass: HomeAssistant,
    use_alternate: bool,
    expected_configs: dict[str, Any],
) -> None:
    """Test basic migration of config entry from 1.2"""

    # Create a mock v1.2 config entry
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=2,
        data={},  # Data is unchanged
        options={
            "use_alternate_energy_format": use_alternate,
        }
    )

    # Setup entry to trigger migration
    with patch(
        "custom_components.midea_ac.async_setup_entry",
        return_value=True,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Assert expected version
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 6

    # Grab options to test migration
    options = mock_config_entry.options

    # Assert old key was removed from options
    assert "use_alternate_energy_format" not in options

    # Assert energy/power sensor configs match
    for key in [CONF_ENERGY_SENSOR, CONF_POWER_SENSOR]:
        config = options.get(key)
        assert config
        assert config == expected_configs[key]


async def test_config_entry_migration_from_1(hass: HomeAssistant) -> None:
    """Test migration of config entry from 1.1"""

    # Create a mock v1.1 config entry
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=1,
        unique_id=1234,  # Unique ID not a string
        data={},  # Data is unchanged
    )

    with patch(
        "custom_components.midea_ac.async_setup_entry",
        return_value=True,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 6
    assert isinstance(mock_config_entry.unique_id, str)
