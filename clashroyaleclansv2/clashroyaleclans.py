import asyncio
import json
import logging
from copy import deepcopy
from datetime import datetime
from time import sleep, time
from typing import Literal

import clashroyale
import discord
from crtoolsdb.crtoolsdb import Constants
from discord.ext import tasks
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core.data_manager import cog_data_path

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

log = logging.getLogger("red.cogs.clashroyaleclans")


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
        }
        self.config = Config.get_conf(
            self, identifier=2286464642345664457, force_registration=True,
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

    async def refresh_data(self):
        try:
            with open(self.claninfo_path) as file:
                self.static_clandata = dict(json.load(file))
            all_clan_data = dict()
            for name, data in self.static_clandata.items():
                try:
                    clan_tag = data["tag"]
                    clan_data = await self.clash.get_clan(clan_tag)
                    all_clan_data[name] = dict(clan_data)
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

    async def red_delete_data_for_user(
        self, *, requester: RequestType, user_id: int
    ) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    @tasks.loop(seconds=30)
    async def get_clandata(self):
        """Check current data against data stored in config."""
        if self is not self.bot.get_cog("ClashRoyaleClans2"):
            return
        old_data = list()
        store_log = await self.config.keep_memberlog()
        if store_log:
            old_data = deepcopy(await self.config.clans())

        try:
            await self.refresh_data()
        except Exception as e:
            if self.last_error_time:
                if self.last_error_time - time.time() >= 300:
                    log.exception(f"Error {e} when updating data.", exc_info=e)
                    self.last_error_time = time.time()
            return

        new_data = dict(deepcopy(await self.config.clans()))
        type(new_data)
        new_data = {
            k: v
            for k, v in sorted(
                new_data.items(),
                key=lambda x: (
                    x[1]["clan_war_trophies"],
                    x[1]["required_trophies"],
                    x[1]["clan_score"],
                ),
                reverse=True,
            )
        }

        if len(new_data) == 0:
            log.error("Clans data is empty.")
            return
        if store_log:
            if len(old_data) == 0:
                await self.config.clans.set(dict(new_data))
                return
            for key, data in new_data.items():
                old_clan_data = {}
                new_clan_data = {}
                for member_data in old_data[key]["member_list"]:
                    old_clan_data[member_data["tag"]] = member_data["name"]
                for member_data in data["member_list"]:
                    new_clan_data[member_data["tag"]] = member_data["name"]

                if len(old_clan_data) > 0:
                    total = set(list(new_clan_data.keys())).union(
                        set(list(old_clan_data.keys()))
                    )
                    players_left_clan = set(total - set(new_clan_data.keys()))
                    players_joined_clan = set(total - set(old_clan_data.keys()))
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

    async def all_clans_data(self):
        """Return clan data"""
        return await self.config.clans()

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
        return [clan["tag"] for clan in self.static_clandata.values()]

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
