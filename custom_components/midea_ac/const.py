from enum import StrEnum, auto
from typing import TypeVar

from msmart.device import AirConditioner as AC
from msmart.device import CommercialCooler as CC

DOMAIN = "midea_ac"
UPDATE_INTERVAL = 15

CONF_KEY = "k1"
CONF_BEEP = "prompt_tone"
CONF_TEMP_STEP = "temp_step"
CONF_FAN_SPEED_STEP = "fan_speed_step"
CONF_WORKAROUNDS = "workarounds"
CONF_USE_FAN_ONLY_WORKAROUND = "use_fan_only_workaround"
CONF_ADDITIONAL_OPERATION_MODES = "additional_operation_modes"
CONF_SHOW_ALL_PRESETS = "show_all_presets"
CONF_MAX_CONNECTION_LIFETIME = "max_connection_lifetime"
CONF_ENERGY_SENSOR = "energy_sensor"
CONF_POWER_SENSOR = "power_sensor"
CONF_ENERGY_DATA_FORMAT = "energy_data_format"
CONF_ENERGY_DATA_SCALE = "energy_data_scale"
CONF_CLOUD_COUNTRY_CODES = ["DE", "KR", "US"]
CONF_DEFAULT_CLOUD_COUNTRY = "US"
CONF_SWING_ANGLE_RTL = "swing_angle_rtl"

PRESET_IECO = "ieco"
PRESET_SILENT = "silent"


class EnergyFormat(StrEnum):
    BCD = auto()
    BINARY = auto()

    # Deprecated formats
    _DEFAULT = "default"
    _ALTERNATE_A = "alternate_a"
    _ALTERNATE_B = "alternate_b"


MideaDevice = TypeVar("MideaDevice", AC, CC)
