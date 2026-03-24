"""Constants for the Deye Cloud integration."""

DOMAIN = "deyecloud"

# Config keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SERIAL_NUMBER = "serial_number"
CONF_APP_ID = "app_id"
CONF_APP_SECRET = "app_secret"
CONF_BASE_URL = "base_url"
CONF_START_MONTH = "start_month"

# Work mode options for /order/sys/workMode/update
WORK_MODES = [
    "SELLING_FIRST",
    "ZERO_EXPORT_TO_LOAD",
    "ZERO_EXPORT_TO_CT",
    "GREEN_POWER_MODE",
    "FULL_CHARGE_MODE",
    "CUSTOMIZED_MODE",
]

WORK_MODE_LABELS = {
    "SELLING_FIRST": "Selling First",
    "ZERO_EXPORT_TO_LOAD": "Zero Export to Load",
    "ZERO_EXPORT_TO_CT": "Zero Export to CT",
    "GREEN_POWER_MODE": "Green Power Mode",
    "FULL_CHARGE_MODE": "Full Charge Mode",
    "CUSTOMIZED_MODE": "Customized Mode",
}

# Energy pattern options for /order/sys/energyPattern/update
ENERGY_PATTERNS = ["BATTERY_FIRST", "LOAD_FIRST"]

ENERGY_PATTERN_LABELS = {
    "BATTERY_FIRST": "Battery First",
    "LOAD_FIRST": "Load First",
}

# Battery type options for /order/battery/type/update
BATTERY_TYPES = ["BATT_V", "BATT_SOC", "LI", "NO_BATTERY"]

BATTERY_TYPE_LABELS = {
    "BATT_V": "Lead-Acid (Voltage)",
    "BATT_SOC": "Lead-Acid (SOC)",
    "LI": "Lithium",
    "NO_BATTERY": "No Battery",
}

# Limit control function types for /order/sys/limitControl
LIMIT_CONTROL_TYPES = [
    "SELL_FIRST",
    "ZERO_EXPORT_TO_UPS_LOAD",
    "ZERO_EXPORT_TO_CT",
    "ZERO_EXPORT_TO_WIRELESS_CT",
]

LIMIT_CONTROL_LABELS = {
    "SELL_FIRST": "Sell First",
    "ZERO_EXPORT_TO_UPS_LOAD": "Zero Export to UPS Load",
    "ZERO_EXPORT_TO_CT": "Zero Export to CT",
    "ZERO_EXPORT_TO_WIRELESS_CT": "Zero Export to Wireless CT",
}

# Battery parameter types for /order/battery/parameter/update
BATT_PARAM_MAX_CHARGE_CURRENT = "MAX_CHARGE_CURRENT"
BATT_PARAM_MAX_DISCHARGE_CURRENT = "MAX_DISCHARGE_CURRENT"
BATT_PARAM_GRID_CHARGE_AMPERE = "GRID_CHARGE_AMPERE"
BATT_PARAM_BATT_LOW = "BATT_LOW"

# System power types for /order/sys/power/update
POWER_TYPE_MAX_SELL = "MAX_SELL_POWER"
POWER_TYPE_MAX_SOLAR = "MAX_SOLAR_POWER"
POWER_TYPE_ZERO_EXPORT = "ZERO_EXPORT_POWER"

# Battery mode types for /order/battery/modeControl
BATTERY_MODE_GEN_CHARGE = "GEN_CHARGE"
BATTERY_MODE_GRID_CHARGE = "GRID_CHARGE"
