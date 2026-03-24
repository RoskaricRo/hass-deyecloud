"""Switch platform for Deye Cloud."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BATTERY_MODE_GEN_CHARGE, BATTERY_MODE_GRID_CHARGE, DOMAIN
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

    tou_config = coordinator.data.get("tou_config")
    tou_is_on = (
        tou_config.get("touAction", "").lower() == "on"
        if tou_config
        else None
    )

    entities: list[SwitchEntity] = [
        DeyeSolarSellSwitch(coordinator, device_sn),
        DeyeBatteryModeSwitch(
            coordinator, device_sn, BATTERY_MODE_GEN_CHARGE,
            "Gen Charge", "mdi:solar-power",
        ),
        DeyeBatteryModeSwitch(
            coordinator, device_sn, BATTERY_MODE_GRID_CHARGE,
            "Grid Charge", "mdi:transmission-tower",
        ),
        DeyeTouSwitch(coordinator, device_sn, initial_state=tou_is_on),
        DeyeGridPeakShavingSwitch(coordinator, device_sn),
        DeyeSmartLoadGridAlwaysOnSwitch(coordinator, device_sn),
    ]

    async_add_entities(entities)


class _DeyeInverterSwitchBase(CoordinatorEntity, SwitchEntity):
    """Base class for Deye inverter switches."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DeyeCloudCoordinator,
        device_sn: str,
        name: str,
        unique_id: str,
        icon: str | None = None,
    ):
        super().__init__(coordinator)
        self._device_sn = device_sn
        self._attr_name = name
        self._attr_unique_id = unique_id
        if icon:
            self._attr_icon = icon

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_sn)},
            "name": f"Deye Inverter {self._device_sn}",
            "manufacturer": "Deye",
            "model": "Inverter",
        }


# ─── Solar Sell ──────────────────────────────────────────────────────

class DeyeSolarSellSwitch(_DeyeInverterSwitchBase):
    """Switch to enable/disable solar sell."""

    _attr_assumed_state = True

    def __init__(self, coordinator: DeyeCloudCoordinator, device_sn: str):
        super().__init__(
            coordinator, device_sn,
            name="Solar Sell",
            unique_id=f"{device_sn}_switch_solar_sell",
            icon="mdi:solar-power",
        )
        self._attr_is_on = None

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.api.control_solar_sell(self._device_sn, "on")
            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to enable solar sell: %s", exc)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.api.control_solar_sell(self._device_sn, "off")
            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to disable solar sell: %s", exc)


# ─── Battery Mode ────────────────────────────────────────────────────

class DeyeBatteryModeSwitch(_DeyeInverterSwitchBase):
    """Switch for battery charge mode (GEN_CHARGE / GRID_CHARGE)."""

    _attr_assumed_state = True

    def __init__(
        self,
        coordinator: DeyeCloudCoordinator,
        device_sn: str,
        battery_mode_type: str,
        name: str,
        icon: str,
    ):
        super().__init__(
            coordinator, device_sn,
            name=name,
            unique_id=f"{device_sn}_switch_{battery_mode_type.lower()}",
            icon=icon,
        )
        self._battery_mode_type = battery_mode_type
        self._attr_is_on = None

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.api.control_battery_mode(
                self._device_sn, "on", self._battery_mode_type
            )
            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to enable %s: %s", self._battery_mode_type, exc)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.api.control_battery_mode(
                self._device_sn, "off", self._battery_mode_type
            )
            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to disable %s: %s", self._battery_mode_type, exc)


# ─── TOU (Time of Use) ──────────────────────────────────────────────

class DeyeTouSwitch(_DeyeInverterSwitchBase):
    """Switch to enable/disable Time of Use schedule."""

    def __init__(
        self,
        coordinator: DeyeCloudCoordinator,
        device_sn: str,
        initial_state: bool | None = None,
    ):
        super().__init__(
            coordinator, device_sn,
            name="Time of Use",
            unique_id=f"{device_sn}_switch_tou",
            icon="mdi:clock-time-eight-outline",
        )
        self._attr_is_on = initial_state

    @property
    def is_on(self) -> bool | None:
        tou = self.coordinator.data.get("tou_config") if self.coordinator.data else None
        if tou and "touAction" in tou:
            return tou["touAction"].lower() == "on"
        return self._attr_is_on

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.api.switch_tou(self._device_sn, "on")
            self._attr_is_on = True
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            _LOGGER.error("Failed to enable TOU: %s", exc)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.api.switch_tou(self._device_sn, "off")
            self._attr_is_on = False
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            _LOGGER.error("Failed to disable TOU: %s", exc)

    @property
    def extra_state_attributes(self):
        tou = self.coordinator.data.get("tou_config") if self.coordinator.data else None
        if not tou:
            return {}
        items = tou.get("timeUseSettingItems", [])
        if not items:
            return {}
        return {"schedule_slots": len(items), "schedule": items}


# ─── Grid Peak Shaving ──────────────────────────────────────────────

class DeyeGridPeakShavingSwitch(_DeyeInverterSwitchBase):
    """Switch to enable/disable grid peak shaving."""

    _attr_assumed_state = True

    def __init__(self, coordinator: DeyeCloudCoordinator, device_sn: str):
        super().__init__(
            coordinator, device_sn,
            name="Grid Peak Shaving",
            unique_id=f"{device_sn}_switch_grid_peak_shaving",
            icon="mdi:chart-bell-curve-cumulative",
        )
        self._attr_is_on = None
        self._last_power = 0

    async def async_turn_on(self, **kwargs) -> None:
        try:
            power = self._last_power if self._last_power > 0 else 5000
            await self.coordinator.api.control_grid_peak_shaving(
                self._device_sn, "on", power
            )
            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to enable grid peak shaving: %s", exc)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.api.control_grid_peak_shaving(
                self._device_sn, "off", 0
            )
            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to disable grid peak shaving: %s", exc)

    def set_power(self, power: int) -> None:
        """Called by the number entity to keep power in sync."""
        self._last_power = power


# ─── Smart Load Grid Always On ───────────────────────────────────────

class DeyeSmartLoadGridAlwaysOnSwitch(_DeyeInverterSwitchBase):
    """Switch for smart load on-grid always on."""

    _attr_assumed_state = True

    def __init__(self, coordinator: DeyeCloudCoordinator, device_sn: str):
        super().__init__(
            coordinator, device_sn,
            name="Smart Load Grid Always On",
            unique_id=f"{device_sn}_switch_smartload_grid_always_on",
            icon="mdi:power-plug",
        )
        self._attr_is_on = None

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.api.update_smart_load(
                self._device_sn, onGridAlwaysOn=True
            )
            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to enable smart load grid always on: %s", exc)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.api.update_smart_load(
                self._device_sn, onGridAlwaysOn=False
            )
            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to disable smart load grid always on: %s", exc)
