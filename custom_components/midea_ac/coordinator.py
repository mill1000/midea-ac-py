"""Device update coordination for Midea Smart AC."""

import datetime
import logging
from asyncio import Lock
from typing import Any, Generic, NoReturn

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (CoordinatorEntity,
                                                      DataUpdateCoordinator)

from .const import DOMAIN, UPDATE_INTERVAL, MideaDevice

_LOGGER = logging.getLogger(__name__)


class MideaDeviceUpdateCoordinator(DataUpdateCoordinator,  Generic[MideaDevice]):
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
        # self._device: MideaDevice = device
        self._proxy: MideaDeviceProxy = MideaDeviceProxy(device)
        self._energy_sensors = 0

    async def _async_update_data(self) -> None:
        """Update the device data."""
        async with self._lock:
            await self._proxy.refresh()

    @property
    def device(self) -> MideaDeviceProxy:
        """Fetch the device proxy."""
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
        self._device: MideaDeviceProxy = coordinator.device

    @property
    def available(self) -> bool:
        """Check device availability."""
        return self._device.online


class MideaDeviceProxy:
    """A proxy that stages state changes and prevents direct access to the device."""

    def __init__(self, device) -> None:
        # Create _device and _stage attributes using super's setattr to avoid a call to our own setattr
        super().__setattr__("_device", device)
        super().__setattr__("_staged", {})

        # Dynamically create properties for all device's properties
        def _make_property(name: str) -> property:
            def fget(self):
                return self.get(name)

            def fset(self, value):
                self.set(name, value)

            return property(fget, fset)

        for attr_name, attr_value in device.__class__.__dict__.items():
            # Only proxy device properties when they won't overwrite existing proxy properties
            if not isinstance(attr_value, property) or hasattr(self.__class__, attr_name):
                continue

            # Create a property in the proxy
            setattr(self.__class__, attr_name, _make_property(attr_name))

    def __setattr__(self, name: str, _) -> NoReturn:
        """Prevent setting any attributes on the proxy."""
        raise AttributeError(
            f"Cannot modify '{name}' directly. Use proxy.set()")

    def get(self, attr: str, default: Any = None) -> Any:
        """Get a property from the device."""
        # Return staged value if present
        if attr in self._staged:
            return self._staged[attr]

        # Otherwise return current device value
        return getattr(self._device, attr, default)

    def set(self, attr: str, value: Any) -> None:
        """Stage a property change."""
        # Save value as pending change
        self._staged[attr] = value

    async def refresh(self) -> None:
        """Update the device data."""
        await self._device.refresh()

    async def apply(self) -> None:
        """Apply changes to the device and update HA state."""
        # Apply changes to local device state
        for prop, value in self._staged.items():
            setattr(self._device, prop, value)

        # Apply state to device
        await self._device.apply()
        self._staged.clear()
