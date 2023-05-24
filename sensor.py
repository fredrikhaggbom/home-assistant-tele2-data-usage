import voluptuous as vol
import requests
import json
import logging
import datetime

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Tele2 Data usage"
DOMAIN = "tele2_datausage"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default="Tele2 data usage"): cv.string,
        vol.Optional("poll_interval", default=1800): cv.positive_int,
        vol.Required("username", default=""): cv.string,
        vol.Required("password", default=""): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    name = config[CONF_NAME]
    pollInterval = config.get("poll_interval")
    username = config.get("username")
    password = config.get("password")

    add_entities([Tele2DataSensor(username, password, name, pollInterval)], True)
    return True


class Tele2DataSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, username, password, name, pollInterval) -> None:
        super().__init__()
        self._name = name
        self._attr_name = name
        # self._attr_native_unit_of_measurement = TEMP_CELSIUS
        self._attr_device_class = SensorDeviceClass.DATA_SIZE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES
        self._attr_native_value = 0
        self._attr_suggested_display_precision = None
        self._attr_suggested_unit_of_measurement = "GB"

        self.pollInterval = pollInterval
        self.BASE_URL = "https://my.tso.tele2.se"
        self.AUTH_URL = self.BASE_URL + "/auth/login"
        self.DATA_USAGE_URL = self.BASE_URL + "/api/subscriptions/22390478/data-usage"
        self.CREDENTIALS = {"username": username, "password": password}
        self.username = username

        self.session = requests.Session()
        self.tries = 0

        self.lastPoll = datetime.datetime.now() - datetime.timedelta(30)

        _LOGGER.debug("setting up with user %s", username)

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return "tele2" + self.username

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": DOMAIN,
        }

    def update(self) -> None:
        deltaSeconds = (datetime.datetime.now() - self.lastPoll).total_seconds()
        if round(deltaSeconds) < self.pollInterval:
            _LOGGER.debug("Will wait until more time passed (seconds since last: %s, poll interval: %s)", round(deltaSeconds), self.pollInterval)
            return
        
        _LOGGER.debug("updating value")
        resp = self.session.get(self.DATA_USAGE_URL)
        if (resp.status_code == 401 or resp.status_code == 403) and self.tries < 1:
            _LOGGER.debug("error with status code: %d", resp.status_code)
            self.tries += 1
            self.updateAuth()
            self.update()
            return
        elif resp.status_code == 200:
            data = json.loads(resp.content)
            limit = data["packageLimit"]
            usage = data["usage"]
            _LOGGER.debug("got result. Limit: %s, usage: %s", limit, usage)
            if limit is not None and usage is not None:
                self.lastPoll = datetime.datetime.now()
                dataLeft = round(limit - usage)
                _LOGGER.debug("Setting native value to: %d", dataLeft)
                self._attr_native_value = dataLeft
                self.tries = 0
                return
        else:
             _LOGGER.debug("Error. Code: " + str(resp.status_code))

        self.lastPoll = datetime.datetime.now()
        self.tries = 0

    def updateAuth(self) -> None:
        _LOGGER.debug("Updating authentication")
        self.session.post(self.AUTH_URL, data=self.CREDENTIALS)
