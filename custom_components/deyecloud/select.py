"""Select platform for Deye Cloud."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BATTERY_TYPE_LABELS,
    BATTERY_TYPES,
    DOMAIN,
    ENERGY_PATTERN_LABELS,
    ENERGY_PATTERNS,
    LIMIT_CONTROL_LABELS,
    LIMIT_CONTROL_TYPES,
    WORK_MODE_LABELS,
    WORK_MODES,
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

    system_config = coordinator.data.get("system_config") or {}

    entities: list[SelectEntity] = [
        DeyeWorkModeSelect(
            coordinator, device_sn,
            initial_value=system_config.get("systemWorkMode"),
        ),
        DeyeEnergyPatternSelect(
            coordinator, device_sn,
            initial_value=system_config.get("energyPattern"),
        ),
        DeyeBatteryTypeSelect(coordinator, device_sn),
        DeyeLimitControlSelect(coordinator, device_sn),
    ]

    async_add_entities(entities)


class _DeyeInverterSelectBase(CoordinatorEntity, SelectEntity):
    """Base class for Deye inverter select entities."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: DeyeCloudCoordinator,
        device_sn: str,
        name: str,
        unique_id: str,
        icon: str,
        options: list[str],
    ):
        super().__init__(coordinator)
        self._device_sn = device_sn
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_icon = icon
        self._attr_options = options

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_sn)},
            "name": f"Deye Inverter {self._device_sn}",
            "manufacturer": "Deye",
            "model": "Inverter",
        }


# ─── Work Mode ───────────────────────────────────────────────────────

class DeyeWorkModeSelect(_DeyeInverterSelectBase):
    """Select entity for system work mode."""

    def __init__(
        self,
        coordinator: DeyeCloudCoordinator,
        device_sn: str,
        initial_value: str | None = None,
    ):
        super().__init__(
            coordinator, device_sn,
            name="Work Mode",
            unique_id=f"{device_sn}_select_work_mode",
            icon="mdi:cog",
            options=list(WORK_MODE_LABELS.values()),
        )
        self._api_options = WORK_MODES
        self._labels = WORK_MODE_LABELS
        self._reverse_labels = {v: k for k, v in WORK_MODE_LABELS.items()}
        self._fallback = initial_value

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data:
            cfg = self.coordinator.data.get("system_config")
            if cfg and "systemWorkMode" in cfg:
                api_val = cfg["systemWorkMode"]
                return self._labels.get(api_val, api_val)
        if self._fallback:
            return self._labels.get(self._fallback, self._fallback)
        return None

    async def async_select_option(self, option: str) -> None:
        api_value = self._reverse_labels.get(option, option)
        try:
            await self.coordinator.api.update_work_mode(self._device_sn, api_value)
            self._fallback = api_value
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            _LOGGER.error("Failed to set work mode: %s", exc)


# ─── Energy Pattern ──────────────────────────────────────────────────

class DeyeEnergyPatternSelect(_DeyeInverterSelectBase):
    """Select entity for energy pattern (Battery First / Load First)."""

    def __init__(
        self,
        coordinator: DeyeCloudCoordinator,
        device_sn: str,
        initial_value: str | None = None,
    ):
        super().__init__(
            coordinator, device_sn,
            name="Energy Pattern",
            unique_id=f"{device_sn}_select_energy_pattern",
            icon="mdi:battery-sync",
            options=list(ENERGY_PATTERN_LABELS.values()),
        )
        self._labels = ENERGY_PATTERN_LABELS
        self._reverse_labels = {v: k for k, v in ENERGY_PATTERN_LABELS.items()}
        self._fallback = initial_value

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data:
            cfg = self.coordinator.data.get("system_config")
            if cfg and "energyPattern" in cfg:
                api_val = cfg["energyPattern"]
                return self._labels.get(api_val, api_val)
        if self._fallback:
            return self._labels.get(self._fallback, self._fallback)
        return None

    async def async_select_option(self, option: str) -> None:
        api_value = self._reverse_labels.get(option, option)
        try:
            await self.coordinator.api.update_energy_pattern(
                self._device_sn, api_value
            )
            self._fallback = api_value
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except Exception as exc:
            _LOGGER.error("Failed to set energy pattern: %s", exc)


# ─── Battery Type ────────────────────────────────────────────────────

class DeyeBatteryTypeSelect(_DeyeInverterSelectBase):
    """Select entity for battery type."""

    _attr_assumed_state = True

    def __init__(self, coordinator: DeyeCloudCoordinator, device_sn: str):
        super().__init__(
            coordinator, device_sn,
            name="Battery Type",
            unique_id=f"{device_sn}_select_battery_type",
            icon="mdi:battery-outline",
            options=list(BATTERY_TYPE_LABELS.values()),
        )
        self._labels = BATTERY_TYPE_LABELS
        self._reverse_labels = {v: k for k, v in BATTERY_TYPE_LABELS.items()}
        self._current: str | None = None

    @property
    def current_option(self) -> str | None:
        return self._current

    async def async_select_option(self, option: str) -> None:
        api_value = self._reverse_labels.get(option, option)
        try:
            await self.coordinator.api.update_battery_type(
                self._device_sn, api_value
            )
            self._current = option
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to set battery type: %s", exc)


# ─── Limit Control Function ─────────────────────────────────────────

class DeyeLimitControlSelect(_DeyeInverterSelectBase):
    """Select entity for limit control function (Micro ESS only)."""

    _attr_assumed_state = True

    def __init__(self, coordinator: DeyeCloudCoordinator, device_sn: str):
        super().__init__(
            coordinator, device_sn,
            name="Limit Control Function",
            unique_id=f"{device_sn}_select_limit_control",
            icon="mdi:speedometer",
            options=list(LIMIT_CONTROL_LABELS.values()),
        )
        self._labels = LIMIT_CONTROL_LABELS
        self._reverse_labels = {v: k for k, v in LIMIT_CONTROL_LABELS.items()}
        self._current: str | None = None

    @property
    def current_option(self) -> str | None:
        return self._current

    async def async_select_option(self, option: str) -> None:
        api_value = self._reverse_labels.get(option, option)
        try:
            await self.coordinator.api.update_limit_control(
                self._device_sn, api_value
            )
            self._current = option
            self.async_write_ha_state()
        except Exception as exc:
            _LOGGER.error("Failed to set limit control: %s", exc)
