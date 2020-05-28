"""Embeds for Timezone Legends discord bot."""
import time
import discord
from dateutil.parser import parse # pip install python-dateutil
from pytz import timezone
from datetime import datetime

class Timezone_Embeds:
    def __init__(self, description=None, color=0x5c0708, show_footer=True, show_timestamp=True, show_thumbnail=True):
        if not show_timestamp:
            self.embed = discord.Embed(colour=discord.Colour(color))
        else:
            if not description:
                self.embed = discord.Embed(colour=discord.Colour(color),
                                           timestamp=datetime.utcfromtimestamp(time.time()))
            else:
                self.embed = discord.Embed(colour=discord.Colour(color),
                                           description=description,
                                           timestamp=datetime.utcfromtimestamp(time.time()))
        if show_thumbnail:
            #self.embed.set_thumbnail(url="https://cdn.iconscout.com/icon/premium/png-256-thumb/global-time-zone-1480117-1253197.png")
            #self.embed.set_thumbnail(url="https://tuccitime.com/modules/xipblog/img/large-time.jpg")
            self.embed.set_thumbnail(url="https://cdn.clipart.email/1cb9490f73d090921ded3aa2b1c2bf1f_different-time-zone-no-problem_513-510.png")

        if show_footer:
            self.embed.set_footer(text="Bot by Vanhorn | Academy",
                                  icon_url="https://vignette.wikia.nocookie.net/clashroyale/images/4/42/GraveyardCard.png/revision/latest/top-crop/width/360/height/450?cb=20171212204803")
        
    def set_title(self, name, icon_url):
        self.embed.set_author(name=name,
                              url="https://discordapp.com/channels/374596069989810176/374597178989215757",
                              icon_url=icon_url)

async def events(ctx, event_list):
    tze = Timezone_Embeds(description="Listing all Events that matched your request (**if any**)")
    tze.set_title("Events", "https://www.kindpng.com/picc/m/246-2465899_upcoming-events-icon-calendar-icon-png-transparent-png.png")
    for event_name, event_time, time_to_event, time_delta in event_list:
        tze.embed.add_field(name="Event", value=f"**{event_name}**", inline=True)
        tze.embed.add_field(name="Local Time", value=f"{event_time}", inline=True)
        tze.embed.add_field(name="Time Left", value=f"**{time_to_event}**", inline=True)
    await ctx.send(embed=tze.embed)

async def created_event(ctx, event, event_id, event_time):
    tze = Timezone_Embeds(show_thumbnail=False)
    tze.set_title("Event Created", "https://cdn2.vectorstock.com/i/1000x1000/70/11/event-schedule-icon-vector-26627011.jpg")
    tze.embed.add_field(name="Name", value=f"**{event}**", inline=True)
    tze.embed.add_field(name="ID", value=f"**{event_id}**", inline=True)
    tze.embed.add_field(name="When", value=f"{event_time}", inline=True)
    await ctx.send(embed=tze.embed)

async def removed_event(ctx, event_id, event):
    """
    {'event': 'Test Event', 'when': '2020-05-07T15:46:17.156085+00:00', 'tz': 'America/New_York'}
    """
    tze = Timezone_Embeds(show_thumbnail=False)
    tze.set_title("Event Removed", "https://cdn2.vectorstock.com/i/1000x1000/70/11/event-schedule-icon-vector-26627011.jpg")
    event_name = event['event']
    event_tz = event['tz']
    fmt = "**%H:%M** %d-%B-%Y **%Z (UTC %z)**"
    event_time = parse(event['when']).astimezone(timezone(event_tz)).strftime(fmt)
    tze.embed.add_field(name="Name", value=f"**{event_name}**", inline=True)
    tze.embed.add_field(name="ID", value=f"**{event_id}**", inline=True)
    tze.embed.add_field(name="When", value=f"{event_time}", inline=True)
    tze.embed.add_field(name="TZ", value=f"{event_tz}", inline=True)
    await ctx.send(embed=tze.embed)

async def show_events(ctx, event_list):
    for idx in range(0, len(event_list)):
        event_id, event_name, event_time, event_tz, time_delta = event_list[idx]
        tze = Timezone_Embeds(show_footer=True if idx == len(event_list)-1 else False,
                              show_timestamp=True if idx == 0 else False,
                              show_thumbnail=True if idx == 0 else False)
        tze.set_title(f"Event ({event_id})",
                      "https://images.squarespace-cdn.com/content/v1/5a5ced468a02c79bfe4829bf/1516978000404-CVQ1CO95BEFJ7W2FTGDM/ke17ZwdGBToddI8pDm48kBPauUSMbKdP-TlqMma_x0ZZw-zPPgdn4jUwVcJE1ZvWEtT5uBSRWt4vQZAgTJucoTqqXjS3CfNDSuuf31e0tVFzDLvN5UbLOifpAePtRMTrCg1jr8OpcUFdGiHX6l_hRjFvbuqF0GUInBxxtVhBOn4/events-icon-website-gray.png")
        tze.embed.add_field(name="Name", value=f"**{event_name}**", inline=True)
        tze.embed.add_field(name="When", value=f"{event_time}", inline=True)
        tze.embed.add_field(name="TZ", value=f"**{event_tz}**", inline=True)
        await ctx.send(embed=tze.embed)


async def compare(ctx, display_name, other_time, time_amt, position_text):
    tze = Timezone_Embeds()
    tze.set_title("User TZ Compare", "https://cdn3.iconfinder.com/data/icons/calendar-23/100/Calendar-15-512.png")
    tze.embed.add_field(name=f"{display_name}'s time", value=f"**{other_time}**", inline=True)
    tze.embed.add_field(name="Which is", value=f"**{time_amt}{position_text}**", inline=True)
    await ctx.send(embed=tze.embed)


async def iso(ctx, code=None, tz=None):
    tze = Timezone_Embeds()
    tze.set_title("ISO", "https://images.assetsdelivery.com/compings_v2/aalbedouin/aalbedouin1808/aalbedouin180806226.jpg")
    if not code or not tz:
        tze.embed.add_field(name=f"**{code}** is invalid. For a full list, see here:", value="[Timezone Link](<https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes>)", inline=False)
    else:
        timezones = '\n'.join(tz)
        tze.embed.add_field(name=f"Supported timezones for **{code}**:", value=f"**{timezones}**", inline=False)
        tze.embed.add_field(name="**NOTE**", value=f"\n**Use** `{ctx.prefix}time tz Continent/City` **to display the current time in that timezone.**", inline=False)
    await ctx.send(embed=tze.embed)

async def me(ctx, usertime, time=None):
    tze = Timezone_Embeds()
    if usertime and time:
        tze.embed.add_field(name=f"Your current timezone is:", value=f"**{usertime}.\nThe current time is: {time}", inline=False)
    else:
        tze.embed.add_field(name=f"You haven't set your timezone yet...",
                            value=f"Do `{ctx.prefix}time me Continent/City`\nsee [Timezones](<https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>)")
    await ctx.send(embed=tze.embed)

async def generic_embeds(ctx, field, value, description=None):
    tze = Timezone_Embeds(description)
    tze.embed.add_field(name=field, value=value)
    await ctx.send(embed=tze.embed)

"""
embed = discord.Embed(colour=discord.Colour(0x5c0708), description="Listing all Events that matched your request (**if any**)", timestamp=datetime.utcfromtimestamp(time.time()))

embed.set_author(name="Events",
                 url="https://discordapp.com/channels/374596069989810176/374597178989215757",
                 icon_url="https://www.kindpng.com/picc/m/246-2465899_upcoming-events-icon-calendar-icon-png-transparent-png.png")
embed.set_thumbnail(url="https://cdn.iconscout.com/icon/premium/png-256-thumb/global-time-zone-1480117-1253197.png")
embed.set_footer(text="Bot by Vanhorn | Academy",
                 icon_url="https://vignette.wikia.nocookie.net/clashroyale/images/4/42/GraveyardCard.png/revision/latest/top-crop/width/360/height/450?cb=20171212204803")

for event_name, event_time, time_to_event in event_list:
    embed.add_field(name="Event", value=f"**{event_name}**", inline=True)
    embed.add_field(name="Local Time", value=f"**{event_time}**", inline=True)
    embed.add_field(name="Time Left", value=f"**{time_to_event}**", inline=True)

#print(embed.to_dict())
await ctx.send(embed=embed)
"""


"""
[x] create_event Creates an event in your timezone, or in a given t...
[x] events Lists all registered events.
[x] show_events Lists all registered events.
[x] remove_event Erases an event if the given ID is found.
[x] compare Compare your saved timezone with another user's timezone.
[x] iso Looks up ISO3166 country codes and gives you a supported ti...
[x] me Sets your timezone.
[x] set Allows the mods to edit timezones.
[x] tell Tells you what the time will be in the given timezone.
[x] tz Gets the time in any timezone.
[x] user Shows the current time for user.
"""
