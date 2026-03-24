"""Binary sensor platform for Deye Cloud."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DeyeCloudCoordinator

_LOGGER = logging.getLogger(__name__)

# deviceState values: 1=Online, 2=Alert, 3=Offline
_ONLINE_STATES = {1, 2}


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

    async_add_entities([
        DeyeDeviceConnectivitySensor(coordinator, device_sn),
    ])


class DeyeDeviceConnectivitySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating whether the inverter is online."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: DeyeCloudCoordinator, device_sn: str
    ):
        super().__init__(coordinator)
        self._device_sn = device_sn
        self._attr_name = "Connection"
        self._attr_unique_id = f"{device_sn}_connectivity"

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        device = self.coordinator.data.get("device_latest", {})
        state = device.get("deviceState")
        if state is None:
            return None
        return state in _ONLINE_STATES

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        device = self.coordinator.data.get("device_latest", {})
        state = device.get("deviceState")
        state_map = {1: "Online", 2: "Alert", 3: "Offline"}
        return {
            "device_state": state_map.get(state, f"Unknown ({state})"),
            "collection_time": device.get("collectionTime"),
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_sn)},
            "name": f"Deye Inverter {self._device_sn}",
            "manufacturer": "Deye",
            "model": "Inverter",
        }
