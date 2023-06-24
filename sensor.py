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
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
)

from pytele2api.const import (
    RES_DATA_LEFT,
    RES_UNLIMITED,
    RES_LIMIT,
    RES_PERIOD_START,
    RES_PERIOD_END,
    CONF_SUBSCRIPTION,
    CONF_SUBSCRIPTIONMODEL,
    RES_USAGE,
    RES_ERROR,
)

from .const import (
    DOMAIN,
    POLL_INTERVAL,
    DEVICE_NAME,
    SensorType,
)
from . import Tele2Manager

from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default="Tele2 Data"): cv.string,
        vol.Optional(POLL_INTERVAL, default=1800): cv.positive_int,
        vol.Required(CONF_USERNAME, default=""): cv.string,
        vol.Required(CONF_PASSWORD, default=""): cv.string,
    }
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Setup sensor platform for the ui"""
    config = config_entry.data
    _LOGGER.debug("Add entities in async_setup_entry")
    await _dry_setup(hass, config, async_add_entities)
    return True


async def _dry_setup(hass, config, add_entities, discovery_info=None):
    """Setup the damn platform using yaml."""
    _LOGGER.debug("In dry_setup")
    _LOGGER.debug("Config: %s", config)
    api = Tele2Manager(hass, config)
    await api._update()

    dataLeftSensor = Tele2Sensor(
        hass, api, SensorType.DATA, "Tele2 Data Left", "tele2.dataleft", RES_DATA_LEFT
    )
    usageSensor = Tele2Sensor(
        hass, api, SensorType.DATA, "Tele2 Data Used", "tele2.datausage", RES_USAGE
    )
    dataTotal = Tele2Sensor(
        hass, api, SensorType.DATA, "Tele2 Data Total", "tele2.datatotal", RES_LIMIT
    )
    dataPeriodStart = Tele2Sensor(
        hass,
        api,
        SensorType.DATE,
        "Tele2 Data Period Start",
        "tele2.dataperiodstart",
        RES_PERIOD_START,
    )
    dataPeriodEnd = Tele2Sensor(
        hass,
        api,
        SensorType.DATE,
        "Tele2 Data Period End",
        "tele2.dataperiodend",
        RES_PERIOD_END,
    )
    unlimitedSensor = Tele2BinaryDataSensor(
        hass, api, "Tele2 Unlimited Data", "tele2.unlimiteddata", RES_UNLIMITED
    )

    add_entities(
        [
            dataLeftSensor,
            usageSensor,
            dataTotal,
            dataPeriodStart,
            dataPeriodEnd,
            unlimitedSensor,
        ]
    )

    if DOMAIN in hass.data:
        _LOGGER.debug("data from hass: %s", hass.data[DOMAIN])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    _LOGGER.debug("Add entities in async_setup_platform")
    api = Tele2Manager(hass, config)
    await api._update()
    dataLeftSensor = Tele2Sensor(
        hass, api, SensorType.DATA, "Tele2 Data Left", "tele2.dataleft", RES_DATA_LEFT
    )
    usageSensor = Tele2Sensor(
        hass, api, SensorType.DATA, "Tele2 Data Used", "tele2.datausage", RES_USAGE
    )
    dataTotal = Tele2Sensor(
        hass, api, SensorType.DATA, "Tele2 Data Total", "tele2.datatotal", RES_LIMIT
    )

    dataPeriodStart = Tele2Sensor(
        hass,
        api,
        SensorType.DATE,
        "Tele2 Data Period Start",
        "tele2.dataperiodstart",
        RES_PERIOD_START,
    )
    dataPeriodEnd = Tele2Sensor(
        hass,
        api,
        SensorType.DATE,
        "Tele2 Data Period End",
        "tele2.dataperiodend",
        RES_PERIOD_END,
    )

    unlimitedSensor = Tele2BinaryDataSensor(
        hass, api, "Tele2 Unlimited Data", "tele2.unlimiteddata", RES_UNLIMITED
    )
    add_entities(
        [
            dataLeftSensor,
            usageSensor,
            dataTotal,
            dataPeriodStart,
            dataPeriodEnd,
            unlimitedSensor,
        ],
        True,
    )
    return True


class Tele2Sensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self,
        hass,
        tele2Session: Tele2Manager,
        sensorType: SensorType,
        sensorName,
        identifier,
        updateField,
    ) -> None:
        super().__init__()
        self._hass = hass
        self._tele2Session = tele2Session
        self._name = sensorName
        self._identifier = identifier
        self._updateField = updateField
        self._attr_name = self._tele2Session.config[CONF_NAME]
        self._attr_native_value = None

        if sensorType == SensorType.DATA:
            self._attr_device_class = SensorDeviceClass.DATA_SIZE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES
            if self._updateField in self._tele2Session._data:
                self._attr_native_value = self._tele2Session._data[self._updateField]
            self._attr_suggested_display_precision = None
            self._attr_suggested_unit_of_measurement = "GB"
        elif sensorType == SensorType.DATE:
            self._attr_native_value = datetime.date.min
            self._attr_device_class = SensorDeviceClass.DATE
        else:
            self._attr_native_value = None

        _LOGGER.debug(
            "setting data left sensor up with user %s",
            self._tele2Session.config[CONF_USERNAME],
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._identifier + "." + self._tele2Session.config[CONF_SUBSCRIPTION]

    """ @property
    def extra_state_attributes(self):
        return self._attributes """

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._tele2Session.config[CONF_SUBSCRIPTION])},
            "name": self._tele2Session.config[CONF_NAME],
            "manufacturer": DEVICE_NAME,
            "model": self._tele2Session.config[CONF_SUBSCRIPTIONMODEL],
        }

    async def async_will_remove_from_hass(self):
        return

    async def async_update(self) -> None:
        """Manual updates of the sensor."""
        if not self._tele2Session.isUpdating:
            self.hass.async_create_task(self._tele2Session._update())
        newValue = self._tele2Session._data[self._updateField]
        if newValue != self._attr_native_value and newValue is not None:
            self._attr_native_value = newValue


class Tele2BinaryDataSensor(BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self, hass, tele2Session: Tele2Manager, sensorName, identifier, updateField
    ) -> None:
        super().__init__()
        self._hass = hass
        self._tele2Session = tele2Session
        self._updateField = updateField
        self._name = sensorName
        self._identifier = identifier
        self._attr_name = self._tele2Session.config[CONF_NAME]
        self._attr_is_on = False
        _LOGGER.debug(
            "setting data left sensor up with user %s",
            self._tele2Session.config[CONF_USERNAME],
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._identifier + "." + self._tele2Session.config[CONF_SUBSCRIPTION]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._tele2Session.config[CONF_SUBSCRIPTION])},
            "name": self._tele2Session.config[CONF_NAME],
            "manufacturer": DEVICE_NAME,
            "model": self._tele2Session.config[CONF_SUBSCRIPTIONMODEL],
        }

    @property
    def state(self):
        _LOGGER.debug("Return from state")
        return self._attr_is_on

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        _LOGGER.debug("Return from is_on")
        return self._attr_is_on

    async def async_will_remove_from_hass(self):
        return

    async def async_update(self) -> None:
        """Manual updates of the sensor."""
        _LOGGER.debug(
            "Will update unlimited binary sensor data (async) from previous call"
        )
        newValue = self._tele2Session._data[self._updateField]
        if newValue != self._attr_is_on and newValue is not None:
            self._attr_is_on = newValue
