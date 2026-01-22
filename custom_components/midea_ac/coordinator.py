"""Device update coordination for Midea Smart AC."""

import datetime
import logging
from asyncio import Lock
from typing import Any, Generic

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (CoordinatorEntity,
                                                      DataUpdateCoordinator)

from .const import DOMAIN, UPDATE_INTERVAL, MideaDevice

_LOGGER = logging.getLogger(__name__)


class MideaDeviceProxy(Generic[MideaDevice]):
    """A device proxy that stages state changes and prevents direct access to the device."""

    def __init__(self, device: MideaDevice) -> None:
        # Create attributes via super() to avoid calling the overridden __setattr__
        super().__setattr__("_device", device)
        super().__setattr__("_staged", {})

    def __getattr__(self, name: str) -> Any:
        """Get a property from the device."""
        # Return staged value if present
        if name in self._staged:
            return self._staged[name]

        # Otherwise return current device value
        return getattr(self._device, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Stage a property change."""
        # Throw if trying to create an attribute
        if not hasattr(self._device, name):
            raise AttributeError(f"Cannot set attribute '{name}'")

        # Check if it's a property and has a setter
        device_attr = getattr(type(self._device), name, None)
        if isinstance(device_attr, property):
            if device_attr.fset is None:
                raise AttributeError(f"Cannot set read-only property '{name}'")

        # Save value as pending change
        self._staged[name] = value

    async def refresh(self) -> None:
        """Update the device data."""
        await self._device.refresh()

    async def apply(self) -> None:
        """Apply changes to the device."""
        # Apply staged changes to local device state
        for name, value in self._staged.items():
            setattr(self._device, name, value)

        # Apply state to device
        await self._device.apply()

        # Clear staged changes
        self._staged.clear()


class MideaDeviceUpdateCoordinator(DataUpdateCoordinator, Generic[MideaDevice]):
    """Device update coordinator for Midea Smart AC."""

    def __init__(self, hass: HomeAssistant, device: MideaDevice) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=datetime.timedelta(seconds=UPDATE_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=1,
                immediate=True,
            )
        )

        self._lock = Lock()
        self._proxy: MideaDeviceProxy[MideaDevice] = MideaDeviceProxy(device)
        self._energy_sensors = 0

    async def _async_update_data(self) -> None:
        """Update the device data."""
        async with self._lock:
            await self._proxy.refresh()

    @property
    def device(self) -> MideaDeviceProxy[MideaDevice]:
        """Return the device proxy typed as the device."""
        return self._proxy

    async def apply(self) -> None:
        """Apply changes to the device and update HA state."""
        async with self._lock:
            await self._proxy.apply()

        # Update state
        await self.async_request_refresh()

    def register_energy_sensor(self) -> None:
        """Record that an energy sensor is active."""

        if not hasattr(self.device, "enable_energy_usage_requests"):
            raise TypeError("Device does not support energy sensors.")

        self._energy_sensors += 1

        # Enable requests
        self.device.enable_energy_usage_requests = True

    def unregister_energy_sensor(self) -> None:
        """Record that an energy sensor is inactive."""

        if not hasattr(self.device, "enable_energy_usage_requests"):
            raise TypeError("Device does not support energy sensors.")

        self._energy_sensors -= 1

        # Disable requests if last sensor
        self.device.enable_energy_usage_requests = self._energy_sensors > 0


class MideaCoordinatorEntity(CoordinatorEntity[MideaDeviceUpdateCoordinator], Generic[MideaDevice]):
    """Coordinator entity for Midea Smart AC."""

    def __init__(self, coordinator: MideaDeviceUpdateCoordinator[MideaDevice]) -> None:
        super().__init__(coordinator)

        # Save reference to device
        self._device: MideaDeviceProxy[MideaDevice] = coordinator.device

    @property
    def available(self) -> bool:
        """Check device availability."""
        return self._device.online
