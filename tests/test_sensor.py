"""Tests for the sensor platform."""

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from msmart.device import AirConditioner as AC
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.midea_ac.const import DOMAIN
from custom_components.midea_ac.coordinator import MideaDeviceUpdateCoordinator
from custom_components.midea_ac.sensor import (MideaEnergySensor,
                                               async_setup_entry)


async def test_energy_sensor_request_enable(
    hass: HomeAssistant
) -> None:
    """Test AC device energy sensors enable energy requests when added to HA."""

    # Create a dummy device and coordinator
    device = AC("0.0.0.0", 0, 0)
    coordinator = MideaDeviceUpdateCoordinator(hass, device)

    # Create sensors
    sensors = [
        MideaEnergySensor(
            coordinator,
            "real_time_power_usage",
            SensorDeviceClass.POWER,
            UnitOfPower.WATT,
            "real_time_power_usage",
            format=AC.EnergyDataFormat.BCD,
            scale=1.0,
        ),
        MideaEnergySensor(
            coordinator,
            "total_energy_usage",
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "total_energy_usage",
            format=AC.EnergyDataFormat.BINARY,
            scale=1.0,
            state_class=SensorStateClass.TOTAL,
        )
    ]

    # Add each sensor to HA
    for sensor in sensors:
        await sensor.async_added_to_hass()

    # Verify energy requests are enabled when sensor is added to HA
    assert coordinator._energy_sensors == len(sensors)
    assert device.enable_energy_usage_requests == True

    # Remove 1 sensor from HA
    await sensors[0].async_will_remove_from_hass()
    assert coordinator._energy_sensors == 1
    assert device.enable_energy_usage_requests == True

    # Verify energy requests are disabled when last sensor is removed
    await sensors[1].async_will_remove_from_hass()
    assert coordinator._energy_sensors == 0
    assert device.enable_energy_usage_requests == False

    await coordinator.async_shutdown()


async def test_setup_without_energy_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor platform sets up when energy options are missing."""

    # Create a dummy device and coordinator
    device = AC("0.0.0.0", 0, 0)
    coordinator = MideaDeviceUpdateCoordinator(hass, device)

    # Create a config entry without energy sensor options
    mock_config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = coordinator

    entities = []

    def add_entities(new_entities, update_before_add=False) -> None:
        entities.extend(new_entities)

    # Verify setup doesn't raise and energy sensors are created
    await async_setup_entry(hass, mock_config_entry, add_entities)
    assert any(isinstance(e, MideaEnergySensor) for e in entities)

    await coordinator.async_shutdown()
