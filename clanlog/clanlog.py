import asyncio
import json
import logging
from copy import deepcopy
from datetime import datetime
from time import time
from typing import Optional

import clashroyale
import discord
from discord.ext import tasks
from redbot.core import Config, checks, commands
from redbot.core.commands.commands import command
from redbot.core.data_manager import cog_data_path
from redbot.core.utils import AsyncIter

log = logging.getLogger("red.cogs.clanlog")


class NoToken(Exception):
    pass


class NoClansCog(Exception):
    pass


class ClanLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=6942053)
        default_global = {
            "log_channel": 747520169404006483,
            "debug_channel": 747520169404006483,
            "clans": list(),
        }
        self.config.register_global(**default_global)

        self.crclans = self.bot.get_cog("ClashRoyaleClans")
        if not self.crclans:
            log.error("Load clashroyale clans for this cog to work.")
            raise NoClansCog
        self.claninfo_path = str(cog_data_path(self.crclans) / "clans.json")

        self.refresh_task = self.clan_log.start()
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
            async with crclans.claninfo_lock:
                with open(self.claninfo_path) as file:
                    self.family_clans = dict(json.load(file))
            all_clan_data = list()
            for name, data in self.family_clans.items():
                try:
                    clan_tag = data["tag"]
                    clan_data = await self.clash.get_clan(clan_tag)
                    all_clan_data.append(
                        {
                            "name": clan_data["name"],
                            "tag": clan_data["tag"],
                            "member_list": clan_data["member_list"],
                        }
                    )
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
    async def clan_log(self):
        """Check current data against data stored in config and log members joined or left in log channel."""

        log_channel_id = await self.config.log_channel()
        debug_channel_id = await self.config.debug_channel()
        log_channel = self.bot.get_channel(log_channel_id)
        debug_channel = self.bot.get_channel(debug_channel_id)

        if log_channel is None:
            log.error("The channel to send log messages is not setup correctly.")
            return

        if debug_channel:
            await debug_channel.send(
                "Loop iteration {} has started at {}.".format(
                    self.loop_count, datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
                )
            )

        if self is not self.bot.get_cog("ClanLog"):
            await log_channel.send(
                "Hi there! This cog is running in an invalid state. "
                "Inform the devs and bot owner that the unload loop is not setup properly."
                "This will require restarting the bot after fixing the cog."
            )
            return

        old_data = deepcopy(await self.config.clans())
        try:
            await self.refresh_data()
        except Exception as e:
            if debug_channel:
                debug_channel.send(f"Error {e} when updating data.")
            if self.last_error:
                if self.last_error - time.time() >= 300:
                    log.error(f"Error {e} when updating data.")
                    self.last_error = time.time()
            return

        new_data = deepcopy(await self.config.clans())

        if len(new_data) == 0:
            log.error("Clans data is empty.")
            return

        if len(old_data) == 0:
            await self.config.clans.set(list(new_data))
            return

        for index, clan in enumerate(new_data):
            old_clan_data = {}
            new_clan_data = {}
            for member_data in old_data[index]["member_list"]:
                old_clan_data[member_data["tag"]] = member_data["name"]
            for member_data in clan["member_list"]:
                new_clan_data[member_data["tag"]] = member_data["name"]
            clan_tag = clan["tag"]

            if len(old_clan_data) > 0:
                total = set(list(new_clan_data.keys())).union(
                    set(list(old_clan_data.keys()))
                )
                players_left_clan = list(total - set(new_clan_data.keys()))
                players_joined_clan = list(total - set(old_clan_data.keys()))
                # if len(players_left_clan) > 0 or len(players_joined_clan) > 0:
                #     print("Total: ", total)
                #     print("New: ", new_clan_data.keys())
                #     print("Old: ", old_clan_data.keys())
                description = ""
                for player_tag in players_left_clan:
                    player_name = old_clan_data.get(player_tag) or "wtf"
                    sad_emote = self.bot.get_emoji(592001717311242241) or ""
                    description += "{}({}) has left {} {}".format(
                        player_name, player_tag, clan["name"], sad_emote
                    )
                if description:
                    embed = discord.Embed(
                        title="Member Left",
                        description=description,
                        colour=discord.Colour.blue(),
                    )
                    await log_channel.send(embed=embed)
                description = ""
                for player_tag in players_joined_clan:
                    player_name = new_clan_data.get(player_tag) or "wtf"
                    happy_emote = self.bot.get_emoji(375143193630605332) or ""
                    description += "{}({}) has joined {} {}".format(
                        player_name, player_tag, clan["name"], happy_emote
                    )
                if description:
                    embed = discord.Embed(
                        title="Member Joined",
                        description=description,
                        colour=discord.Colour.blue(),
                    )
                    await log_channel.send(embed=embed)

        await self.config.clans.set(list(new_data))
        self.last_error_time = None
        self.last_updated = datetime.now()
        self.last_updated_preety = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        if debug_channel:
            await debug_channel.send(
                "Loop iteration {} has ended at {}.".format(
                    self.loop_count, self.last_updated_preety
                )
            )
        self.loop_count += 1

    @commands.command()
    @checks.admin_or_permissions()
    async def stopclanlog(self, ctx):
        if self.refresh_task:
            self.refresh_task.stop()

    @commands.command()
    @checks.admin_or_permissions()
    async def setclanloglogchannel(self, ctx, channel: discord.TextChannel):
        await self.config.log_channel.set(channel.id)
        await ctx.send("Clanlog channel has been set to {}".format(channel.mention))
        await ctx.tick()

    @commands.command()
    @checks.is_owner()
    async def setclanlogdebugchannel(self, ctx, channel: Optional[discord.TextChannel]):
        if channel is None:
            await self.config.debug_channel.set(None)
            await ctx.send("Debug disabled.")
            await ctx.tick()
            return
        await self.config.debug_channel.set(channel.id)
        await ctx.send("Debug channel has been set to {}".format(channel.mention))
        await ctx.tick()

    @commands.command()
    @checks.is_owner()
    async def clearoldclanlog(self, ctx):
        await self.config.clans.set(list())
        await ctx.tick()

    def cog_unload(self):
        if self.refresh_task:
            self.refresh_task.cancel()
        if self.token_task:
            self.token_task.cancel()
        if self.clash:
            close_task = self.bot.loop.create_task(self.clash.close())
