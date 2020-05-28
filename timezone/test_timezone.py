#!/usr/bin/env python3.8
"""Timezone bot for Legends discord bot."""
from datetime import datetime
from dateutil.parser import parse # pip install python-dateutil
from tzlocal import get_localzone # pip install tzlocal
from time import tzname
from typing import Optional
from pytz import common_timezones
from pytz import country_timezones
from pytz import timezone
import pytz
import time
import discord
from redbot.core import Config, commands, checks

def get_time_data(tz, timestamp: Optional[str] = None):
    """Returns a tuple (tz, time, fmt) on success."""
    if not tz:
        now = datetime.utcfromtimestamp(time.time()).replace(tzinfo=pytz.utc).astimezone(get_localzone())
        fmt = "Current system time: **%H:%M** %d-%B-%Y"
        return (get_localzone(), now, fmt)
    if "'" in tz:
        tz = tz.replace("'", "")
    if len(tz) > 4 and "/" not in tz:
        raise ValueError("""
Error: Incorrect format. Use:
**Continent/City** with correct capitals.  e.g. `America/New_York`
See the full list of supported timezones here:
<https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>""")
    """
    datetime.utcfromtimestamp(time.time()).replace(tzinfo=pytz.utc).astimezone(timezone('Asia/Kolkata'))
    parse('15:16').replace(tzinfo=get_localzone()).astimezone(timezone('Asia/Kolkata')).strftime('%H:%M')
    """
    tz = tz.title() if '/' in tz else tz.upper()
    if tz not in common_timezones:
        raise KeyError(tz)
    fmt = "**%H:%M** %d-%B-%Y **%Z (UTC %z)**"
    if timestamp:
        now = pytz.timezone(tz).localize( parse(timestamp) )
    else:
        now = datetime.now(timezone(tz))
    return (timezone(tz), now, fmt)

def tell(tz_to = None, tz_from: Optional[str] = None, timestamp: Optional[str] = None):
    try:
        if not tz_to:
            print("timezone_TO timezone is not set. You must provide a valid time_zone to convert your time to in the format <Continent/City> (e.g. America/New_York, or Asia/Kolkata, or Asia/Singapore, or Europe/Paris, etc)!")
            return
        tz_from, now_from, fmt_from = get_time_data(tz_from, timestamp)
        tz_to, now_to, fmt_to = get_time_data(tz_to)
        print(now_from.astimezone(tz_to).strftime(fmt_to))
    except ValueError as e:
        print(str(e))
    except KeyError as e:
        print(f"**Error:** {str(e)} is an unsupported timezone.")

if __name__ == '__main__':
    tell(tz_to='Australia/Brisbane', tz_from='America/New_York', timestamp='2020-05-07 12:35')
    #tell(tz_to='Asia/Singapore', tz_from='America/New_York', timestamp='2020-05-06 23:59')
    # tell(tz_to='America/New_York')
    # tell(tz_to='Europe/Paris')
    # tell(tz_to='Europe/Paris', tz_from='Asia/Kolkata', timestamp='2020-05-07 00:55')
    # tell(tz_to='Europe/Paris', tz_from='Australia/Brisbane', timestamp='2020-05-07 05:45')
    # tell(tz_to='Asia/Kolkata')
    # tell(tz_to='Asia/Kolkata', tz_from='America/New_York')
    # tell(tz_to='Asia/Kolkata', tz_from='Europe/Paris')
    # tell(tz_to='Asia/Kolkata', tz_from='Europe/Paris', timestamp='2020-05-06 21:00')
    # tell(tz_to='Asia/Kolkata', timestamp='00:00')
    # tell(tz_to='Asia/Kolkata', timestamp='13:25')
    # tell(tz_to='Asia/Kolkata', timestamp='14:25')
    # tell(tz_to='Asia/Kolkata', timestamp='15:25')
    # tell(tz_to='Asia/Kolkata', timestamp='16:25')
    # tell(tz_to='Asia/Singapore')
    # tell(tz_to='Asia/Singapore', tz_from='America/New_York')
    # tell(tz_to='Asia/Singapore', tz_from='America/New_York', timestamp='00:00')
