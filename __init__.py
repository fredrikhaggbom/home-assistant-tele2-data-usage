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
    return res


async def _dry_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up using yaml config file."""
    _LOGGER.debug("Tele2 setup done!")
    return True


class Tele2Manager:
    """Holds the data"""

    def __init__(self, hass: HomeAssistant, config: Config):
        self._hass = hass
        self.pollDecreaseFactor = 4

        _LOGGER.debug("Init with config: ", str(config))
        self._data = {
            RES_UNLIMITED: False,
            RES_USAGE: None,
            RES_LIMIT: None,
            RES_DATA_LEFT: None,
            RES_PERIOD_START: None,
            RES_PERIOD_END: None,
        }
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
        self.initialUpdate()

    def getSubscription(self) -> dict:
        return self.api.getSubscription()

    async def initialUpdate(self):
        _LOGGER.debug("Updating initial data")
        self._data = await self._hass.async_add_executor_job(self.api.getDataUsage)
        _LOGGER.debug("Updated data: %s", str(self._data))

    def updateFromApi(self):
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
            return
        if self.isUpdating:
            return

        self.isUpdating = True
        _LOGGER.debug("Updating values from API")
        newData = self.api.getDataUsage()
        self.isDecreasing = False
        if (
            RES_DATA_LEFT in self._data
            and self._data[RES_DATA_LEFT] is not None
            and RES_DATA_LEFT in newData
            and newData[RES_DATA_LEFT] is not None
        ):
            self.isDecreasing = newData[RES_DATA_LEFT] < self._data[RES_DATA_LEFT]
            _LOGGER.debug(
                "newdata: %f, olddata: %f. isdecreasing: %s",
                newData[RES_DATA_LEFT],
                self._data[RES_DATA_LEFT],
                str(self.isDecreasing),
            )

        self._data = newData
        _LOGGER.debug("Updated data: %s", str(self._data))

        self.lastPoll = datetime.datetime.now()
        self.tries = 0
        self.isUpdating = False
        _LOGGER.debug("Update complete")

    async def _update(self):
        await self._hass.async_add_executor_job(self.updateFromApi)
