"""Integration for Midea Smart AC."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_HOST, CONF_ID, CONF_PORT, CONF_TOKEN,
                                 Platform)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from msmart import __version__ as MSMART_VERSION
from msmart.base_device import Device
from msmart.const import DeviceType
from msmart.device import AirConditioner as AC
from msmart.device import CommercialAirConditioner as CC
from msmart.lan import AuthenticationError

from .const import (CONF_ADDITIONAL_OPERATION_MODES, CONF_DEVICE_TYPE,
                    CONF_ENERGY_DATA_FORMAT, CONF_ENERGY_DATA_SCALE,
                    CONF_ENERGY_SENSOR, CONF_KEY, CONF_MAX_CONNECTION_LIFETIME,
                    CONF_POWER_SENSOR, CONF_SHOW_ALL_PRESETS,
                    CONF_USE_FAN_ONLY_WORKAROUND, CONF_WORKAROUNDS, DOMAIN,
                    EnergyFormat)
from .coordinator import MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Setup Midea Smart AC device from a config entry."""

    # Ensure the global data dict exists
    hass.data.setdefault(DOMAIN, {})

    device_type = config_entry.data[CONF_DEVICE_TYPE]
    id = config_entry.data[CONF_ID]
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]

    _LOGGER.info("Starting midea-ac-py for device type %02X ID %s (%s:%d). Using msmart-ng version %s.",
                 device_type, id, host, port, MSMART_VERSION)

    # Construct the device
    device = Device.construct(
        type=device_type,
        ip=host,
        port=port,
        device_id=int(id)
    )
    assert isinstance(device, (AC, CC))

    # Configure the connection lifetime
    if (lifetime := config_entry.options.get(CONF_MAX_CONNECTION_LIFETIME)) is not None:
        _LOGGER.info(
            "Setting maximum connection lifetime to %s seconds for device ID %s.", lifetime, device.id)
        device.set_max_connection_lifetime(lifetime)

    # Configure token and k1 as needed
    token = config_entry.data[CONF_TOKEN]
    key = config_entry.data[CONF_KEY]
    if token and key:
        try:
            await device.authenticate(token, key)
        except AuthenticationError as e:
            raise ConfigEntryNotReady(
                "Failed to authenticate with device.") from e

    # Query device capabilities
    _LOGGER.info("Querying capabilities for device ID %s.", device.id)
    await device.get_capabilities()

    # Create device coordinator and fetch data
    coordinator = MideaDeviceUpdateCoordinator(hass, device)  # type: ignore
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in global data
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    # Forward setup to all platforms
    await hass.config_entries.async_forward_entry_setups(config_entry, _PLATFORMS)

    # Reload entry when its updated
    config_entry.async_on_unload(
        config_entry.add_update_listener(async_reload_entry))

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entry."""

    _LOGGER.debug("Migrating configuration from version %s.%s.",
                  config_entry.version, config_entry.minor_version)

    if config_entry.version > 1:
        # Unsupported downgrade
        return False

    if config_entry.version == 1:
        # 1.1 -> 1.2: Convert unique ID to string
        if config_entry.minor_version == 1:
            hass.config_entries.async_update_entry(
                config_entry, unique_id=str(config_entry.unique_id), minor_version=2)

        # 1.2 -> 1.3: Convert alternate energy boolean option to enum
        if config_entry.minor_version == 2:
            new_options = {**config_entry.options}
            if new_options.pop("use_alternate_energy_format", False):
                new_options["energy_format"] = EnergyFormat._ALTERNATE_B
            else:
                new_options["energy_format"] = EnergyFormat._DEFAULT

            hass.config_entries.async_update_entry(
                config_entry, options=new_options, minor_version=3)

        # 1.3 -> 1.4:
        # Convert alternate energy enum to custom fields
        # Group workarounds into section
        if config_entry.minor_version == 3:
            new_options = {**config_entry.options}
            old_energy_format = new_options.pop(
                "energy_format", EnergyFormat._DEFAULT)

            # Old default format was BCD, alternates A/B were binary
            data_format = (EnergyFormat.BCD if old_energy_format ==
                           EnergyFormat._DEFAULT else EnergyFormat.BINARY)

            # Setup energy and power sensor configs
            new_options[CONF_ENERGY_SENSOR] = {
                CONF_ENERGY_DATA_FORMAT: data_format,
                # Scale energy by 1/10 to match Alternate B
                CONF_ENERGY_DATA_SCALE:  0.1 if old_energy_format == EnergyFormat._ALTERNATE_B else 1.0
            }
            new_options[CONF_POWER_SENSOR] = {
                CONF_ENERGY_DATA_FORMAT: data_format,
                CONF_ENERGY_DATA_SCALE: 1
            }

            # Migrate workarounds into a section
            new_options[CONF_WORKAROUNDS] = {
                CONF_USE_FAN_ONLY_WORKAROUND: new_options.pop(CONF_USE_FAN_ONLY_WORKAROUND, False),
                CONF_SHOW_ALL_PRESETS: new_options.pop(CONF_SHOW_ALL_PRESETS, False),
                CONF_ADDITIONAL_OPERATION_MODES: new_options.pop(
                    CONF_ADDITIONAL_OPERATION_MODES, None) or ""
            }

            hass.config_entries.async_update_entry(
                config_entry, options=new_options, minor_version=4)

        # 1.4 -> 1.5: Assign a device type
        if config_entry.minor_version == 4:
            hass.config_entries.async_update_entry(
                config_entry,
                data={
                    CONF_DEVICE_TYPE: DeviceType.AIR_CONDITIONER,
                    **config_entry.data,
                },
                minor_version=5,
            )

    _LOGGER.debug("Migration to configuration version %s.%s successful.",
                  config_entry.version, config_entry.minor_version)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Remove the coordinator from global data
    try:
        hass.data[DOMAIN].pop(config_entry.entry_id)
    except KeyError:
        _LOGGER.warning("Failed remove device from global data.")

    # Forward unload to all platforms
    for platform in _PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(config_entry, platform)

    return True


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload a config entry."""
    await hass.config_entries.async_reload(config_entry.entry_id)
