import asyncio
import json
import logging
from copy import deepcopy
from datetime import datetime
from time import sleep, time
from typing import Dict, Literal, Optional

import clashroyale
import discord
from crtoolsdb.crtoolsdb import Constants
from discord.ext import tasks
from redbot.core import checks, commands
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core.data_manager import cog_data_path
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import humanize_list, pagify
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

log = logging.getLogger("red.cogs.clashroyaleclansv2")

default_sort = lambda x: (
                    x[1]["clan_war_trophies"],
                    x[1]["required_trophies"],
                    x[1]["clan_score"],
                )

class NoToken(Exception):
    pass


class ClashRoyaleClans2(commands.Cog):
    """
    Keep track of clashroyaleclans
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot

        crtools_cog = self.bot.get_cog("ClashRoyaleTools")
        self.tags = getattr(crtools_cog, "tags", None)
        self.constants = Constants()

        default_global = {
            "clans": dict(),
            "keep_memberlog": False,
            "dispatch_event": True,
        }
        self.config = Config.get_conf(
            self,
            identifier=2286464642345664457,
            force_registration=True,
        )
        self.config.register_global(**default_global)

        try:
            self.claninfo_path = str(cog_data_path(self) / "clans.json")
            with open(self.claninfo_path) as file:
                self.static_clandata = dict(json.load(file))
        except:
            self.static_clandata = {}

        self.claninfo_lock = asyncio.Lock()

        self.refresh_task = self.get_clandata.start()
        self.token_task = self.bot.loop.create_task(self.crtoken())
        self.clash = None
        self.last_updated = None
        self.last_updated_preety = None
        self.last_error_time = None
        self.loop_count = 0

    async def crtoken(self):
        # Initialize clashroyale API
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if not token or token.get("token") is None:
            log.error(
                "CR Token is not SET. "
                "Use [p]set api clashroyale token,YOUR_TOKEN to set it"
            )
            raise NoToken
        self.clash = clashroyale.official_api.Client(
            token=token["token"], is_async=True, url="https://proxy.royaleapi.dev/v1"
        )

    def cog_unload(self):
        if self.refresh_task:
            self.refresh_task.cancel()
        if self.token_task:
            self.token_task.cancel()
        if self.clash:
            self.bot.loop.create_task(self.clash.close())

    async def red_delete_data_for_user(
        self, *, requester: RequestType, user_id: int
    ) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    async def refresh_data(self):
        try:
            with open(self.claninfo_path) as file:
                self.static_clandata = dict(json.load(file))
            all_clan_data = dict()
            for name, data in self.static_clandata.items():
                try:
                    clan_tag = data["tag"]
                    clan_data = (await self.clash.get_clan(clan_tag)).to_dict()
                    all_clan_data[name] = clan_data
                # REMINDER: Order is important. RequestError is base exception class.
                except clashroyale.NotFoundError:
                    log.critical("Invalid clan tag.")
                    raise
                except clashroyale.RequestError:
                    log.error("Error: Cannot reach ClashRoyale Server.")
                    raise
            await self.config.clans.set(all_clan_data)
            # log.info("Updated data for all clans.")
        except Exception as e:
            log.error("Encountered exception {} when refreshing clan data.".format(e))
            raise

    @tasks.loop(seconds=30)
    async def get_clandata(self, sortBy=default_sort, reverse=True):
        """Check current data against data stored in config."""
        if self is not self.bot.get_cog("ClashRoyaleClans2"):
            return
        old_data = dict()
        dispatch_clandata_update = await self.config.dispatch_event()
        if dispatch_clandata_update:
            old_data = deepcopy(await self.config.clans())

        try:
            await self.refresh_data()
        except Exception as e:
            if self.last_error_time:
                if self.last_error_time - time.time() >= 300:
                    log.exception(f"Error {e} when updating data.", exc_info=e)
                    self.last_error_time = time.time()
            return

        new_data = deepcopy(await self.config.clans())
        type(new_data)
        new_data = {
            k: v
            for k, v in sorted(
                new_data.items(),
                key=sortBy,
                reverse=reverse,
            )
        }

        if len(new_data) == 0:
            log.error("Clans data is empty.")
            return
        if dispatch_clandata_update:
            self.bot.dispatch("clandata_update", old_data, new_data)

        await self.config.clans.set(new_data)
        self.last_error_time = None
        self.last_updated = datetime.now()
        self.last_updated_preety = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        self.loop_count += 1

    def get_static_clankey(self, clankey):
        for key, data in self.static_clandata.items():
            if (
                data["tag"].lower() == clankey.lower()
                or data["name"].lower() == clankey.lower()
                or data["nickname"].lower() == clankey.lower()
            ):
                return key
        return None

    def get_static_clandata(self, clankey: str, req_data: str = None):
        key = self.get_static_clankey(clankey)
        if key:
            if req_data:
                return self.static_clandata[key][req_data]
            else:
                return self.static_clandata[key]
        return None

    async def save_clan_data(self):
        async with self.claninfo_lock:
            with open(self.claninfo_path, "w") as file:
                json.dump(self.static_clandata, file, indent=4)

    async def all_clans_data(self, sortBy=None, reverse=True):
        """Return clan data"""
        clans_data = await self.config.clans()
        if sortBy is not None:
            clans_data = {
                k: v
                for k, v in sorted(
                    clans_data.items(),
                    key=sortBy,
                    reverse=reverse,
                )
            }
        return clans_data

    def get_all_static_clan_data(self):
        return self.static_clandata

    async def clan_data(self, clankey: str, req_data: str = None):
        """Return clan info stored in config"""
        all_clans = await self.config.clans()
        key = self.get_static_clankey(clankey)
        if key:
            if req_data:
                return all_clans[key][req_data]
            else:
                return all_clans[key]
        return None

    async def clan_member_data(
        self, clankey: str, memberkey: str, req_data: str = None
    ):
        """Return clan member's dict"""
        data = await self.clan_data(clankey, "member_list")
        for member in data:
            if member["tag"] == memberkey or member["name"] == memberkey:
                if req_data:
                    return member[req_data]
                else:
                    return member
        return None

    def num_clans(self):
        """Return the number of clans"""
        return len(self.static_clandata.keys())

    def keys(self):
        """Get keys of all the clans"""
        return self.static_clandata.keys()

    async def clan_members_tags(self, clankey):
        """Get keys of all the clan members"""
        data = await self.clan_data_by_key(clankey, "member_list")
        return [member["tag"] for member in data]

    def clan_names(self):
        """Get name of all the clans"""
        return [clan["name"] for clan in self.static_clandata.values()]

    def clan_tags(self):
        """Get tags of all the clans"""
        return [clan["tag"].strip("#") for clan in self.static_clandata.values()]

    def clan_roles(self):
        """Get roles of all the clans"""
        roles = ["Member"]
        roles.extend([clan["clanrole"] for clan in self.static_clandata.values()])
        return roles

    def verify_clan_membership(self, clantag):
        """Check if a clan is part of the family"""
        return any((data["tag"] == clantag for data in self.static_clandata.values()))

    def clan_key_from_tag(self, clantag):
        """Get a clan key from a clan tag."""
        for key, data in self.static_clandata.items():
            if data["tag"] == clantag:
                return key
        return None

    def waiting(self, clankey):
        data = self.get_static_clandata(clankey)
        return data["waiting"]

    def num_waiting(self, clankey):
        """Get a clan's wating list length from a clan key."""
        return len(self.waiting(clankey))

    async def clan_cwr(self, clankey, league):
        """Get a clan's CWR"""
        for name, data in self.static_clandata.items():
            if (
                data["tag"] == clankey
                or data["name"] == clankey
                or data["nickname"] == clankey
            ):
                return data["cwr"][league]
        return 0

    async def add_waiting_member(self, clankey, memberID):
        """Add a user to a clan's waiting list"""
        if memberID not in self.waiting(clankey):
            clankey = self.get_static_clankey(clankey)
            self.static_clandata[clankey]["waiting"].append(memberID)
            await self.save_clan_data()
            return True
        else:
            return False

    async def remove_waiting_member(self, clankey, memberID):
        """Remove a user to a clan's waiting list"""
        if memberID in self.waiting(clankey):
            clankey = self.get_static_clankey(clankey)
            self.static_clandata[clankey]["waiting"].remove(memberID)
            await self.save_clan_data()
            return True
        else:
            return False

    async def check_if_waiting(self, clankey, memberID):
        """check if a user is in a waiting list"""
        return memberID in self.waiting(clankey)

    async def delClan(self, clankey):
        """delete a clan from the family"""
        if self.static_clandata.pop(clankey, None):
            await self.save_clan_data()
            return True
        return False

    async def set_clan_pb(self, clankey, trophies):
        """Set a clan's PB Trohies"""
        clankey = self.get_static_clankey(clankey)
        self.static_clandata[clankey]["requirements"]["personalbest"] = trophies
        await self.save_clan_data()

    async def set_cwr(self, clankey, league, cwr):
        """Set a clan's CWR"""
        clankey = self.get_static_clankey(clankey)
        self.static_clandata[clankey]["requirements"]["cwr"][league] = cwr
        await self.save_clan_data()

    async def set_bonus(self, clankey, bonus):
        """Set a clan's Bonus Statement"""
        clankey = self.get_static_clankey(clankey)
        self.static_clandata[clankey]["requirements"]["bonustitle"] = bonus
        await self.save_clan_data()

    async def toggle_private(self, clankey):
        """Toggle Private approval of new recruits"""
        clankey = self.get_static_clankey(clankey)
        self.static_clandata[clankey]["requirements"][
            "approval"
        ] = not self.static_clandata[clankey]["requirements"]["approval"]
        await self.save_clan_data()
        return self.static_clandata[clankey]["requirements"]["approval"]

    async def set_log_channel(self, clankey, channel_id):
        """Toggle Private approval of new recruits"""
        clankey = self.get_static_clankey(clankey)
        self.static_clandata[clankey]["log_channel"] = channel_id
        await self.save_clan_data()

    @commands.command(name="clanaudit")
    async def clanaudit(self, ctx, nickname: str):
        async with ctx.channel.typing():
            clan_info = await self.clan_data(nickname)
            if clan_info is None:
                embed = discord.Embed(
                    title="Unknown nickname",
                    description="You entered a nickname not found found in clans.json",
                    color=0xFF0000,
                )
                await ctx.channel.send(embed=embed)
                return

            clan_role = self.get_static_clandata(nickname, "clanrole")
            # List of all clan member tags from ClashRoyalAPI
            clan_member_by_name_by_tags = await self.clan_members_by_tag(nickname)
            # Obtain all members with the clanrole
            role = discord.utils.get(ctx.guild.roles, name=clan_role)

            unknown_members = []  # People w/ role and no tags
            orphan_members = (
                []
            )  # People w/ role and have a tag and can't be found in the ClashRoyalAPI
            absent_names = []  # Tags (URLS?) of people who aren't in Discord
            processed_tags = []

            tags_by_member_id = self.tags.getTagsForUsers(
                [member.id for member in role.members]
            )

            # Send people with roles to either unknown_members or orphan_members if required
            async for member in AsyncIter(role.members):
                member_tags = tags_by_member_id.get(member.id, [])
                if len(member_tags) == 0:
                    unknown_members.append(f"{member.name}")
                found = False
                for tag in member_tags:
                    if tag in clan_member_by_name_by_tags.keys():
                        found = True
                        processed_tags.append(tag)
                if not found:
                    orphan_members.append(f"{member.name}")
            # Get people not in discord but are in clan
            absent_names = [
                f"{name} (#{tag})"
                for tag, name in clan_member_by_name_by_tags.items()
                if tag not in processed_tags
            ]

            if len(unknown_members) == 0:
                unknown_members_str = "None"
                unknown_count = 0
            else:
                unknown_members.sort(key=str.lower)
                unknown_members_str = "\n".join(unknown_members)
                unknown_count = len(unknown_members)

            if len(orphan_members) == 0:
                orphan_members_str = "None"
                orphan_count = 0
            else:
                orphan_members.sort(key=str.lower)
                orphan_members_str = "\n".join(orphan_members)
                orphan_count = len(orphan_members)

            if len(absent_names) == 0:
                absent_names_str = "None"
                absent_count = 0
            else:
                absent_names.sort(key=str.lower)
                absent_names_str = "\n".join(absent_names)
                absent_count = len(absent_names)

            embed = discord.Embed(
                title=f"Clan Audit: {clan_info['name']}", color=discord.Colour.blue()
            )

            embed.add_field(
                name=f"({unknown_count}) Players with **{clan_role}** role, but have **NO** tags saved",
                value=unknown_members_str,
                inline=False,
            )
            embed.add_field(
                name=f"({orphan_count}) Players with **{clan_role}** role, but have **NOT** joined the clan",
                value=orphan_members_str,
                inline=False,
            )

            pages = []
            absent_members_title = f"({absent_count}) Players in **{clan_info['name']}**, but have **NOT** joined discord"
            absent_members_value = "None"
            for index, page in enumerate(pagify(absent_names_str, page_length=1024)):
                if index == 0:
                    absent_members_value = page
                em = discord.Embed(title=absent_members_title, description=page)
                pages.append(em)
            embed.add_field(
                name=absent_members_title,
                value=absent_members_value,
                inline=False,
            )
            pages[0] = embed
            await menu(ctx, pages, controls=DEFAULT_CONTROLS)

    async def clan_members_by_tag(self, nickname: str) -> Dict[str, str]:
        members_names_by_tag = {}
        clan_data = await self.clan_data(nickname, "member_list")
        for member in clan_data:
            members_names_by_tag[member["tag"].strip("#")] = member["name"]
        return members_names_by_tag

    @commands.group(name="clans")
    @checks.admin()
    async def clans(self, ctx):
        """ Set requirements for clan """
        pass

    @clans.command(name="logchannel")
    async def clans_logchannel(
        self,
        ctx: commands.Context,
        clankey: str,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Set clan channel used to log changes to clan"""
        await self.set_log_channel(clankey, channel.id if channel else channel)
        await ctx.send(
            f"Set log channel for {clankey} to {channel.mention if channel else 'None'}"
        )
        await ctx.tick()

    @clans.command(name="cwr")
    async def clans_cwr(self, ctx, clankey, league, percent: int):
        """ Set cwr as requirement for clan """
        clan_name = self.get_static_clankey(clankey)
        if not clan_name:
            await ctx.send(f"{clankey} is not a valid clanname.")
            return
        try:
            await self.set_cwr(clankey, league, percent)
        except IndexError:
            await ctx.send(f"Cannot find league {league}")
            return
        await self.save_clan_data()
        await ctx.tick()

    @clans.command(name="pb")
    async def clans_pb(self, ctx, clankey, value: int):
        """ Set personal best as requirements"""
        clan_name = self.get_static_clankey(clankey)
        if not clan_name:
            await ctx.send(f"{clankey} is not a valid clanname.")
            return
        await self.set_clan_pb(clankey, value)
        await self.save_clan_data()
        await ctx.tick()

    @clans.command(name="bonus")
    async def clans_bonus(self, ctx, clankey, value: str):
        """ Set bonus requirements for clan. Note that these values must be checked manually by hub officers. """
        clan_name = self.get_static_clankey(clankey)
        if not clan_name:
            await ctx.send(f"{clankey} is not a valid clanname.")
            return
        await self.set_bonus(clankey, value)
        await ctx.tick()

    @clans.command(name="cwthreshold")
    async def clans_cwthreshold(self, ctx, clankey, value: int):
        """ Set fame threshold for clan """
        clan_name = self.get_static_clankey(clankey)
        if not clan_name:
            await ctx.send(f"{clankey} is not a valid clanname.")
            return
        self.static_clandata[clan_name]["cwthreshold"] = value
        await self.save_clan_data()
        await ctx.tick()

    @clans.command(name="wdwins")
    async def clans_wdwins(self, ctx, clankey, value: int):
        """ Set warday wins requirements for clan """
        clan_name = self.get_static_clankey(clankey)
        if not clan_name:
            await ctx.send(f"{clankey} is not a valid clanname.")
            return
        self.static_clandata[clan_name]["requirements"]["wdwins"] = value
        await self.save_clan_data()
        await ctx.tick()
