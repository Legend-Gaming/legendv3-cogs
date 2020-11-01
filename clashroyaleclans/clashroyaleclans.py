import asyncio
import itertools
import json
import logging
from datetime import datetime
from typing import List, Optional

import clashroyale
import discord
from discord.ext import tasks
from redbot.core import Config, checks, commands
from redbot.core.data_manager import cog_data_path
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import humanize_list, pagify

credits = "Bot by Legend Gaming"
credits_icon = "https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1"
log = logging.getLogger("red.cogs.clashroyaleclans")


class InvalidRole(Exception):
    pass


class NoToken(Exception):
    pass


async def simple_embed(
    ctx: commands.Context,
    message: str,
    success: Optional[bool] = None,
    mentions: dict = dict({"users": True, "roles": True}),
) -> discord.Message:
    """Helper function for embed"""
    if success is True:
        colour = discord.Colour.dark_green()
    elif success is False:
        colour = discord.Colour.dark_red()
    else:
        colour = discord.Colour.blue()
    embed = discord.Embed(description=message, color=colour)
    embed.set_footer(text=credits, icon_url=credits_icon)
    return await ctx.send(
        embed=embed, allowed_mentions=discord.AllowedMentions(**mentions)
    )


class ClashRoyaleClans(commands.Cog):
    """Commands for Clash Royale Family Management"""

    def __init__(self, bot):
        self.bot = bot

        crtools_cog = self.bot.get_cog("ClashRoyaleTools")
        self.tags = getattr(crtools_cog, "tags", None)
        self.constants = getattr(crtools_cog, "constants", "None")

        self.config = Config.get_conf(self, identifier=2286464642345664456)
        default_global = {"clans": list()}
        self.config.register_global(**default_global)

        try:
            self.claninfo_path = str(cog_data_path(self) / "clans.json")
            with open(self.claninfo_path) as file:
                self.family_clans = dict(json.load(file))
        except:
            self.family_clans = {}

        self.claninfo_lock = asyncio.Lock()

        self.token_task = self.bot.loop.create_task(self.crtoken())
        self.refresh_task = self.refresh_data.start()
        self.last_updated = None

    async def crtoken(self):
        # Initialize clashroyale API
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token.get("token") is None:
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

    @tasks.loop(seconds=30)
    async def refresh_data(self):
        try:
            async with self.claninfo_lock:
                with open(self.claninfo_path) as file:
                    self.family_clans = dict(json.load(file))
            all_clan_data = list()
            for name, data in self.family_clans.items():
                try:
                    clan_tag = data["tag"]
                    clan_data = await self.clash.get_clan(clan_tag)
                    all_clan_data.append(dict(clan_data))
                # REMINDER: Order is important. RequestError is base exception class.
                except clashroyale.NotFoundError:
                    log.critical("Invalid clan tag.")
                except clashroyale.RequestError as err:
                    log.error("Error: Cannot reach ClashRoyale Server. {}".format(err))
            all_clan_data = sorted(
                all_clan_data,
                key=lambda x: (
                    x["clan_war_trophies"],
                    x["required_trophies"],
                    x["clan_score"],
                ),
                reverse=True,
            )
            await self.config.clans.set(all_clan_data)
            # log.info("Updated data for all clans.")
        except Exception as e:
            log.error("Encountered exception {} when refreshing clan data.".format(e))
        self.last_updated = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
