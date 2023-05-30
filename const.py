from enum import Enum

DOMAIN = "tele2_datausage"
DEFAULT_NAME = "Tele2 Data usage"
DEVICE_NAME = "Tele2"
ATTRIBUTE_UNLIMITED = "Unlimited"
POLL_INTERVAL = "poll_interval"

RES_LIMIT = "packageLimit"
RES_USAGE = "usage"
RES_UNLIMITED = "hasUnlimitedData"
RES_DATA_LEFT = "dataLeft"
RES_DATA_TOTAL = "dataTotal"
RES_PERIOD_START = "periodStart"
RES_PERIOD_END = "periodEnd"

class Tele2ApiResult:
    unlimitedData = "hasUnlimitedData"
    startDate = "startDate"
    endDate = "endDate"
    remaining = "remaining"
    packageLimit = "packageLimit"
    buckets = "buckets"


class SensorType(Enum):
    DATA = 1
    DATE = 2
    OTHER = 3