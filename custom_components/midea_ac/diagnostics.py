"""Diagnostics support for Midea Smart AC."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from msmart.device import AirConditioner as AC

from .const import CONF_KEY, DOMAIN

_REDACT = [
    CONF_KEY,
    CONF_TOKEN,
    "key"
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    # Fetch coordinator from global data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    device = coordinator.device

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), _REDACT),
        "device": {
            # Dump basic device info
            **async_redact_data(super(AC, device).to_dict(), _REDACT),

            # Dump supported features
            **{
                "supported_modes": device.supported_operation_modes,
                "supported_swing_modes": device.supported_swing_modes,
                "supported_fan_speeds": device.supported_fan_speeds,
                "supports_custom_fan_speed": device.supports_custom_fan_speed,
                "supported_rate_selects": device.supported_rate_selects,
                "supported_aux_modes": device.supported_aux_modes,

                "supports_eco": device.supports_eco,
                "supports_ieco": device.supports_ieco,
                "supports_turbo": device.supports_turbo,
                "supports_freeze_protection": device.supports_freeze_protection,

                "supports_display_control": device.supports_display_control,
                "supports_filter_reminder": device.supports_filter_reminder,
                "supports_self_clean": device.supports_self_clean,
                "supports_purifier": device.supports_purifier,

                "supports_humidity": device.supports_humidity,
                "supports_target_humidity": device.supports_target_humidity,

                "supports_vertical_swing_angle": device.supports_vertical_swing_angle,
                "supports_horizontal_swing_angle": device.supports_horizontal_swing_angle,

                "supports_breezeless": device.supports_breezeless,
                "supports_breeze_mild": device.supports_breeze_mild,
                "supports_breeze_away": device.supports_breeze_away,

                "enable_energy_usage_requests": device.enable_energy_usage_requests,
                "use_alternate_energy_format": device.use_alternate_energy_format,

                "_supported_properties": device._supported_properties,
            }
        }
    }
