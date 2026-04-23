"""Deye Cloud API client."""

import hashlib
import logging
from datetime import datetime, timedelta

import aiohttp

_LOGGER = logging.getLogger(__name__)


class DeyeCloudAPIError(Exception):
    """Base exception for Deye Cloud API errors."""


class DeyeCloudAuthError(DeyeCloudAPIError):
    """Authentication error."""


class DeyeCloudAPI:
    """Client for the Deye Cloud developer API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        app_id: str,
        app_secret: str,
        email: str,
        password: str,
    ):
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._app_id = app_id
        self._app_secret = app_secret
        self._email = email
        self._password_hash = hashlib.sha256(
            password.encode("utf-8")
        ).hexdigest().lower()
        self._token: str | None = None
        self._token_expiry: datetime | None = None

    # ------------------------------------------------------------------ auth

    async def authenticate(self) -> str:
        """Obtain a new access token. Returns the token string."""
        url = f"{self._base_url}/account/token?appId={self._app_id}"
        payload = {
            "appSecret": self._app_secret,
            "email": self._email,
            "password": self._password_hash,
        }
        async with self._session.post(
            url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            if not data.get("success"):
                raise DeyeCloudAuthError(
                    f"Authentication failed: {data.get('msg')}"
                )
            self._token = data["accessToken"]
            self._token_expiry = datetime.utcnow() + timedelta(minutes=25)
            _LOGGER.debug("Token refreshed successfully")
            return self._token

    async def _ensure_token(self) -> None:
        now = datetime.utcnow()
        if self._token and self._token_expiry and self._token_expiry > now:
            return
        await self.authenticate()

    # -------------------------------------------------------------- request

    async def _request(
        self,
        method: str,
        path: str,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Make an authenticated API request."""
        await self._ensure_token()
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._token}"}

        async with self._session.request(
            method,
            url,
            headers=headers,
            json=json_data,
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            if not data.get("success"):
                msg = data.get("msg", "Unknown error")
                code = data.get("code", "")
                raise DeyeCloudAPIError(f"API error [{code}]: {msg}")
            return data

    # ============================================================== Account

    async def get_account_info(self) -> list:
        """Query which company the account belongs to and the role."""
        data = await self._request("POST", "/account/info")
        return data.get("orgInfoList", [])

    # ============================================================== Station

    async def get_station_list(
        self, page: int = 1, size: int = 100
    ) -> list:
        """Fetch station list under account."""
        data = await self._request(
            "POST", "/station/list", {"page": page, "size": size}
        )
        return data.get("stationList", [])

    async def get_station_latest(self, station_id: int) -> dict:
        """Retrieve latest real-time station data."""
        return await self._request(
            "POST", "/station/latest", {"stationId": station_id}
        )

    async def get_station_history(
        self,
        station_id: int,
        granularity: int,
        start_at: str,
        end_at: str | None = None,
    ) -> list:
        """Retrieve station history (1=frame, 2=day, 3=month, 4=year)."""
        payload: dict = {
            "stationId": station_id,
            "granularity": granularity,
            "startAt": start_at,
        }
        if end_at:
            payload["endAt"] = end_at
        data = await self._request("POST", "/station/history", payload)
        return data.get("stationDataItems", [])

    async def get_station_history_power(
        self, station_id: int, start_timestamp: int, end_timestamp: int
    ) -> list:
        """History data by Unix timestamp; 12-month max span."""
        data = await self._request(
            "POST",
            "/station/history/power",
            {
                "stationId": station_id,
                "startTimestamp": start_timestamp,
                "endTimestamp": end_timestamp,
            },
        )
        return data.get("stationDataItems", [])

    async def get_station_devices(
        self, station_ids: list[int], page: int = 1, size: int = 100
    ) -> list:
        """Fetch device list for stations (up to 10 stations per batch)."""
        data = await self._request(
            "POST",
            "/station/device",
            {"stationIds": station_ids, "page": page, "size": size},
        )
        return data.get("deviceListItems", [])

    async def get_station_alerts(
        self,
        station_id: int,
        start_timestamp: int,
        end_timestamp: int,
        page: int = 1,
        size: int = 20,
    ) -> dict:
        """Retrieve alert list for a station; 180-day max span."""
        return await self._request(
            "POST",
            "/station/alertList",
            {
                "stationId": station_id,
                "startTimestamp": start_timestamp,
                "endTimestamp": end_timestamp,
                "page": page,
                "size": size,
            },
        )

    async def get_station_list_with_devices(
        self,
        page: int = 1,
        size: int = 100,
        device_type: str | None = None,
    ) -> dict:
        """Fetch stations with embedded device lists."""
        payload: dict = {"page": page, "size": size}
        if device_type:
            payload["deviceType"] = device_type
        return await self._request(
            "POST", "/station/listWithDevice", payload
        )

    # ============================================================== Device

    async def get_device_latest(self, device_sns: list[str]) -> list:
        """Fetch latest device data; batch up to 10 devices."""
        data = await self._request(
            "POST", "/device/latest", {"deviceList": device_sns}
        )
        return data.get("deviceDataList", [])

    async def get_device_list(
        self, page: int = 1, size: int = 100
    ) -> list:
        """Fetch device list for business members."""
        data = await self._request(
            "POST", "/device/list", {"page": page, "size": size}
        )
        return data.get("deviceList", [])

    async def get_device_alerts(
        self,
        start_timestamp: int,
        end_timestamp: int,
        device_sn: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> dict:
        """Retrieve device alert list using Unix timestamps."""
        payload: dict = {
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "page": page,
            "size": size,
        }
        if device_sn:
            payload["deviceSn"] = device_sn
        return await self._request("POST", "/device/alertList", payload)

    async def get_device_history(
        self,
        device_sn: str,
        granularity: int,
        start_at: str,
        end_at: str | None = None,
        measure_points: list[str] | None = None,
    ) -> dict:
        """Returns device history data at different granularities."""
        payload: dict = {
            "deviceSn": device_sn,
            "granularity": granularity,
            "startAt": start_at,
        }
        if end_at:
            payload["endAt"] = end_at
        if measure_points:
            payload["measurePoints"] = measure_points
        return await self._request("POST", "/device/history", payload)

    async def get_device_history_raw(
        self,
        device_sn: str,
        start_timestamp: int,
        end_timestamp: int,
        measure_points: list[str],
    ) -> dict:
        """Timestamp-based history retrieval; 5-day window maximum."""
        return await self._request(
            "POST",
            "/device/historyRaw",
            {
                "deviceSn": device_sn,
                "startTimestamp": start_timestamp,
                "endTimestamp": end_timestamp,
                "measurePoints": measure_points,
            },
        )

    async def get_device_measure_points(
        self, device_sn: str, device_type: str = "INVERTER"
    ) -> list:
        """Fetch available measure points for a device."""
        data = await self._request(
            "POST",
            "/device/measurePoints",
            {"deviceSn": device_sn, "deviceType": device_type},
        )
        return data.get("measurePoints", [])

    # =========================================================== Config

    async def get_battery_config(self, device_sn: str) -> dict:
        """Retrieve battery parameters (capacity, charge/discharge currents)."""
        return await self._request(
            "POST", "/config/battery", {"deviceSn": device_sn}
        )

    async def get_system_config(self, device_sn: str) -> dict:
        """Obtain system work mode related parameters."""
        return await self._request(
            "POST", "/config/system", {"deviceSn": device_sn}
        )

    async def get_tou_config(self, device_sn: str) -> dict:
        """Obtain time of use configuration."""
        return await self._request(
            "POST", "/config/tou", {"deviceSn": device_sn}
        )

    # ======================================================= Control/Order

    async def control_solar_sell(
        self, device_sn: str, action: str
    ) -> dict:
        """Enable or disable solar sell. action: 'on' or 'off'."""
        return await self._request(
            "POST",
            "/order/sys/solarSell/control",
            {"deviceSn": device_sn, "action": action},
        )

    async def control_battery_mode(
        self, device_sn: str, action: str, battery_mode_type: str
    ) -> dict:
        """Enable/disable charge modes. battery_mode_type: GEN_CHARGE or GRID_CHARGE."""
        return await self._request(
            "POST",
            "/order/battery/modeControl",
            {
                "deviceSn": device_sn,
                "action": action,
                "batteryModeType": battery_mode_type,
            },
        )

    async def update_battery_parameter(
        self, device_sn: str, parameter_type: str, value: int
    ) -> dict:
        """Set battery-related parameter values.

        parameter_type: MAX_CHARGE_CURRENT, MAX_DISCHARGE_CURRENT,
                        GRID_CHARGE_AMPERE, BATT_LOW
        """
        return await self._request(
            "POST",
            "/order/battery/parameter/update",
            {
                "deviceSn": device_sn,
                "paramterType": parameter_type,  # API spelling
                "value": value,
            },
        )

    async def update_battery_type(
        self, device_sn: str, battery_type: str
    ) -> dict:
        """Set battery type. battery_type: BATT_V, BATT_SOC, LI, NO_BATTERY."""
        return await self._request(
            "POST",
            "/order/battery/type/update",
            {"deviceSn": device_sn, "batteryType": battery_type},
        )

    async def control_grid_peak_shaving(
        self, device_sn: str, action: str, power: int
    ) -> dict:
        """Enable/disable grid peak shaving functionality."""
        return await self._request(
            "POST",
            "/order/gridPeakShaving/control",
            {"deviceSn": device_sn, "action": action, "power": power},
        )

    async def update_smart_load(self, device_sn: str, **kwargs) -> dict:
        """Set smart-load parameters (onVoltage, offVoltage, onSOC, offSOC, onGridAlwaysOn)."""
        payload: dict = {"deviceSn": device_sn}
        for key in (
            "deviceType",
            "onVoltage",
            "offVoltage",
            "onSOC",
            "offSOC",
            "onGridAlwaysOn",
        ):
            if key in kwargs:
                payload[key] = kwargs[key]
        return await self._request(
            "POST", "/order/smartload/update", payload
        )

    async def update_energy_pattern(
        self, device_sn: str, energy_pattern: str
    ) -> dict:
        """Set energy pattern: BATTERY_FIRST or LOAD_FIRST."""
        return await self._request(
            "POST",
            "/order/sys/energyPattern/update",
            {"deviceSn": device_sn, "energyPattern": energy_pattern},
        )

    async def update_limit_control(
        self, device_sn: str, limit_control_type: str
    ) -> dict:
        """Set limit control function (Micro ESS only)."""
        return await self._request(
            "POST",
            "/order/sys/limitControl",
            {
                "deviceSn": device_sn,
                "limitControlFunctionType": limit_control_type,
            },
        )

    async def update_system_power(
        self, device_sn: str, power_type: str, value: int
    ) -> dict:
        """Set power limits. power_type: MAX_SELL_POWER, MAX_SOLAR_POWER, ZERO_EXPORT_POWER."""
        return await self._request(
            "POST",
            "/order/sys/power/update",
            {"deviceSn": device_sn, "powerType": power_type, "value": value},
        )

    async def switch_tou(
        self, device_sn: str, action: str, days: list[str] | None = None
    ) -> dict:
        """Turn on/off TOU; days activate by default when enabled."""
        payload: dict = {"deviceSn": device_sn, "action": action}
        if days:
            payload["days"] = days
        return await self._request(
            "POST", "/order/sys/tou/switch", payload
        )

    async def update_tou(
        self, device_sn: str, time_use_setting_items: list[dict]
    ) -> dict:
        """Set time of use strategy in 5-minute intervals."""
        return await self._request(
            "POST",
            "/order/sys/tou/update",
            {
                "deviceSn": device_sn,
                "timeUseSettingItems": time_use_setting_items,
            },
        )

    async def update_work_mode(
        self, device_sn: str, work_mode: str
    ) -> dict:
        """Set system work mode."""
        return await self._request(
            "POST",
            "/order/sys/workMode/update",
            {"deviceSn": device_sn, "workMode": work_mode},
        )

    async def get_order_result(
        self, order_id: int, language: str = "en"
    ) -> dict:
        """Get command execution result. status 666 = success."""
        return await self._request(
            "GET",
            f"/order/{order_id}",
            params={"language": language},
        )

    # ============================================================ Strategy

    async def dynamic_control(self, device_sn: str, **kwargs) -> dict:
        """Dynamic control: unset parameters retain current values."""
        payload: dict = {"deviceSn": device_sn}
        for key in (
            "workMode",
            "maxSolarPower",
            "maxSellPower",
            "zeroExportPower",
            "gridChargeAction",
            "gridChargeAmpere",
            "solarSellAction",
            "touAction",
            "touDays",
            "timeUseSettingItems",
        ):
            if key in kwargs:
                payload[key] = kwargs[key]
        return await self._request(
            "POST", "/strategy/dynamicControl", payload
        )

    async def dynamic_control_read(self, device_sn: str) -> dict:
        """Send read command for dynamic control parameters. Returns orderId."""
        return await self._request(
            "POST",
            "/strategy/dynamicControl/read",
            {"deviceSn": device_sn},
        )

    async def dynamic_control_read_result(
        self, order_id: int | None = None
    ) -> dict:
        """Query dynamic control read results."""
        payload: dict = {}
        if order_id is not None:
            payload["orderId"] = order_id
        return await self._request(
            "POST", "/strategy/dynamicControl/readResult", payload
        )
