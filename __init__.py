import logging
import requests
import datetime
import json
import pytele2api

import voluptuous as vol

from homeassistant import core
from homeassistant.core import Config, HomeAssistant
from homeassistant.config_entries import ConfigEntry


from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
)

from pytele2api.const import (
    RES_UNLIMITED,
    RES_LIMIT,
    RES_USAGE,
    RES_DATA_LEFT,
    RES_PERIOD_START,
    RES_PERIOD_END,
    CONF_SUBSCRIPTION,
    CONF_SUBSCRIPTIONMODEL,
    RES_ERROR,
)

from .const import (
    DOMAIN,
    POLL_INTERVAL,
)

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default="Tele2 data usage"): cv.string,
        vol.Optional(POLL_INTERVAL, default=1800): cv.positive_int,
        vol.Required(CONF_USERNAME, default=""): cv.string,
        vol.Required(CONF_PASSWORD, default=""): cv.string,
        vol.Optional(CONF_SUBSCRIPTION, default=""): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the Tele2 Data usage component."""
    _LOGGER.debug("Init in async_setup: ", str(config))
    return await _dry_setup(hass, config)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tele2 as config entry."""
    _LOGGER.debug("Init in async_setup_entry: ", str(entry.data))
    res = await _dry_setup(hass, entry.data)
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    entry.add_update_listener(async_reload_entry)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return res


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    _LOGGER.debug("Unloading Tele2 component")
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    return True


async def _dry_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up using yaml config file."""
    _LOGGER.debug("Tele2 setup done!")
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def update_listener(hass, entry):
    """Handle options update."""
    _LOGGER.debug("Config changed, reloading!")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class Tele2Manager:
    """Holds the data"""

    def __init__(self, hass: HomeAssistant, config: Config):
        self._hass = hass
        self.pollDecreaseFactor = 4

        _LOGGER.debug("Init with config: ", str(config))

        if DOMAIN in hass.data:
            self._data = hass.data[DOMAIN]
            _LOGGER.debug("Setting up with stored data: %s", self._data)
        else:
            self._data = {
                RES_UNLIMITED: False,
                RES_USAGE: None,
                RES_LIMIT: None,
                RES_DATA_LEFT: None,
                RES_PERIOD_START: None,
                RES_PERIOD_END: None,
            }
            _LOGGER.debug("Setting up with new empty data")

        self.config = config

        if CONF_NAME in config:
            name = config[CONF_NAME]
        if POLL_INTERVAL in config:
            pollInterval = config.get(POLL_INTERVAL)
        if CONF_USERNAME in config:
            username = config.get(CONF_USERNAME)
        if CONF_PASSWORD in config:
            password = config.get(CONF_PASSWORD)

        _LOGGER.debug(
            "Initing Tele2Session with: %s, %s, %s, %s",
            name,
            str(pollInterval),
            username,
            "****",
        )

        subscriptionId = None
        if CONF_SUBSCRIPTION in config:
            subscriptionId = str(config[CONF_SUBSCRIPTION])

        self.api = pytele2api.Tele2Api(
            username, password, subscriptionId=subscriptionId
        )
        self.pollInterval = pollInterval
        self.username = username
        self.isUpdating = False
        self.isDecreasing = False
        self.lastPoll = datetime.datetime.now() - datetime.timedelta(30)
        self.oldDataLeft = 50000
        self.initialUpdate()

    def getSubscription(self) -> dict:
        return self.api.getSubscription()

    async def initialUpdate(self):
        _LOGGER.debug("Updating initial data")
        self._data = await self._hass.async_add_executor_job(self.api.getDataUsage)
        self._hass.data[DOMAIN] = self._data
        self.oldDataLeft = 0
        if RES_DATA_LEFT in self._data:
            self.oldDataLeft = self._data[RES_DATA_LEFT]

        if RES_ERROR in self._data and self._data[RES_ERROR] is not None:
            _LOGGER.error(
                "Error while updating Tele 2 data: %s", str(self._data[RES_ERROR])
            )
        _LOGGER.debug("Updated data: %s", str(self._data))

    def updateFromApi(self):
        if self.isUpdating:
            return

        self.isUpdating = True
        deltaSeconds = (datetime.datetime.now() - self.lastPoll).total_seconds()
        shouldPoll = round(deltaSeconds) >= self.pollInterval
        if self.isDecreasing:
            shouldPoll = round(deltaSeconds) >= round(
                self.pollInterval / self.pollDecreaseFactor
            )

        if not shouldPoll:
            _LOGGER.debug(
                "Will wait until more time passed (seconds since last: %s, poll interval: %s)",
                round(deltaSeconds),
                round(self.pollInterval / self.pollDecreaseFactor)
                if self.isDecreasing
                else self.pollInterval,
            )
            self.isUpdating = False
            return

        _LOGGER.debug("Updating values from API")
        self._data = self.api.getDataUsage()
        self._hass.data[DOMAIN] = self._data
        if RES_ERROR in self._data and self._data[RES_ERROR] is not None:
            _LOGGER.error(
                "Error while updating Tele 2 data: %s", str(self._data[RES_ERROR])
            )
            self.lastPoll = datetime.datetime.now()
            self.tries = 0
            self.isUpdating = False
            return

        self.isDecreasing = False
        if RES_DATA_LEFT in self._data and self._data[RES_DATA_LEFT] is not None:
            self.isDecreasing = self._data[RES_DATA_LEFT] < self.oldDataLeft
            _LOGGER.debug(
                "newdata: %f, olddata: %f. isdecreasing: %s",
                self._data[RES_DATA_LEFT],
                self.oldDataLeft,
                str(self.isDecreasing),
            )

        _LOGGER.debug("Updated data: %s", str(self._data))
        if RES_DATA_LEFT in self._data:
            self.oldDataLeft = self._data[RES_DATA_LEFT]

        self.lastPoll = datetime.datetime.now()
        self.tries = 0
        self.isUpdating = False
        _LOGGER.debug("Update complete")

    async def _update(self):
        await self._hass.async_add_executor_job(self.updateFromApi)
