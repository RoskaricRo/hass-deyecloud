"""Sensor platform for Deye Cloud."""

import logging
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfIrradiance,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import DeyeCloudCoordinator

_LOGGER = logging.getLogger(__name__)

_RELATIVE_DAY_OFFSETS = {
    "today": 0,
    "yesterday": 1,
    "day_before": 2,
}

# Station-level real-time sensors from /station/latest
_STATION_LATEST_SENSORS = [
    ("generationPower", "Generation Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("consumptionPower", "Consumption Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("gridPower", "Grid Export Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("purchasePower", "Grid Import Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("chargePower", "Battery Charge Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("dischargePower", "Battery Discharge Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("batteryPower", "Battery Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("batterySOC", "Battery SOC", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),
    ("wirePower", "Wire Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    ("irradiateIntensity", "Irradiance", UnitOfIrradiance.WATTS_PER_SQUARE_METER, SensorDeviceClass.IRRADIANCE, SensorStateClass.MEASUREMENT),
]

_MONTHLY_METRICS = [
    ("generationValue", "Solar Generation"),
    ("consumptionValue", "Monthly Consumption"),
    ("gridValue", "Monthly Grid Export"),
    ("purchaseValue", "Monthly Grid Import"),
    ("chargeValue", "Monthly Battery Charge"),
    ("dischargeValue", "Monthly Battery Discharge"),
]

_DAILY_METRICS = [
    ("generationValue", "Solar Generation"),
    ("consumptionValue", "Daily Consumption"),
    ("gridValue", "Daily Grid Export"),
    ("purchaseValue", "Daily Grid Import"),
    ("chargeValue", "Daily Battery Charge"),
    ("dischargeValue", "Daily Battery Discharge"),
]

# Map device data units to HA classes
_UNIT_MAP = {
    "kWh": (UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    "W": (UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "V": (UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    "A": (UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    "%": (PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),
    "°C": (UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "C": (UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "Hz": (UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT),
}


def _resolve_daily_date_key(date_key: str) -> str:
    """Convert relative day key to YYYY-MM-DD using HA timezone."""
    if date_key in _RELATIVE_DAY_OFFSETS:
        d = dt_util.now().date() - timedelta(days=_RELATIVE_DAY_OFFSETS[date_key])
        return d.isoformat()
    return date_key


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: DeyeCloudCoordinator = data["coordinator"]

    entities: list[SensorEntity] = []
    station_id = coordinator.data.get("station_id")
    device_sn = coordinator.data.get("device_sn")

    now = dt_util.now()
    this_year, this_month = now.year, now.month
    last_month_dt = now - relativedelta(months=1)
    prev_year, prev_month = last_month_dt.year, last_month_dt.month

    # ── Station latest (real-time power) ──────────────────────────
    for key, name, unit, dev_cls, state_cls in _STATION_LATEST_SENSORS:
        entities.append(
            DeyeCloudSensor(
                coordinator=coordinator,
                sensor_type="station_latest",
                name=name,
                unique_id=f"station_{station_id}_{key}",
                unit=unit,
                device_class=dev_cls,
                state_class=state_cls,
                station_id=station_id,
                metric_key=key,
            )
        )

    # ── Monthly raw history ───────────────────────────────────────
    for record in coordinator.data.get("history", []):
        y = record.get("year")
        m = record.get("month")
        if not y or not m:
            continue
        month_name = datetime(year=y, month=m, day=1).strftime("%b %Y")
        entities.append(
            DeyeCloudSensor(
                coordinator=coordinator,
                sensor_type="monthly_raw",
                name=f"Deye {station_id} {month_name}",
                unique_id=f"{station_id}_raw_{y}_{m:02d}",
                unit=UnitOfEnergy.KILO_WATT_HOUR,
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
                station_id=station_id,
                date_key=f"{y}_{m}",
                extra_attributes=record,
            )
        )

    # ── Monthly metrics (current + last month) ────────────────────
    for metric_key, metric_name in _MONTHLY_METRICS:
        entities.append(
            DeyeCloudSensor(
                coordinator=coordinator,
                sensor_type="monthly_metric",
                name=f"{metric_name} {station_id}",
                unique_id=f"{station_id}_{metric_key}_current_month",
                unit=UnitOfEnergy.KILO_WATT_HOUR,
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
                station_id=station_id,
                date_key="current",
                metric_key=metric_key,
                extra_attributes={"year": this_year, "month": this_month, "metric": metric_name},
            )
        )
        entities.append(
            DeyeCloudSensor(
                coordinator=coordinator,
                sensor_type="monthly_metric",
                name=f"{metric_name} (Last Month) {station_id}",
                unique_id=f"{station_id}_{metric_key}_last_month",
                unit=UnitOfEnergy.KILO_WATT_HOUR,
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
                station_id=station_id,
                date_key="last",
                metric_key=metric_key,
                extra_attributes={"year": prev_year, "month": prev_month, "metric": metric_name},
            )
        )

    # ── Daily metrics ─────────────────────────────────────────────
    for rel_key, rel_suffix in [
        ("day_before", "_day_before"),
        ("yesterday", "_yesterday"),
        ("today", "_today"),
    ]:
        for metric_key, metric_name in _DAILY_METRICS:
            entities.append(
                DeyeCloudSensor(
                    coordinator=coordinator,
                    sensor_type="daily",
                    name=f"{metric_name} {rel_suffix.replace('_', ' ')} {station_id}",
                    unique_id=f"{station_id}_{metric_key}{rel_suffix}",
                    unit=UnitOfEnergy.KILO_WATT_HOUR,
                    device_class=SensorDeviceClass.ENERGY,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    station_id=station_id,
                    date_key=rel_key,
                    metric_key=metric_key,
                    extra_attributes={"relative_day": rel_key},
                )
            )

    # ── Device status sensors ─────────────────────────────────────
    device_latest = coordinator.data.get("device_latest", {})
    for data_item in device_latest.get("dataList", []):
        key = data_item.get("key")
        if not key:
            continue
        raw_unit = data_item.get("unit", "")
        mapped = _UNIT_MAP.get(raw_unit, (raw_unit or None, None, None))
        unit, dev_cls, state_cls = mapped

        entities.append(
            DeyeCloudSensor(
                coordinator=coordinator,
                sensor_type="device",
                name=f"{key} {device_sn}",
                unique_id=f"device_{device_sn}_{key}",
                unit=unit,
                device_class=dev_cls,
                state_class=state_cls,
                station_id=station_id,
                device_sn=device_sn,
                device_key=key,
                extra_attributes={
                    "device_type": device_latest.get("deviceType"),
                    "device_state": device_latest.get("deviceState"),
                    "collection_time": device_latest.get("collectionTime"),
                },
            )
        )

    async_add_entities(entities)
    _LOGGER.info("DeyeCloud sensor setup completed with %d entities", len(entities))


class DeyeCloudSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Deye Cloud Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DeyeCloudCoordinator,
        sensor_type: str,
        name: str,
        unique_id: str,
        unit=None,
        device_class=None,
        state_class=None,
        extra_attributes: dict | None = None,
        station_id=None,
        date_key: str | None = None,
        metric_key: str | None = None,
        device_sn: str | None = None,
        device_key: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_native_unit_of_measurement = unit
        if device_class:
            self._attr_device_class = device_class
        if state_class:
            self._attr_state_class = state_class
        self._extra_attributes = extra_attributes or {}
        self._station_id = station_id
        self._date_key = date_key
        self._metric_key = metric_key
        self._device_sn = device_sn
        self._device_key = device_key

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None

        try:
            if self._sensor_type == "station_latest":
                return self.coordinator.data.get("station_latest", {}).get(
                    self._metric_key
                )

            if self._sensor_type == "monthly_raw":
                year, month = map(int, self._date_key.split("_"))
                for record in self.coordinator.data.get("history", []):
                    if record.get("year") == year and record.get("month") == month:
                        return record.get("generationValue")

            elif self._sensor_type == "monthly_metric":
                if self._date_key == "current":
                    now = dt_util.now()
                    year, month = now.year, now.month
                else:
                    last_month = dt_util.now() - relativedelta(months=1)
                    year, month = last_month.year, last_month.month
                for record in self.coordinator.data.get("history", []):
                    if record.get("year") == year and record.get("month") == month:
                        return record.get(self._metric_key)

            elif self._sensor_type == "daily":
                date_str = _resolve_daily_date_key(self._date_key)
                daily_data = self.coordinator.data.get("daily", {}).get(date_str, {})
                return daily_data.get(self._metric_key)

            elif self._sensor_type == "device":
                device_data = self.coordinator.data.get("device_latest", {})
                for data_item in device_data.get("dataList", []):
                    if data_item.get("key") == self._device_key:
                        return data_item.get("value")

        except (KeyError, ValueError, TypeError) as exc:
            _LOGGER.error("Error extracting value for %s: %s", self.unique_id, exc)

        return None

    @property
    def device_info(self):
        if self._device_sn:
            return {
                "identifiers": {(DOMAIN, self._device_sn)},
                "name": f"Deye Inverter {self._device_sn}",
                "manufacturer": "Deye",
                "model": "Inverter",
            }
        if self._station_id is not None:
            return {
                "identifiers": {(DOMAIN, f"station_{self._station_id}")},
                "name": f"Deye Station {self._station_id}",
                "manufacturer": "Deye",
                "model": "Station",
            }
        return None

    @property
    def extra_state_attributes(self):
        attrs = self._extra_attributes.copy()
        if self._station_id is not None:
            attrs["station_id"] = self._station_id
        if self._date_key:
            if self._sensor_type == "monthly_raw":
                attrs["year"] = int(self._date_key.split("_")[0])
                attrs["month"] = int(self._date_key.split("_")[1])
            elif self._sensor_type == "daily":
                attrs["relative_day"] = self._date_key
                attrs["date"] = _resolve_daily_date_key(self._date_key)
        if self._device_sn:
            attrs["device_sn"] = self._device_sn
        return attrs
