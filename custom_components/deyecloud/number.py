"""Number platform for Deye Cloud."""

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BATT_PARAM_BATT_LOW,
    BATT_PARAM_GRID_CHARGE_AMPERE,
    BATT_PARAM_MAX_CHARGE_CURRENT,
    BATT_PARAM_MAX_DISCHARGE_CURRENT,
    DOMAIN,
    POWER_TYPE_MAX_SELL,
    POWER_TYPE_MAX_SOLAR,
    POWER_TYPE_ZERO_EXPORT,
)
from .coordinator import DeyeCloudCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: DeyeCloudCoordinator = data["coordinator"]
    device_sn = coordinator.device_sn
    if not device_sn:
        return

    battery_config = coordinator.data.get("battery_config") or {}
    system_config = coordinator.data.get("system_config") or {}

    entities: list[NumberEntity] = [
        # Battery parameters (from config/battery)
        DeyeBatteryParamNumber(
            coordinator, device_sn,
            param_type=BATT_PARAM_MAX_CHARGE_CURRENT,
            name="Max Charge Current",
            unique_id=f"{device_sn}_number_max_charge_current",
            icon="mdi:current-dc",
            unit="A",
            min_value=0, max_value=200, step=1,
            initial_value=battery_config.get("maxChargeCurrent"),
            config_key="maxChargeCurrent",
        ),
        DeyeBatteryParamNumber(
            coordinator, device_sn,
            param_type=BATT_PARAM_MAX_DISCHARGE_CURRENT,
            name="Max Discharge Current",
            unique_id=f"{device_sn}_number_max_discharge_current",
            icon="mdi:current-dc",
            unit="A",
            min_value=0, max_value=200, step=1,
            initial_value=battery_config.get("maxDischargeCurrent"),
            config_key="maxDischargeCurrent",
        ),
        DeyeBatteryParamNumber(
            coordinator, device_sn,
            param_type=BATT_PARAM_BATT_LOW,
            name="Battery Low Capacity",
            unique_id=f"{device_sn}_number_batt_low",
            icon="mdi:battery-low",
            unit="%",
            min_value=0, max_value=100, step=1,
            initial_value=battery_config.get("battLowCapacity"),
            config_key="battLowCapacity",
        ),
        DeyeBatteryParamNumber(
            coordinator, device_sn,
            param_type=BATT_PARAM_GRID_CHARGE_AMPERE,
            name="Grid Charge Current",
            unique_id=f"{device_sn}_number_grid_charge_ampere",
            icon="mdi:current-ac",
            unit="A",
            min_value=0, max_value=200, step=1,
            initial_value=None,  # Not in config/battery response
            config_key=None,
        ),
        # System power limits (from config/system)
        DeyeSystemPowerNumber(
            coordinator, device_sn,
            power_type=POWER_TYPE_MAX_SELL,
            name="Max Sell Power",
            unique_id=f"{device_sn}_number_max_sell_power",
            icon="mdi:transmission-tower-export",
            min_value=0, max_value=20000, step=100,
            initial_value=system_config.get("maxSellPower"),
            config_key="maxSellPower",
        ),
        DeyeSystemPowerNumber(
            coordinator, device_sn,
            power_type=POWER_TYPE_MAX_SOLAR,
            name="Max Solar Power",
            unique_id=f"{device_sn}_number_max_solar_power",
            icon="mdi:solar-panel-large",
            min_value=0, max_value=20000, step=100,
            initial_value=system_config.get("maxSolarPower"),
            config_key="maxSolarPower",
        ),
        DeyeSystemPowerNumber(
            coordinator, device_sn,
            power_type=POWER_TYPE_ZERO_EXPORT,
            name="Zero Export Power",
            unique_id=f"{device_sn}_number_zero_export_power",
            icon="mdi:transmission-tower-off",
            min_value=0, max_value=20000, step=100,
            initial_value=system_config.get("zeroExportPower"),
            config_key="zeroExportPower",
        ),
        # Grid peak shaving power (assumed state)
        DeyeGridPeakShavingPowerNumber(coordinator, device_sn),
        # Smart load parameters (assumed state)
        DeyeSmartLoadNumber(
            coordinator, device_sn,
            param_name="onVoltage",
            name="Smart Load On Voltage",
            unique_id=f"{device_sn}_number_smartload_on_voltage",
            icon="mdi:flash",
            unit="V",
            min_value=40, max_value=60, step=0.1,
        ),
        DeyeSmartLoadNumber(
            coordinator, device_sn,
            param_name="offVoltage",
            name="Smart Load Off Voltage",
            unique_id=f"{device_sn}_number_smartload_off_voltage",
            icon="mdi:flash-off",
            unit="V",
            min_value=40, max_value=60, step=0.1,
        ),
        DeyeSmartLoadNumber(
            coordinator, device_sn,
            param_name="onSOC",
            name="Smart Load On SOC",
            unique_id=f"{device_sn}_number_smartload_on_soc",
            icon="mdi:battery-arrow-up",
            unit="%",
            min_value=0, max_value=100, step=1,
        ),
        DeyeSmartLoadNumber(
            coordinator, device_sn,
            param_name="offSOC",
            name="Smart Load Off SOC",
            unique_id=f"{device_sn}_number_smartload_off_soc",
            icon="mdi:battery-arrow-down",
            unit="%",
            min_value=0, max_value=100, step=1,
        ),
    ]

    async_add_entities(entities)


class _DeyeInverterNumberBase(CoordinatorEntity, NumberEntity):
    """Base class for Deye inverter number entities."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: DeyeCloudCoordinator,
        device_sn: str,
        name: str,
        unique_id: str,
        icon: str,
        unit: str,
        min_value: float,
        max_value: float,
        step: float,
    ):
        super().__init__(coordinator)
        self._device_sn = device_sn
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_sn)},
            "name": f"Deye Inverter {self._device_sn}",
            "manufacturer": "Deye",
            "model": "Inverter",
        }


# ─── Battery Parameter ───────────────────────────────────────────────

class DeyeBatteryParamNumber(_DeyeInverterNumberBase):
    """Number entity for battery parameters (charge/discharge current, low capacity)."""

    def __init__(
        self,
        coordinator: DeyeCloudCoordinator,
        device_sn: str,
        param_type: str,
        name: str,
        unique_id: str,
        icon: str,
        unit: str,
        min_value: float,
        max_value: float,
        step: float,
        initial_value: float | None,
        config_key: str | None,
    ):
        super().__init__(
            coordinator, device_sn, name, unique_id, icon, unit,
            min_value, max_value, step,
        )
        self._param_type = param_type
        self._config_key = config_key
        self._fallback_value = initial_value

    @property
    def native_value(self) -> float | None:
        if self._config_key and self.coordinator.data:
            cfg = self.coordinator.data.get("battery_config")
            if cfg and self._config_key in cfg:
                return cfg[self._config_key]
        return self._fallback_value

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.api.update_battery_parameter(
                self._device_sn, self._param_type, int(value)
            )
            self._fallback_value = value
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            _LOGGER.error("Failed to set %s: %s", self._param_type, exc)


# ─── System Power ────────────────────────────────────────────────────

class DeyeSystemPowerNumber(_DeyeInverterNumberBase):
    """Number entity for system power limits (max sell, max solar, zero export)."""

    def __init__(
        self,
        coordinator: DeyeCloudCoordinator,
        device_sn: str,
        power_type: str,
        name: str,
        unique_id: str,
        icon: str,
        min_value: float,
        max_value: float,
        step: float,
        initial_value: float | None,
        config_key: str,
    ):
        super().__init__(
            coordinator, device_sn, name, unique_id, icon, "W",
            min_value, max_value, step,
        )
        self._power_type = power_type
        self._config_key = config_key
        self._fallback_value = initial_value

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            cfg = self.coordinator.data.get("system_config")
            if cfg and self._config_key in cfg:
                return cfg[self._config_key]
        return self._fallback_value

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.api.update_system_power(
                self._device_sn, self._power_type, int(value)
            )
            self._fallback_value = value
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            _LOGGER.error("Failed to set %s: %s", self._power_type, exc)


# ─── Grid Peak Shaving Power ────────────────────────────────────────

class DeyeGridPeakShavingPowerNumber(_DeyeInverterNumberBase):
    """Number entity for grid peak shaving power threshold."""

    _attr_assumed_state = True

    def __init__(self, coordinator: DeyeCloudCoordinator, device_sn: str):
        super().__init__(
            coordinator, device_sn,
            name="Grid Peak Shaving Power",
            unique_id=f"{device_sn}_number_grid_peak_shaving_power",
            icon="mdi:chart-bell-curve-cumulative",
            unit="W",
            min_value=0, max_value=20000, step=100,
        )
        self._value: float | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.api.control_grid_peak_shaving(
                self._device_sn, "on", int(value)
            )
            self._value = value
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to set grid peak shaving power: %s", exc)


# ─── Smart Load ──────────────────────────────────────────────────────

class DeyeSmartLoadNumber(_DeyeInverterNumberBase):
    """Number entity for smart load parameters."""

    _attr_assumed_state = True

    def __init__(
        self,
        coordinator: DeyeCloudCoordinator,
        device_sn: str,
        param_name: str,
        name: str,
        unique_id: str,
        icon: str,
        unit: str,
        min_value: float,
        max_value: float,
        step: float,
    ):
        super().__init__(
            coordinator, device_sn, name, unique_id, icon, unit,
            min_value, max_value, step,
        )
        self._param_name = param_name
        self._value: float | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.api.update_smart_load(
                self._device_sn, **{self._param_name: int(value)}
            )
            self._value = value
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to set smart load %s: %s", self._param_name, exc)
