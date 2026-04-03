import hashlib
import logging
import aiohttp
import asyncio
import json

_LOGGER = logging.getLogger(__name__)

def _sha256(password: str) -> str:
    """Encrypt password using SHA256 as required by Deye API."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest().lower()

async def async_get_token(session: aiohttp.ClientSession, username, password, app_id, app_secret, base_url):
    """Fetch the access token from DeyeCloud API."""
    url = f"{base_url}/account/token?appId={app_id}"
    payload = {
        "appSecret": app_secret,
        "username": username,
        "password": _sha256(password),
    }
    
    _LOGGER.debug(f"Requesting token from API: {url} | Username: {username}")
    
    try:
        async with session.post(url, json=payload, timeout=15) as resp:
            resp.raise_for_status()
            
            raw_response = await resp.text()
            _LOGGER.debug(f"Token response raw data: {raw_response}")
            
            j = json.loads(raw_response)
            if not j.get("success"):
                error_msg = j.get('msg', 'Unknown error')
                error_code = j.get('code', 'Unknown code')
                _LOGGER.error(f"Token request failed from Deye API. Message: {error_msg} (Code: {error_code})")
                raise Exception(f"Token request failed: {error_msg}")
            
            _LOGGER.info("Successfully acquired DeyeCloud API token.")
            return j["accessToken"]
            
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout while requesting token from DeyeCloud API. Server might be down or rate-limiting.")
        raise
    except aiohttp.ClientResponseError as e:
        _LOGGER.error(f"HTTP error during token request: Status {e.status} - {e.message}")
        raise
    except Exception as e:
        _LOGGER.error(f"Unexpected error during token request: {e}")
        raise

async def async_control_solar_sell(session: aiohttp.ClientSession, token, base_url, device_sn, is_enable):
    """Send Solar Sell control command."""
    url = f"{base_url}/order/sys/solarSell/control"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    action = "on" if is_enable else "off"
    payload = {
        "action": action,
        "deviceSn": device_sn
    }
    
    _LOGGER.debug(f"Sending solar sell control command to {url} | Action: {action} | Device: {device_sn}")
    
    try:
        async with session.post(url, json=payload, headers=headers, timeout=15) as resp:
            resp.raise_for_status()
            
            raw_response = await resp.text()
            _LOGGER.debug(f"Solar sell control response raw data: {raw_response}")
            
            j = json.loads(raw_response)
            if not j.get("success"):
                _LOGGER.error(f"Solar sell control failed: {j.get('msg', 'Unknown error')}")
            else:
                _LOGGER.info(f"Successfully sent solar sell command '{action}' to device {device_sn}")
                
            return j
            
    except Exception as e:
        _LOGGER.error(f"Failed to execute solar sell control for device {device_sn}: {e}")
        raise
