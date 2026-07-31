"""DataUpdateCoordinator for Deye Cloud."""

import logging
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import DeyeCloudAPI, DeyeCloudAPIError, DeyeCloudAuthError
from .const import CONF_SERIAL_NUMBER, CONF_START_MONTH
from .data import (
    _DAILY_ZERO_RECORD_KEYS,
    empty_daily_record as _empty_daily_record,
    should_reject_stale_today as _should_reject_stale_today,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)
CONFIG_REFRESH_INTERVAL = timedelta(minutes=5)

# ---------------------------------------------------------------------------
# Date-parsing and daily-record-selection helpers below are ported from
# heavenknows1978/hass-deyecloud. DeyeCloud can lag right after local
# midnight and briefly keep returning yesterday's daily bucket. Naively
# taking the first "today" record in that window can feed yesterday's final
# totals into Home Assistant's Energy Dashboard as today's data and create a
# negative delta once the real bucket appears. The stale-bucket detection
# itself (records_look_like_same_daily_bucket / should_reject_stale_today)
# lives in data.py as dependency-free, unit-testable pure functions.
# ---------------------------------------------------------------------------

_MIDNIGHT_STALE_GUARD = timedelta(hours=2)


def _parse_api_date(value) -> date | None:
    """Parse a DeyeCloud date-like value into a date if possible."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    # Some API regions return epoch timestamps (seconds or milliseconds).
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            ts = float(value)
            if ts > 1e12:  # milliseconds
                ts /= 1000.0
            if ts > 1e8:  # plausible epoch seconds (>1973)
                return datetime.fromtimestamp(
                    ts, tz=dt_util.DEFAULT_TIME_ZONE
                ).date()
        except (ValueError, OverflowError, OSError):
            return None
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.isdigit() and len(text) >= 10:
        return _parse_api_date(int(text))

    text = text.replace("/", "-")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _record_date(item: dict) -> date | None:
    """Extract the calendar date a DeyeCloud data record belongs to."""
    item_date = _parse_api_date(
        item.get("date")
        or item.get("time")
        or item.get("timestamp")
        or item.get("collectionTime")
    )
    if item_date is not None:
        return item_date

    year, month, day = item.get("year"), item.get("month"), item.get("day")
    try:
        if year and month and day:
            return date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None
    return None


def _is_midnight_guard_window(now: datetime) -> bool:
    start = datetime.combine(now.date(), datetime.min.time(), tzinfo=now.tzinfo)
    return now - start < _MIDNIGHT_STALE_GUARD


def _select_daily_record(
    daily_items: list, day: str, *, allow_undated_fallback: bool
) -> dict | None:
    """Select only the record that actually belongs to the requested day."""
    target = datetime.strptime(day, "%Y-%m-%d").date()
    has_date_field = False

    for item in daily_items:
        item_date = _record_date(item)
        if item_date is None:
            continue
        has_date_field = True
        if item_date == target:
            return item

    if allow_undated_fallback and not has_date_field and len(daily_items) == 1:
        return daily_items[0]

    return None


class DeyeCloudCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches all Deye Cloud data."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: DeyeCloudAPI
    ):
        super().__init__(
            hass, _LOGGER, name="Deye Cloud", update_interval=SCAN_INTERVAL
        )
        self.entry = entry
        self.api = api
        self._serial_number = entry.data[CONF_SERIAL_NUMBER]
        self._history_start = entry.data.get(CONF_START_MONTH, "2026-04")
        self._last_config_refresh: datetime | None = None
        self._station_id: int | None = None
        self._device_sn: str | None = None

    @property
    def device_sn(self) -> str | None:
        """Return the inverter serial number."""
        return self._device_sn

    @property
    def station_id(self) -> int | None:
        """Return the station ID."""
        return self._station_id

    async def _async_update_data(self) -> dict:
        try:
            return await self._fetch_all_data()
        except DeyeCloudAuthError as exc:
            raise UpdateFailed(f"Authentication failed: {exc}") from exc
        except DeyeCloudAPIError as exc:
            raise UpdateFailed(f"API error: {exc}") from exc
        except Exception as exc:
            raise UpdateFailed(f"Unexpected error: {exc}") from exc

    async def _fetch_all_data(self) -> dict:
        # Discover station and device on first run
        if not self._station_id or not self._device_sn:
            await self._discover_station_and_device()

        result: dict = {
            "station_id": self._station_id,
            "device_sn": self._device_sn,
        }

        # Station info from list
        stations = await self.api.get_station_list()
        result["station_info"] = next(
            (
                s
                for s in stations
                if (s.get("id") or s.get("stationId")) == self._station_id
            ),
            {},
        )

        # Station latest (real-time power flow)
        result["station_latest"] = await self._safe_fetch(
            self.api.get_station_latest, self._station_id
        ) or {}

        # Monthly history
        result["history"] = await self._fetch_monthly_history()

        # Daily history (today, yesterday, day_before)
        result["daily"] = await self._fetch_daily_history()

        # Device latest data
        try:
            device_data_list = await self.api.get_device_latest(
                [self._device_sn]
            )
            result["device_latest"] = (
                device_data_list[0] if device_data_list else {}
            )
        except Exception as exc:
            _LOGGER.warning("Failed to fetch device latest: %s", exc)
            result["device_latest"] = self.data.get("device_latest", {}) if self.data else {}

        # Config data (refresh every CONFIG_REFRESH_INTERVAL)
        now = dt_util.utcnow()
        needs_config = (
            self._last_config_refresh is None
            or (now - self._last_config_refresh) >= CONFIG_REFRESH_INTERVAL
        )

        if needs_config:
            result["battery_config"] = await self._safe_fetch(
                self.api.get_battery_config, self._device_sn
            )
            result["system_config"] = await self._safe_fetch(
                self.api.get_system_config, self._device_sn
            )
            result["tou_config"] = await self._safe_fetch(
                self.api.get_tou_config, self._device_sn
            )
            self._last_config_refresh = now
        else:
            prev = self.data or {}
            result["battery_config"] = prev.get("battery_config")
            result["system_config"] = prev.get("system_config")
            result["tou_config"] = prev.get("tou_config")

        return result

    async def _discover_station_and_device(self) -> None:
        """Find the station containing the configured serial number."""
        stations = await self.api.get_station_list()
        if not stations:
            raise UpdateFailed("No stations found")

        for station in stations:
            station_id = station.get("id") or station.get("stationId")
            if not station_id:
                continue
            devices = await self.api.get_station_devices([station_id])
            for device in devices:
                if (
                    device.get("deviceType") == "INVERTER"
                    and device.get("deviceSn") == self._serial_number
                ):
                    self._station_id = station_id
                    self._device_sn = device["deviceSn"]
                    _LOGGER.info(
                        "Found inverter %s in station %s",
                        self._device_sn,
                        self._station_id,
                    )
                    return

        raise UpdateFailed(
            f"Serial number {self._serial_number} not found in any station"
        )

    async def _fetch_monthly_history(self) -> list:
        start_dt = datetime.strptime(self._history_start, "%Y-%m")
        start = start_dt.date().replace(day=1)
        end = dt_util.now().date().replace(day=1)
        items: list = []

        while start <= end:
            range_start = start
            range_end = min(range_start + relativedelta(months=11), end)
            try:
                batch = await self.api.get_station_history(
                    self._station_id,
                    3,
                    range_start.strftime("%Y-%m"),
                    range_end.strftime("%Y-%m"),
                )
                items.extend(batch)
            except Exception as exc:
                _LOGGER.warning(
                    "Failed to fetch monthly history batch: %s", exc
                )
            start = range_end + relativedelta(months=1)

        return items

    async def _fetch_daily_history(self) -> dict:
        today = dt_util.now().date()
        now = dt_util.now()
        previous_daily = (self.data or {}).get("daily", {}) if self.data else {}
        daily: dict = {}

        for offset in range(3):  # today, yesterday, day_before
            d = today - timedelta(days=offset)
            start_date = d.isoformat()
            end_date = (d + timedelta(days=1)).isoformat()
            is_today = offset == 0
            try:
                items = await self.api.get_station_history(
                    self._station_id, 2, start_date, end_date
                )
            except Exception as exc:
                _LOGGER.warning(
                    "Failed to fetch daily history for %s: %s",
                    start_date,
                    exc,
                )
                continue

            # Undated single-record fallback is disabled for "today" while
            # we're still guarding against a stale bucket, to avoid mapping
            # yesterday's only record into the new day.
            cached_today = previous_daily.get(start_date) if is_today else None
            in_guard_window = is_today and _is_midnight_guard_window(now)
            guarding_placeholder = bool(
                cached_today and cached_today.get("_deyecloud_placeholder")
            )
            allow_fallback = not (in_guard_window or guarding_placeholder)
            record = _select_daily_record(
                items or [], start_date, allow_undated_fallback=allow_fallback
            )

            if is_today:
                yesterday_key = (today - timedelta(days=1)).isoformat()
                reference = previous_daily.get(yesterday_key)
                if _should_reject_stale_today(
                    record,
                    reference,
                    cached_today,
                    in_midnight_guard=in_guard_window,
                ):
                    _LOGGER.debug(
                        "Stale daily bucket detected for %s; reporting "
                        "zero until DeyeCloud publishes real data",
                        start_date,
                    )
                    record = _empty_daily_record(start_date)

            if record is not None:
                daily[start_date] = record

        return daily

    async def _safe_fetch(self, func, *args, **kwargs):
        """Call an API method, returning None on failure."""
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            _LOGGER.debug(
                "Optional fetch failed (may not be supported): %s", exc
            )
            return None
