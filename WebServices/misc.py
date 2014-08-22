from dateutil.parser import parse
from datetime import datetime
from calendar import timegm

def enum(**enums):
    return type('Enum', (), enums)

def parse_time(s):
    try:
        ret = parse(s)
    except ValueError:
        ret = datetime.utcfromtimestamp(s)
    return ret

def get_timestamp(dt):
    return timegm(dt.timetuple())