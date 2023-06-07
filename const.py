from enum import Enum

DOMAIN = "tele2_datausage"
DEFAULT_NAME = "Tele2 Data usage"
DEVICE_NAME = "Tele2"
ATTRIBUTE_UNLIMITED = "Unlimited"
POLL_INTERVAL = "poll_interval"


class SensorType(Enum):
    DATA = 1
    DATE = 2
    OTHER = 3