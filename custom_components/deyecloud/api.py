import hashlib
import logging
import aiohttp
import asyncio
import json

_LOGGER = logging.getLogger(__name__)

def _sha256(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest().lower()

async def async_get_token(session: aiohttp.ClientSession, username, password, app_id, app_secret, base_url):
    url = f"{base_url}/account/token?appId={app_id}"
    payload = {"appSecret": app_secret, "password": _sha256(password)}
    if "@" in username: payload["email"] = username
    else: payload["username"] = username

    _LOGGER.debug(f"Requesting token from API: {url}")
    try:
        async with session.post(url, json=payload, timeout=15) as resp:
            resp.raise_for_status()
            raw_response = await resp.text()
            j = json.loads(raw_response)
            if not j.get("success"):
                raise Exception(f"Token request failed: {j.get('msg')}")
            return j["accessToken"]
    except Exception as e:
        _LOGGER.error(f"Unexpected error during token request: {e}")
        raise

async def async_control_solar_sell(session: aiohttp.ClientSession, token, base_url, device_sn, is_enable):
    url = f"{base_url}/order/sys/solarSell/control"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    action = "on" if is_enable else "off"
    payload = {"action": action, "deviceSn": device_sn}

    try:
        async with session.post(url, json=payload, headers=headers, timeout=15) as resp:
            resp.raise_for_status()
            j = await resp.json()
            if not j.get("success"): _LOGGER.error(f"Solar sell control failed: {j.get('msg')}")
            return j
    except Exception as e:
        _LOGGER.error(f"Failed to execute solar sell control for device {device_sn}: {e}")
        raise

async def async_get_device_alarms(session: aiohttp.ClientSession, token, base_url, device_sn):
    """Fetch active diagnostic alarms for a specific device."""
    # Uporabili bomo standardni endpoint za branje alarmov naprave
    url = f"{base_url}/device/alertList"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"deviceSn": device_sn, "page": 1, "size": 20, "status": 0} # status 0 = active

    try:
        async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
            if resp.status != 200:
                _LOGGER.debug(f"Alarm endpoint returned HTTP {resp.status}, ignoring.")
                return []
            j = await resp.json()
            if not j.get("success"):
                _LOGGER.debug(f"Alarm endpoint returned success: false. Ignoring.")
                return []

            # API ponavadi vrne list znotraj 'alertList' ali 'list' ali 'data'
            alarms = j.get("alertList", j.get("list", j.get("items", j.get("data", []))))
            if isinstance(alarms, list):
                return alarms
            return []
    except Exception as e:
        _LOGGER.debug(f"Could not fetch alarms for {device_sn} (Feature might not be supported by your account): {e}")
        return []
