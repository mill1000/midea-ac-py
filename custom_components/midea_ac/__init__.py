"""Integration for Midea Smart AC."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from msmart import __version__ as MSMART_VERISON
from msmart.device import AirConditioner as AC

from . import helpers
from .const import CONF_KEY, CONF_MAX_CONNECTION_LIFETIME, DOMAIN
from .coordinator import MideaDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Setup Midea Smart AC device from a config entry."""

    _LOGGER.info("Starting midea-ac-py. Using msmart-ng version %s.",
                 MSMART_VERISON)

    # Ensure the global data dict exists
    hass.data.setdefault(DOMAIN, {})

    # Construct the device
    id = config_entry.data[CONF_ID]
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    device = AC(ip=host, port=port, device_id=int(id))

    # Configure token and k1 as needed
    token = config_entry.data[CONF_TOKEN]
    key = config_entry.data[CONF_KEY]
    if token and key:
        success = await device.authenticate(token, key)
        if not success:
            raise ConfigEntryAuthFailed(
                "Failed to authenticate with device.")

    # Configure the connection lifetime
    lifetime = config_entry.options.get(CONF_MAX_CONNECTION_LIFETIME)
    if lifetime is not None and helpers.method_exists(device, "set_max_connection_lifetime"):
        _LOGGER.info(
            "Setting maximum connection lifetime to %s seconds.", lifetime)
        device.set_max_connection_lifetime(lifetime)

    # Query device capabilities
    if helpers.method_exists(device, "get_capabilities"):
        _LOGGER.info("Querying device capabilities.")
        await device.get_capabilities()

    # Create device coordinator and fetch data
    coordinator = MideaDeviceUpdateCoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in global data
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    # Create platform entries
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "climate"))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor"))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor"))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "switch"))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "number"))

    # Reload entry when its updated
    config_entry.async_on_unload(
        config_entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Remove the coordinator from global data
    try:
        hass.data[DOMAIN].pop(config_entry.data[CONF_ID])
    except KeyError:
        _LOGGER.warning("Failed remove device from global data.")

    await hass.config_entries.async_forward_entry_unload(config_entry, "climate")
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(config_entry, "binary_sensor")
    await hass.config_entries.async_forward_entry_unload(config_entry, "switch")
    await hass.config_entries.async_forward_entry_unload(config_entry, "number")

    return True


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload a config entry."""
    await hass.config_entries.async_reload(config_entry.entry_id)
