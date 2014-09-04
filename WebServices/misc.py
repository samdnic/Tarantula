from dateutil.parser import parse
import datetime
from calendar import timegm

def parse_time(s):
    try:
        ret = parse(s)
    except ValueError:
        ret = datetime.utcfromtimestamp(s)
    return ret

def get_timestamp(dt):
    return int(timegm(dt.timetuple()))

def parse_duration(data, units='seconds'):
    if units == 'seconds':
        return datetime.timedelta(seconds=int(data))
    elif units == 'minutes':
        return datetime.timedelta(minutes=int(data))
    elif units == 'hours':
        return datetime.timedelta(hours=int(data))
    elif units == 'days':
        return datetime.timedelta(days=int(data))
    elif units == 'weeks':
        return datetime.timedelta(weeks=int(data))
    else:
        raise ValueError('Unknown unit specifier "{0}"'.format(units))
    