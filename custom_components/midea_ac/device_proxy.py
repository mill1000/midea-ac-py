"""Device proxy for Midea Smart AC."""

import logging
from typing import Any, Generic

from .const import MideaDevice

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
        if isinstance(device_attr, property) and device_attr.fset is None:
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

    def set_direct(self, name: str, value: Any) -> None:
        """Directly set a device attribute bypassing the staging."""
        # Throw if trying to create an attribute
        if not hasattr(self._device, name):
            raise AttributeError(f"Cannot set attribute '{name}'")

        # Check if it's a property and has a setter
        device_attr = getattr(type(self._device), name, None)
        if isinstance(device_attr, property) and device_attr.fset is None:
            raise AttributeError(f"Cannot set read-only property '{name}'")

        setattr(self._device, name, value)
