"""Adds config flow for Tele2."""
import logging
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.template import Template
from homeassistant.const import (
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant, callback

from pytele2api.const import (
    CONF_SUBSCRIPTION,
    CONF_SUBSCRIPTIONMODEL,
)

from .const import (
    DOMAIN,
    POLL_INTERVAL,
)
from . import Tele2Manager

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    _LOGGER.debug("Getting subId")
    hub = Tele2Manager(hass, data)
    # The dummy hub provides a `test_connection` method to ensure it's working
    # as expected
    result = await hass.async_add_executor_job(hub.getSubscription)
    if result == {}:
        raise CannotConnect

    _LOGGER.debug("Got subId: " + result[CONF_SUBSCRIPTION])
    return result


@staticmethod
@callback
def async_get_options_flow(config_entry):
    """Get the options flow for this handler."""
    return OptionsFlowHandler(config_entry)


class Tele2FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Tele2."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(
        self, user_input=None
    ):  # pylint: disable=dangerous-default-value
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            if CONF_USERNAME in user_input:
                await self.async_set_unique_id("Tele2-" + user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
            else:
                await self.async_set_unique_id("Tele2-" + "data")
                self._abort_if_unique_id_configured()

            subDetails = await validate_input(self.hass, user_input)
            user_input[CONF_SUBSCRIPTION] = subDetails[CONF_SUBSCRIPTION]
            user_input[CONF_SUBSCRIPTIONMODEL] = subDetails[CONF_SUBSCRIPTIONMODEL]

            return self.async_create_entry(title="Tele2", data=user_input)

        data_schema = {
            vol.Optional(CONF_NAME, default="Tele2 data usage"): str,
            vol.Optional(POLL_INTERVAL, default=1800): int,
            vol.Required(CONF_USERNAME, default=""): str,
            vol.Required(CONF_PASSWORD, default=""): str,
        }

        placeholders = {
            "username": "Username",
            "password": "Password",
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            description_placeholders=placeholders,
            errors=self._errors,
        )

    async def async_step_import(self, user_input):  # pylint: disable=unused-argument
        """Import a config entry.
        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        return self.async_create_entry(title="configuration.yaml", data={})


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, any] = None
    ) -> dict[str, any]:
        """Manage the options for the custom component."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Adding options: %s", user_input)
            _LOGGER.debug("Earlier: %s", self.config_entry)
            new_data = self.config_entry.data.copy()
            new_data[POLL_INTERVAL] = user_input[POLL_INTERVAL]

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )

            return self.async_create_entry(title="Tele2", data=user_input)

        currentPollInterval = 1800
        if POLL_INTERVAL in self.config_entry.data:
            currentPollInterval = self.config_entry.data[POLL_INTERVAL]

        options_schema = vol.Schema(
            {
                vol.Optional(POLL_INTERVAL, default=currentPollInterval): int,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
