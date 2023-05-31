import logging
import requests
import datetime
import json
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

from .const import (
    DOMAIN,
    POLL_INTERVAL,
    RES_UNLIMITED,
    RES_LIMIT,
    RES_USAGE,
    RES_DATA_LEFT,
    RES_PERIOD_START,
    RES_PERIOD_END,
    CONF_SUBSCRIPTION,
    CONF_SUBSCRIPTIONMODEL,
    Tele2ApiResult,
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
    # @TODO: Add setup code.
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


async def async_update(self) -> None:
    _LOGGER.debug("UPDATE IN INIT")


class Tele2Session:
    """Holds the data"""

    def __init__(self, hass: HomeAssistant, config: Config):
        self._hass = hass
        self._last_tick = None
        self._data = {
            RES_UNLIMITED: False,
            RES_USAGE: None,
            RES_LIMIT: None,
            RES_DATA_LEFT: None,
            RES_PERIOD_START: None,
            RES_PERIOD_END: None,
        }
        self.config = config

        _LOGGER.debug("Init with config: ", str(config))

        if CONF_NAME in config:
            name = config[CONF_NAME]
        if POLL_INTERVAL in config:
            pollInterval = config.get(POLL_INTERVAL)
        if CONF_USERNAME in config:
            username = config.get(CONF_USERNAME)
        if CONF_PASSWORD in config:
            password = config.get(CONF_PASSWORD)

        if (
            CONF_NAME in config
            and POLL_INTERVAL in config
            and CONF_USERNAME in config
            and CONF_PASSWORD in config
        ):
            _LOGGER.debug(
                "Initing Tele2Session with: %s, %s, %s, %s",
                name,
                str(pollInterval),
                username,
                "****",
            )
            if CONF_SUBSCRIPTION in config:
                self.subscriptionId = config[CONF_SUBSCRIPTION]
            else:
                self.subscriptionId = "unknown"
            self.pollInterval = pollInterval
            self.BASE_URL = "https://my.tso.tele2.se"
            self.AUTH_URL = self.BASE_URL + "/auth/login"
            self.DATA_USAGE_URL = (
                self.BASE_URL
                + "/api/subscriptions/"
                + self.subscriptionId
                + "/data-usage"
            )
            self.SUBSCRIPTION_URL = (
                self.BASE_URL + "/api/subscriptions?refreshableOnly=false"
            )
            self.CREDENTIALS = {"username": username, "password": password}
            self.username = username
            self.isUpdating = False

            self.session = requests.Session()
            self.tries = 0

            self.lastPoll = datetime.datetime.now() - datetime.timedelta(30)

    def getSubscription(self) -> dict:
        self.session.post(self.AUTH_URL, data=self.CREDENTIALS)
        resp = self.session.get(self.SUBSCRIPTION_URL)

        if resp.status_code == 200:
            data = json.loads(resp.content)
            if len(data) > 0 and "subsId" in data[0]:
                return {
                    CONF_SUBSCRIPTION: str(data[0]["subsId"]),
                    CONF_SUBSCRIPTIONMODEL: data[0]["name"],
                }

        return {}

    def logInfo(self):
        _LOGGER.debug("In log info")
        if DOMAIN in self.config:
            _LOGGER.debug("Info: nam: %s", str(self.config[DOMAIN]))

    def doTheUpdate(self):
        _LOGGER.debug("calling _update from init")
        deltaSeconds = (datetime.datetime.now() - self.lastPoll).total_seconds()
        if round(deltaSeconds) < self.pollInterval:
            _LOGGER.debug(
                "Will wait until more time passed (seconds since last: %s, poll interval: %s)",
                round(deltaSeconds),
                self.pollInterval,
            )
            return
        if self.isUpdating:
            return

        self.isUpdating = True
        _LOGGER.debug("updating value")
        resp = self.session.get(self.DATA_USAGE_URL)
        if (resp.status_code == 401 or resp.status_code == 403) and self.tries < 1:
            _LOGGER.debug("error with status code: %d", resp.status_code)
            self.tries += 1
            self.isUpdating = False
            self.updateAuth()
            self.doTheUpdate()
            return
        elif resp.status_code == 200:
            data = json.loads(resp.content)
            limit = data[Tele2ApiResult.packageLimit]
            usage = data["usage"]
            remaining = data[Tele2ApiResult.remaining]
            _LOGGER.debug(
                "got result. Limit: %s, usage: %s, unlimited: %s",
                limit,
                usage,
                data[Tele2ApiResult.unlimitedData],
            )

            if Tele2ApiResult.unlimitedData in data:
                self._data[RES_UNLIMITED] = data[Tele2ApiResult.unlimitedData]

            if Tele2ApiResult.buckets in data and len(data["buckets"]) > 0:
                bucket = data["buckets"][0]
                if Tele2ApiResult.startDate in bucket:
                    startDate = datetime.datetime.strptime(
                        bucket[Tele2ApiResult.startDate], "%Y-%m-%d"
                    ).date()
                    self._data[RES_PERIOD_START] = startDate
                if Tele2ApiResult.endDate in bucket:
                    endDate = datetime.datetime.strptime(
                        bucket[Tele2ApiResult.endDate], "%Y-%m-%d"
                    ).date()
                    self._data[RES_PERIOD_END] = endDate

            if limit is not None and usage is not None:
                self.lastPoll = datetime.datetime.now()
                dataLeft = remaining
                _LOGGER.debug("Setting native value to: %d", dataLeft)
                self.tries = 0
                self._data[RES_LIMIT] = limit
                self._data[RES_USAGE] = usage
                self._data[RES_DATA_LEFT] = dataLeft
                self.isUpdating = False
                return
        else:
            self.isUpdating = False
            _LOGGER.debug("Error. Code: " + str(resp.status_code))

        self.lastPoll = datetime.datetime.now()
        self.tries = 0
        self.isUpdating = False

    async def _update(self):
        await self._hass.async_add_executor_job(self.doTheUpdate)

    def updateAuth(self) -> None:
        _LOGGER.debug("Updating authentication")
        self.session.post(self.AUTH_URL, data=self.CREDENTIALS)
