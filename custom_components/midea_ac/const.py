from enum import StrEnum, auto

DOMAIN = "midea_ac"

CONF_KEY = "k1"
CONF_BEEP = "prompt_tone"
CONF_TEMP_STEP = "temp_step"
CONF_FAN_SPEED_STEP = "fan_speed_step"
CONF_USE_FAN_ONLY_WORKAROUND = "use_fan_only_workaround"
CONF_ADDITIONAL_OPERATION_MODES = "additional_operation_modes"
CONF_SHOW_ALL_PRESETS = "show_all_presets"
CONF_MAX_CONNECTION_LIFETIME = "max_connection_lifetime"
CONF_ENERGY_FORMAT = "energy_format"
CONF_CLOUD_COUNTRY_CODES = ["DE", "KR", "US"]
CONF_DEFAULT_CLOUD_COUNTRY = "US"

PRESET_IECO = "ieco"


class EnergyFormat(StrEnum):
    DEFAULT = auto()
    ALTERNATE_A = auto()
    ALTERNATE_B = auto()
