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
from .embeds import events as embed_events, created_event as embed_event_created, removed_event as embed_removed_event, show_events as embed_show_events, compare as embed_compare, iso as embed_iso, me as embed_me, generic_embeds as embed_generic
from .utils import format_time_delta

async def user_time(user, config):
    """Returns the timezone of the given user, if it was set."""
    if not user:
        raise KeyError("You must give a valid user!")
    else:
        usertime = await config.user(user).usertime()
        if usertime:
            time = datetime.now(timezone(usertime))
            fmt = "**%H:%M** %d-%B-%Y **%Z (UTC %z)**"
            time_str = time.strftime(fmt)
            return (usertime, time, time_str)
        else:
            raise RuntimeError("That user hasn't set their timezone.")

def get_time_data(tz, timestamp: Optional[str] = None):
    """Given a Timezone, returns a tuple (tz, time, fmt) on success.
    Usage: get_time_data(<timezone>, [timestamp]). If you give a timestamp
    (e.g. 2020-05-06-13:33) it will set the time to that value, instead of now.
    """
    if not tz:
        if not timestamp:
            now = datetime.utcfromtimestamp(time.time()).replace(tzinfo=pytz.utc).astimezone(get_localzone())
        else:
            now = get_localzone().localize( parse(timestamp) )
        fmt = "**%H:%M** %d-%B-%Y"
        return (get_localzone(), now, fmt)
    if "'" in tz:
        tz = tz.replace("'", "")
    if len(tz) > 4 and "/" not in tz:
        raise ValueError("""
Error: Incorrect format. Use:
**Continent/City** with correct capitals.  e.g. `America/New_York`
See the full list of supported timezones here:
<https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>""")
    tz = tz.title() if '/' in tz else tz.upper()
    if tz not in common_timezones:
        raise KeyError(tz)
    fmt = "**%H:%M** %d-%B-%Y **%Z (UTC %z)**"
    if timestamp:
        now = pytz.timezone(tz).localize( parse(timestamp) )
    else:
        now = datetime.now(timezone(tz))
    return (timezone(tz), now, fmt)

class Timezone(commands.Cog):
    """Gets times across the world..."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 278049241001, force_registration=True)
        default_user = {"usertime": None}
        self.config.register_user(**default_user)

        """Format:  'events' : { 'id':[name, (event_tz, event_time, event_fmt)] }"""
        default_guild = {
            'events': {}
        }
        self.config.register_guild(**default_guild)

    @commands.guild_only()
    @commands.group()
    async def time(self, ctx):
        """
            Checks the time.

            For the list of supported timezones, see here:
            https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        """
        pass

    @time.command()
    async def tz(self, ctx, *, tz: Optional[str] = None):
        """Gets the time in any timezone."""
        try:
            tz, time, fmt = get_time_data(tz)
            await embed_generic(ctx, field="TZ", value=time.strftime(fmt))
        except ValueError as e:
            await embed_generic(ctx, field="**ERROR**:", value=f"{str(e)}")
        except KeyError as e:
            await embed_generic(ctx, field="**ERROR**:", value=f"{str(e)} is an unsupported timezone.")

    @time.command()
    async def iso(self, ctx, *, code=None):
        """Looks up ISO3166 country codes and gives you a supported timezone."""
        if code is None:
            await embed_generic(ctx, field="**ERROR**:", value=f"{code} doesn't look like a country code!")
        else:
            await embed_iso(ctx, code, country_timezones(code) if code in country_timezones else None)

    @time.command()
    async def me(self, ctx, *, tz=None):
        """
            Sets your timezone.
            Usage: [p]time me Continent/City
        """
        if tz is None:
            usertime = await self.config.user(ctx.message.author).usertime()
            time = None
            if usertime:
                time = datetime.now(timezone(usertime)).strftime("**%H:%M** %d-%B-%Y **%Z (UTC %z)**")
            await embed_me(ctx, usertime, time)
        else:
            exist = True if tz.title() in common_timezones else False
            if exist:
                if "'" in tz:
                    tz = tz.replace("'", "")
                await self.config.user(ctx.message.author).usertime.set(tz.title())
                await embed_generic(ctx, field="Timezone", value=f"Successfully set your timezone to **{tz.title()}**.")
            else:
                await embed_generic(ctx, field="Timezone : **ERROR**:", value=f"Unrecognized timezone. Try `{ctx.prefix}time me Continent/City`\n"
                    "see [Timezones](<https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>)")

    @time.command()
    async def tell(self, ctx, tz_to = None, tz_from: Optional[str] = None, *, timestamp: Optional[str] = None):
        """Tells you what the time will be in the given timezone.
           If you don't give a origin TZ, it expects to use one that was saved by the 'me' command.
           Timezone to convert to is mandatory.
           All timezones need to be in the timezone format as returned by the 'iso' command.
            Arguments: <timezone_TO> [timezone_FROM] [time]
            Usage: [p]time tell <Continent/City> [Continent/City] [time]
            Example: [p]time tell America/New_York Asia/Kolkata '2020-05-06-23:59'"""
        try:
            if not tz_to:
                return await ctx.send_help()
                #return await embed_generic(ctx, field="timezone_TO", value="Field timezone_to is not set. You must provide a valid time_zone to convert your time to in the format <Continent/City>\n(e.g. America/New_York, or Asia/Kolkata, or Asia/Singapore, or Europe/Paris, etc)!")
            tz_from, now_from, fmt_from = get_time_data(tz_from, timestamp)
            tz_to, now_to, fmt_to = get_time_data(tz_to)
            await embed_generic(ctx, field="TELL", value=now_from.astimezone(tz_to).strftime(fmt_to))
        except ValueError as e:
            await embed_generic(ctx, field="**ERROR**:", value=f"{str(e)}")
        except KeyError as e:
            await embed_generic(ctx, field="**ERROR**:", value=f"{str(e)} is an unsupported timezone.")

    @time.command()
    async def events(self, ctx, name=None):
        """Lists all registered events.
        Usage: [p]time events [name] : Returns how long for event to start, and what time it will be in your timezone
        """
        # First see if we can get the user's timezone
        try:
            usertime, time, time_str = await user_time(ctx.message.author, self.config)
        except RuntimeError as e:
            return await embed_generic(ctx, field="**ERROR**:", value=f"{str(e)}.")
        except KeyError as e:
            return await embed_generic(ctx, field="**ERROR**:", value=f"{str(e)}.")

        # now go through events
        event_list = []
        events = await self.config.guild(ctx.guild).events.get_raw()
        # now go through all events and tell the user how long for the event to start, and what time it will be for him
        for id, event in events.items():
            # events[event_id] = {'event': event, 'when': event_time.astimezone(pytz.utc).isoformat(), 'tz':str(event_tz)}
            # to convert back from UTC string: dateutils.parse(events['when']).astimezone(timezone(events[event_id]['tz']))
            event_name = event['event'].lower()
            if not name or name in event_name:
                event_tz = event['tz']
                event_time = parse(event['when']).astimezone(timezone(event_tz))
                user_event_time = parse(event['when']).astimezone(timezone(usertime))
                user_now = datetime.now(timezone(usertime))
                fmt = "**%H:%M** %d-%B-%Y **%Z (UTC %z)**"
                time_delta = event_time - user_now
                event_list.append((event_name, user_event_time.strftime(fmt), format_time_delta(time_delta), time_delta))
        event_list.sort(key=lambda x: x[3], reverse=True)
        await embed_events(ctx, event_list)

    @time.command()
    async def show_events(self, ctx, event=None, when=None, tz: Optional[str]=None):
        """Lists all registered events."""
        # First see if we can get the user's timezone
        try:
            usertime, time, time_str = await user_time(ctx.message.author, self.config)
        except RuntimeError as e:
            return await embed_generic(ctx, field="**ERROR**:", value=f"{str(e)}")
        except KeyError as e:
            return await embed_generic(ctx, field="**ERROR**:", value=f"{str(e)}")

        # now go through events
        event_list = []
        events = await self.config.guild(ctx.guild).events.get_raw()
        for id, event in events.items():
            # events[event_id] = {'event': event, 'when': event_time.astimezone(pytz.utc).isoformat(), 'tz':str(event_tz)}
            # to convert back from UTC string: dateutils.parse(events['when']).astimezone(timezone(events[event_id]['tz']))
            event_name = event['event']
            event_tz = event['tz']
            event_time = parse(event['when']).astimezone(timezone(event_tz))
            user_now = datetime.now(timezone(usertime))
            time_delta = event_time - user_now
            fmt = "**%H:%M** %d-%B-%Y **%Z (UTC %z)**"
            if time_delta.total_seconds() < 0:
                fmt += " **! EVENT IS OVER !**"
            event_list.append((id, event_name, event_time.strftime(fmt), event_tz, time_delta))
        if not event_list:
            event_list.append((0, " ** NO EVENTS ** ", "", "", 0))
        event_list.sort(key=lambda x: x[4], reverse=True)
        await embed_show_events(ctx, event_list)

    @time.command()
    async def create_event(self, ctx, event=None, when=None, tz: Optional[str]=None):
        """
            Creates an event in your timezone, or in a given timezone.
            Usage: [p]time create_event <name> <date/time> [Continent/City]
            Example: [p]time create_event "June Tournament" 2020-06-01-14:00
                    (will use the local timezone of the server)
            Example: [p]time create_event "June Tournament" 2020-06-01-14:00 America/New_York
                    (will force the event timezone to be EST)
        """
        if not event:
            return await ctx.send_help()
            #return await embed_generic(ctx, field="**ERROR**:", value='You must set an event name (between double quotes "event name" preferably).')
        if not when:
            return await ctx.send_help()
            #return await embed_generic(ctx, field="**ERROR**:", value='You must set an event date/time (between double quotes "YYYY-MM-DD-HH:MM:SS" preferably).')
        try:
            event_tz, event_time, event_fmt = get_time_data(tz, when)
        except KeyError as e:
            return await embed_generic(ctx, field="**ERROR**:", value=f"{str(e)} is an unsupported timezone.")
        events = await self.config.guild(ctx.guild).events.get_raw()
        last_id = sorted(events.keys())
        event_id = 1
        if last_id:
            event_id = int(last_id[-1]) + 1
        # datetime is not JSON serializable, so we need to store the isoformat representation
        events[event_id] = {'event': event, 'when': event_time.astimezone(pytz.utc).isoformat(), 'tz':str(event_tz)}
        # to convert back from UTC string: dateutils.parse(events['when']).astimezone(timezone(events[event_id]['tz']))
        await self.config.guild(ctx.guild).events.set(events)
        await embed_event_created(ctx, event, event_id, event_time.strftime(event_fmt))

    @time.command()
    async def remove_event(self, ctx, event_id):
        """Erases an event if the given ID is found."""
        try:
            events = await self.config.guild(ctx.guild).events.get_raw()
            if event_id not in events.keys():
                raise KeyError(event_id)
            await embed_removed_event(ctx, event_id, events[event_id])
            events.__delitem__(event_id)
            await self.config.guild(ctx.guild).events.set(events)
        except KeyError as e:
            await embed_generic(ctx, field="**ERROR**:", value=f"**Error:** Event ID {str(e)} does not exist. Use '{ctx.prefix}time event_print' to see all registered events.")

    @time.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def set(self, ctx, user: discord.Member, *, tz=None):
        """Allows the mods to edit timezones."""
        if not user:
            user = ctx.message.author
        if tz is None:
            return await embed_generic(ctx, field="**ERROR**:", value="That timezone is invalid.")
        else:
            exist = True if tz.title() in common_timezones else False
            if exist:
                if "'" in tz:
                    tz = tz.replace("'", "")
                await self.config.user(user).usertime.set(tz.title())
                await embed_generic(ctx, field="**ERROR**:", value=f"Successfully set {user.name}'s timezone to **{tz.title()}**.")
            else:
                await embed_generic(ctx, field="**ERROR**:", value=f"Unrecognized timezone. Try `{ctx.prefix}time set @user Continent/City`\n"
                    "see [Timezones](<https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>)")

    @time.command()
    async def user(self, ctx, user: discord.Member = None):
        """Shows the current time for user."""
        try:
            usertime, time, time_str = await user_time(user, self.config)
            await embed_generic(ctx, field='User', value=f"{user.name}'s current timezone is: **{usertime}**\n"
                           f"The current time is: {str(time_str)}")
        except RuntimeError as e:
            await embed_generic(ctx, field="**ERROR**:", value=f"{str(e)}")
        except KeyError as e:
            await embed_generic(ctx, field="**ERROR**:", value=f"{str(e)}")

    @time.command()
    async def compare(self, ctx, user: discord.Member = None):
        """Compare your saved timezone with another user's timezone."""
        if not user:
            return await ctx.send_help()

        usertime = await self.config.user(ctx.message.author).usertime()
        othertime = await self.config.user(user).usertime()

        if not usertime:
            return await embed_generic(ctx, title='', value=f"You haven't set your timezone. Do `{ctx.prefix}time me Continent/City`\n"
                "see [Timezones](<https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>)")
        if not othertime:
            await embed_generic(ctx, field="**ERROR**:", value=f"That user's timezone isn't set yet.")

        user_now = datetime.now(timezone(usertime))
        user_diff = user_now.utcoffset().total_seconds() / 60 / 60
        other_now = datetime.now(timezone(othertime))
        other_diff = other_now.utcoffset().total_seconds() / 60 / 60
        time_diff = int(abs(user_diff - other_diff))
        fmt = "**%H:%M %Z (UTC %z)**"
        other_time = other_now.strftime(fmt)
        plural = "" if time_diff == 1 else "s"
        time_amt = "the same time zone as you" if time_diff == 0 else f"{time_diff} hour{plural}"
        position = "ahead of" if user_diff < other_diff else "behind"
        position_text = "" if time_diff == 0 else f" {position} you"

        await embed_compare(ctx, user.display_name, other_time, time_amt, position_text)

