import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_NORDPOOL_ENTITY,
    CONF_FIXED_THRESHOLD,
    CONF_LOW_TARGET_PER_DAY,
    CONF_LOW_TIME_WINDOW,
    CONF_HIGH_TARGET_PER_DAY,
    CONF_HIGH_TIME_WINDOW,
    DEFAULT_FIXED_THRESHOLD,
    DEFAULT_LOW_TARGET,
    DEFAULT_LOW_WINDOW,
    DEFAULT_HIGH_TARGET,
    DEFAULT_HIGH_WINDOW,
)


class NordpoolSmartPlannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="Nordpool Smart Planner",
                data=user_input,
            )

        data_schema = vol.Schema({
            vol.Required(CONF_NORDPOOL_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_FIXED_THRESHOLD, default=DEFAULT_FIXED_THRESHOLD): vol.Coerce(float),
            vol.Optional(CONF_LOW_TARGET_PER_DAY, default=DEFAULT_LOW_TARGET): vol.Coerce(int),
            vol.Optional(CONF_LOW_TIME_WINDOW, default=DEFAULT_LOW_WINDOW): vol.Coerce(float),
            vol.Optional(CONF_HIGH_TARGET_PER_DAY, default=DEFAULT_HIGH_TARGET): vol.Coerce(int),
            vol.Optional(CONF_HIGH_TIME_WINDOW, default=DEFAULT_HIGH_WINDOW): vol.Coerce(float),
        })

        return self.async_show_form(step_id="user", data_schema=data_schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NordpoolSmartPlannerOptionsFlowHandler(config_entry)


class NordpoolSmartPlannerOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_data = {**self._config_entry.data, **self._config_entry.options}

        options_schema = vol.Schema({
            vol.Optional(
                CONF_FIXED_THRESHOLD,
                default=current_data.get(CONF_FIXED_THRESHOLD, DEFAULT_FIXED_THRESHOLD),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_LOW_TARGET_PER_DAY,
                default=current_data.get(CONF_LOW_TARGET_PER_DAY, DEFAULT_LOW_TARGET),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_LOW_TIME_WINDOW,
                default=current_data.get(CONF_LOW_TIME_WINDOW, DEFAULT_LOW_WINDOW),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_HIGH_TARGET_PER_DAY,
                default=current_data.get(CONF_HIGH_TARGET_PER_DAY, DEFAULT_HIGH_TARGET),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_HIGH_TIME_WINDOW,
                default=current_data.get(CONF_HIGH_TIME_WINDOW, DEFAULT_HIGH_WINDOW),
            ): vol.Coerce(float),
        })

        return self.async_show_form(step_id="init", data_schema=options_schema)