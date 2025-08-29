"""Sensor platform for Midea Smart AC."""
from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.sensor import (SensorDeviceClass, SensorEntity,
                                             SensorStateClass)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (PERCENTAGE, UnitOfEnergy, UnitOfPower,
                                 UnitOfTemperature)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from msmart.device import AirConditioner as AC

from .const import (CONF_ENERGY_DATA_FORMAT, CONF_ENERGY_DATA_SCALE,
                    CONF_ENERGY_SENSOR, CONF_POWER_SENSOR, DOMAIN,
                    EnergyFormat)
from .coordinator import MideaCoordinatorEntity, MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup the sensor platform for Midea Smart AC."""

    _LOGGER.info("Setting up sensor platform.")

    # Fetch coordinator from global data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    def _get_energy_config(key: str) -> tuple[EnergyFormat, float]:
        config = config_entry.options.get(key)
        format = AC.EnergyDataFormat.get_from_name(
            config.get(CONF_ENERGY_DATA_FORMAT).upper())
        scale = config.get(CONF_ENERGY_DATA_SCALE)
        return format, scale

    # Configure energy format
    energy_data_format, energy_scale = _get_energy_config(CONF_ENERGY_SENSOR)
    _LOGGER.info(
        "Using energy format %r (scale: %f) for device ID %s.", energy_data_format, energy_scale, coordinator.device.id)

    power_data_format, power_scale = _get_energy_config(CONF_POWER_SENSOR)
    _LOGGER.info(
        "Using power format %r (scale: %f) for device ID %s.", power_data_format, power_scale, coordinator.device.id)

    entities = [
        # Temperature sensors
        MideaSensor(
            coordinator,
            "indoor_temperature",
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            "indoor_temperature",
        ),
        MideaSensor(
            coordinator,
            "outdoor_temperature",
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            "outdoor_temperature",
        ),

        # Energy sensors
        MideaEnergySensor(
            coordinator,
            "total_energy_usage",
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "total_energy_usage",
            format=energy_data_format,
            scale=energy_scale,
            state_class=SensorStateClass.TOTAL,
        ),
        MideaEnergySensor(
            coordinator,
            "current_energy_usage",
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "current_energy_usage",
            format=energy_data_format,
            scale=energy_scale,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        MideaEnergySensor(
            coordinator,
            "real_time_power_usage",
            SensorDeviceClass.POWER,
            UnitOfPower.WATT,
            "real_time_power_usage",
            format=power_data_format,
            scale=power_scale,
        )
    ]

    if coordinator.device.supports_humidity:
        entities.append(MideaSensor(
            coordinator,
            "indoor_humidity",
            SensorDeviceClass.HUMIDITY,
            PERCENTAGE,
            "indoor_humidity",
        ))

    add_entities(entities)


class MideaSensor(MideaCoordinatorEntity, SensorEntity):
    """Generic sensor class for Midea AC."""

    def __init__(self,
                 coordinator: MideaDeviceUpdateCoordinator,
                 prop: str,
                 device_class: SensorDeviceClass,
                 unit: str,
                 translation_key: Optional[str] = None,
                 *,
                 state_class: SensorStateClass = SensorStateClass.MEASUREMENT,
                 ) -> None:
        MideaCoordinatorEntity.__init__(self, coordinator)

        self._prop = prop
        self._device_class = device_class
        self._state_class = state_class
        self._unit = unit
        self._attr_translation_key = translation_key

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        return {
            "identifiers": {
                (DOMAIN, self._device.id)
            },
        }

    @property
    def has_entity_name(self) -> bool:
        """Indicates if entity follows naming conventions."""
        return True

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this entity."""
        return f"{self._device.id}-{self._prop}"

    @property
    def available(self) -> bool:
        """Check entity availability."""

        # Sensor is unavailable if device is offline or value is None
        return super().available and self.native_value is not None

    @property
    def device_class(self) -> str:
        """Return the device class of this entity."""
        return self._device_class

    @property
    def state_class(self) -> str:
        """Return the state class of this entity."""
        return self._state_class

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the native units of this entity."""
        return self._unit

    @property
    def native_value(self) -> float | None:
        """Return the current native value."""
        return getattr(self._device, self._prop, None)


class MideaEnergySensor(MideaSensor):
    """Energy sensor class for Midea AC."""

    def __init__(self,
                 *args,
                 format: AC.EnergyDataFormat,
                 scale: float = 1.0,
                 **kwargs) -> None:
        MideaSensor.__init__(self, *args, **kwargs)

        self._format = format
        self._scale = scale
        self._attr_entity_registry_enabled_default = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Call super method to ensure lifecycle is properly handled
        await super().async_added_to_hass()

        # Register energy sensor with coordinator
        self.coordinator.register_energy_sensor()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        # Call super method to ensure lifecycle is properly handled
        await super().async_will_remove_from_hass()

        # Unregister energy sensor with coordinator
        self.coordinator.unregister_energy_sensor()

    @property
    def native_value(self) -> float | None:
        """Return the scaled native value."""
        # Manually prepend 'get_' to the property.
        # This is so we don't have to change prop which causes unique ids to change
        get_method = getattr(self._device, f"get_{self._prop}", None)
        if get_method and callable(get_method):
            value = get_method(self._format)
        else:
            value = None

        if value is None:
            return None

        return value * self._scale
