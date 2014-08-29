from dateutil.parser import parse
from datetime import datetime
from calendar import timegm

def parse_time(s):
    try:
        ret = parse(s)
    except ValueError:
        ret = datetime.utcfromtimestamp(s)
    return ret

def get_timestamp(dt):
    return int(timegm(dt.timetuple()))