"""Deye Cloud integration for Home Assistant."""

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DeyeCloudAPI
from .const import (
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_BASE_URL,
    CONF_COMPANY_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from .coordinator import DeyeCloudCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "switch", "number", "select"]

# ---------------------------------------------------------------------------
# Bundled Lovelace energy-flow card, ported from heavenknows1978/hass-deyecloud.
# ---------------------------------------------------------------------------
CARD_VERSION = "2.2.5"
CARD_STATIC_URL = "/deyecloud/frontend"
CARD_MODULE_URL = (
    f"{CARD_STATIC_URL}/deyecloud-energy-flow-card-v225.js?v={CARD_VERSION}"
)
DATA_FRONTEND_MODULE_URL = "frontend_module_url"


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve and automatically load the bundled Lovelace card."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(DATA_FRONTEND_MODULE_URL) == CARD_MODULE_URL:
        return

    frontend_dir = Path(__file__).parent / "frontend"
    card_file = frontend_dir / "deyecloud-energy-flow-card-v225.js"
    if not card_file.is_file():
        _LOGGER.error("Bundled DeyeCloud frontend card is missing: %s", card_file)
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_STATIC_URL, str(frontend_dir), False)]
    )
    add_extra_js_url(hass, CARD_MODULE_URL)
    domain_data[DATA_FRONTEND_MODULE_URL] = CARD_MODULE_URL
    _LOGGER.info(
        "Registered bundled DeyeCloud Energy Flow card resource: %s",
        CARD_MODULE_URL,
    )


async def async_setup(hass: HomeAssistant, config: dict):
    await _async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    await _async_register_frontend(hass)

    session = async_get_clientsession(hass)
    api = DeyeCloudAPI(
        session=session,
        base_url=entry.data[CONF_BASE_URL],
        app_id=entry.data[CONF_APP_ID],
        app_secret=entry.data[CONF_APP_SECRET],
        email=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        company_id=entry.data.get(CONF_COMPANY_ID),
    )

    coordinator = DeyeCloudCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
