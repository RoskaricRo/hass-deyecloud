"""Config flow for Deye Cloud integration."""

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import DeyeCloudAPI, DeyeCloudAuthError
from .const import (
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_BASE_URL,
    CONF_PASSWORD,
    CONF_SERIAL_NUMBER,
    CONF_START_MONTH,
    CONF_USERNAME,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SERIAL_NUMBER): str,
        vol.Required(CONF_APP_ID): str,
        vol.Required(CONF_APP_SECRET): str,
        vol.Required(
            CONF_BASE_URL,
            default="https://eu1-developer.deyecloud.com/v1.0",
        ): str,
        vol.Required(CONF_START_MONTH, default="2024-01"): str,
    }
)


class DeyeCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate_credentials(self, user_input: dict) -> None:
        """Test authentication with the provided credentials."""
        async with aiohttp.ClientSession() as session:
            api = DeyeCloudAPI(
                session=session,
                base_url=user_input[CONF_BASE_URL],
                app_id=user_input[CONF_APP_ID],
                app_secret=user_input[CONF_APP_SECRET],
                email=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            await api.authenticate()

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            try:
                await self._validate_credentials(user_input)
                return self.async_create_entry(
                    title=f"DeyeCloud - {user_input[CONF_USERNAME]}",
                    data=user_input,
                )
            except DeyeCloudAuthError as e:
                errors["base"] = f"auth_failed: {e}"
            except Exception as e:
                errors["base"] = f"auth_failed: {e}"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            try:
                await self._validate_credentials(user_input)
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    title=f"DeyeCloud - {user_input[CONF_USERNAME]}",
                    data=user_input,
                )
            except DeyeCloudAuthError as e:
                errors["base"] = f"auth_failed: {e}"
            except Exception as e:
                errors["base"] = f"auth_failed: {e}"

        current_data = self._get_reconfigure_entry().data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=current_data.get(CONF_USERNAME),
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=current_data.get(CONF_PASSWORD),
                    ): str,
                    vol.Required(
                        CONF_SERIAL_NUMBER,
                        default=current_data.get(CONF_SERIAL_NUMBER),
                    ): str,
                    vol.Required(
                        CONF_APP_ID,
                        default=current_data.get(CONF_APP_ID),
                    ): str,
                    vol.Required(
                        CONF_APP_SECRET,
                        default=current_data.get(CONF_APP_SECRET),
                    ): str,
                    vol.Required(
                        CONF_BASE_URL,
                        default=current_data.get(
                            CONF_BASE_URL,
                            "https://eu1-developer.deyecloud.com/v1.0",
                        ),
                    ): str,
                    vol.Required(
                        CONF_START_MONTH,
                        default=current_data.get(CONF_START_MONTH, "2024-01"),
                    ): str,
                }
            ),
            errors=errors,
        )
