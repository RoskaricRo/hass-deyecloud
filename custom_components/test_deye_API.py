import asyncio
import aiohttp
import hashlib
import json
import logging
import sys

# Setting debugging level
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DeyeCloudTest")

# ==========================================================
# ENTER YOUR DETAILS HERE
# ==========================================================
USERNAME = "email@domain.com"
PASSWORD = "password for cloud"
APP_ID = "app_id from developer portal"
APP_SECRET = "app_secret_from developer portal"

# Check if your account uses different URL
BASE_URL = "https://eu1-developer.deyecloud.com/v1.0"
# ==========================================================

def _sha256(password: str) -> str:
    """Hashing password which is used for Deye API."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest().lower()

async def test_deye_api():
    async with aiohttp.ClientSession() as session:
        # ==========================================
        # 1. STEP: Login and get token
        # ==========================================
        token_url = f"{BASE_URL}/account/token?appId={APP_ID}"
        payload = {
          "appSecret": app_secret,
          "password": _sha256(password),
        }
    
        if "@" in username:
           payload["email"] = username
        else:
           payload["username"] = username
        
        logger.info("--- Step 1: Login and get token ---")
        logger.debug(f"URL: {token_url}")
        
        token = None
        try:
            async with session.post(token_url, json=payload, timeout=15) as resp:
                logger.info(f"HTTP login status: {resp.status}")
                raw_text = await resp.text()
                logger.debug(f"Response (RAW): {raw_text}")
                
                resp.raise_for_status()
                j = json.loads(raw_text)
                
                if not j.get("success"):
                    logger.error(f"Login failed: {j.get('msg')} (Code: {j.get('code', 'unknown')})")
                    return
                
                token = j.get("accessToken")
                logger.info("✅ Login successful! Token obtained.")
                
        except Exception as e:
            logger.error(f"❌ Error in authorization: {e}")
            return

        if not token:
            logger.error("❌ Token is emtpy, interrupting execution.")
            return

        # ==========================================
        # 2. STEP: Getting a list of stations
        # ==========================================
        logger.info("\n--- Step 2: Getting a list of stations ---")
        station_url = f"{BASE_URL}/station/list"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        logger.debug(f"URL: {station_url}")
        logger.debug(f"Headers: {{'Authorization': 'Bearer {token[:10]}...'}}")
        
        try:
            # Integration sends empty JSON when calling station list
            async with session.post(station_url, headers=headers, json={}, timeout=15) as resp:
                logger.info(f"HTTP stations status: {resp.status}")
                raw_text = await resp.text()
                logger.debug(f"Answer (RAW): {raw_text}")
                
                resp.raise_for_status()
                j = json.loads(raw_text)
                
                if not j.get("success"):
                    logger.error(f"Failed to acquire stations: {j.get('msg')}")
                    return
                
                stations = j.get("stationList", [])
                logger.info(f"✅ Successfully acquired {len(stations)} stations.")
                
                for i, station in enumerate(stations, 1):
                    # The API can return an ID under 'id' or 'stationId'
                    s_id = station.get('id') or station.get('stationId')
                    s_name = station.get('stationName', 'Unknown name')
                    s_status = station.get('status', 'Unknown status')
                    
                    logger.info(f"  [{i}] ID: {s_id} | Name: {s_name} | Status: {s_status}")
                    logger.debug(f"  Station details: {json.dumps(station, indent=2)}")
                    
        except Exception as e:
            logger.error(f"❌ Error while acquiring stations: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_deye_api())
    except KeyboardInterrupt:
        logger.info("\nTerminated by user.")
