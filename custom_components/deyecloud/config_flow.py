import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import aiohttp
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_APP_ID, CONF_APP_SECRET, CONF_BASE_URL, CONF_START_MONTH, CONF_SERIAL_NUMBER
from .api import async_get_token

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Required(CONF_SERIAL_NUMBER): str,
    vol.Required(CONF_APP_ID): str,
    vol.Required(CONF_APP_SECRET): str,
    vol.Required(CONF_BASE_URL, default="https://eu1-developer.deyecloud.com/v1.0"): str,
    vol.Required(CONF_START_MONTH, default="2024-01"): str,
})

class DeyeCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            try:
                async with aiohttp.ClientSession() as session:
                    await async_get_token(
                        session,
                        user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                        user_input[CONF_APP_ID],
                        user_input[CONF_APP_SECRET],
                        user_input[CONF_BASE_URL]
                    )
                return self.async_create_entry(
                    title=f"DeyeCloud - {user_input[CONF_USERNAME]}",
                    data=user_input
                )
            except Exception as e:
                errors["base"] = f"auth_failed: {str(e)}"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors
        )

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Handle reconfiguration of the integration."""
        errors = {}
        if user_input is not None:
            try:
                async with aiohttp.ClientSession() as session:
                    await async_get_token(
                        session,
                        user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                        user_input[CONF_APP_ID],
                        user_input[CONF_APP_SECRET],
                        user_input[CONF_BASE_URL]
                    )
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    title=f"DeyeCloud - {user_input[CONF_USERNAME]}",
                    data=user_input,
                )
            except Exception as e:
                errors["base"] = f"auth_failed: {str(e)}"

        current_data = self._get_reconfigure_entry().data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME, default=current_data.get(CONF_USERNAME)): str,
                vol.Required(CONF_PASSWORD, default=current_data.get(CONF_PASSWORD)): str,
                vol.Required(CONF_SERIAL_NUMBER, default=current_data.get(CONF_SERIAL_NUMBER)): str,
                vol.Required(CONF_APP_ID, default=current_data.get(CONF_APP_ID)): str,
                vol.Required(CONF_APP_SECRET, default=current_data.get(CONF_APP_SECRET)): str,
                vol.Required(CONF_BASE_URL, default=current_data.get(CONF_BASE_URL, "https://eu1-developer.deyecloud.com/v1.0")): str,
                vol.Required(CONF_START_MONTH, default=current_data.get(CONF_START_MONTH, "2024-01")): str,
            }),
            errors=errors
        )
