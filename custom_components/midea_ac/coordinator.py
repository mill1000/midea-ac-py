"""Device update coordination for Midea Smart AC."""

import datetime
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (CoordinatorEntity,
                                                      DataUpdateCoordinator)
from homeassistant.helpers.debounce import Debouncer
from msmart.device import AirConditioner as AC

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MideaDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Device update coordinator for Midea Smart AC."""

    def __init__(self, hass: HomeAssistant, device: AC) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=datetime.timedelta(seconds=15),
            request_refresh_debouncer = Debouncer(
                hass,
                _LOGGER,
                cooldown=1,
                immediate=True,
            )
        )

        self._device = device

    async def _async_update_data(self) -> None:
        """Update the device data."""
        await self._device.refresh()

    async def apply(self) -> None:
        """Apply changes to the device and update HA state."""

        # Apply changes to device
        await self._device.apply()

        # Update state
        await self.async_request_refresh()
        # self.async_write_ha_state() # TODO?

    @property
    def device(self) -> AC:
        """Fetch the device object."""
        return self._device


class MideaCoordinatorEntity(CoordinatorEntity):
    """Coordinator entity for Midea Smart AC."""

    def __init__(self, coordinator: MideaDeviceUpdateCoordinator) -> None:
        super().__init__(coordinator)

        # Save reference to device
        self._device = coordinator.device

    @property
    def available(self) -> bool:
        """Check device availability."""
        return self._device.online
