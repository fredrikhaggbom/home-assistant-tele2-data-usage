import logging
from homeassistant import core
from homeassistant.core import Config, HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the Tele2 Data usage component."""
    # @TODO: Add setup code.
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up nordpool as config entry."""
    res = await _dry_setup(hass, entry.data)
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return res

async def _dry_setup(hass: HomeAssistant, _: Config) -> bool:
    """Set up using yaml config file."""
    return True

class Tele2Session:
    """Holds the data"""

    def __init__(self, hass: HomeAssistant):
        self._hass = hass
        self._last_tick = None
        self._data = defaultdict(dict)
        self.session = None

    async def _update(self, type_="today", dt=None):
        _LOGGER.debug("calling _update %s %s", type_, dt)
        hass = self._hass
        client = async_get_clientsession(hass)

        if dt is None:
            dt = dt_utils.now()

        # We dont really need today and morrow
        # when the region is in another timezone
        # as we request data for 3 days anyway.
        # Keeping this for now, but this should be changed.
        for currency in self.currency:
            spot = AioPrices(currency, client)
            data = await spot.hourly(end_date=dt)
            if data:
                self._data[currency][type_] = data["areas"]
