import asyncio
import itertools
import json
import logging
import os
import random
import string
from datetime import datetime
from typing import List, Optional

import clashroyale
import discord
from discord.ext import tasks
from redbot.core import Config, checks, commands
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import humanize_list, pagify
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu, start_adding_reactions
from redbot.core.utils.predicates import MessagePredicate

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
        self.discord_helper = Helper(bot)

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

    @commands.command(name="nick")
    @checks.mod()
    async def _clan_server_setup(self, ctx, member: discord.Member):
        """
            Setup nickname, and roles for a new member in a private clan server
        """
        guild = ctx.guild
        legend_servers = {
            757553323602608128: ["RY9QJU2", "Rising"],
            741928176779001948: ["9P2PQULQ", "Empire"],
            424929926844776462: ["80CC8", "Squad"],
            712090493399334913: ["PRCRJYCR", "Dragons Eight III"],
        }
        if guild.id not in legend_servers:
            return await ctx.send("Command cannot be used in this server")

        try:
            player_tags = self.tags.getAllTags(member.id)
        except AttributeError:
            return await ctx.send("Cannot connect to database. Please notify the devs.")
        clans_joined = []
        clan_roles = []
        discord_invites = []
        clan_nicknames = []
        ign = ""
        output_msg = ""

        if len(player_tags) == 0:
            return await ctx.send(
                "You must associate a tag with this member first using ``{}save #tag @member``".format(
                    ctx.prefix
                )
            )

        try:
            for tag in player_tags:
                player_data = await self.clash.get_player(tag)
                if player_data.clan is None:
                    player_clan_tag = ""
                else:
                    player_clan_tag = player_data.clan.tag.strip("#")

                if player_clan_tag == legend_servers[guild.id][0]:

                    ign = player_data.name
                    try:
                        await member.edit(nick=ign)
                    except discord.HTTPException:
                        await simple_embed(
                            ctx,
                            "I don't have permission to change nick for this user.",
                            False,
                        )
                    else:
                        output_msg += "Nickname changed to **{}**\n".format(ign)

                    clan_roles.append(legend_servers[guild.id][1])
                    try:
                        await self.discord_helper._add_roles(
                            member, clan_roles, reason="used nick"
                        )
                        output_msg += f"**{humanize_list(clan_roles)}** role added."
                    except discord.Forbidden:
                        await ctx.send(
                            "{} does not have permission to edit {}’s roles.".format(
                                ctx.author.display_name, member.display_name
                            )
                        )
                    except discord.HTTPException:
                        await ctx.send(
                            "Failed to add role {}.".format(humanize_list(clan_roles))
                        )
                    except InvalidRole:
                        await ctx.send(
                            "Server roles are not setup properly. "
                            "Please check if you have {} roles in server.".format(
                                humanize_list(clan_roles)
                            )
                        )
                    if output_msg:
                        return await simple_embed(ctx, output_msg, True)

            else:
                try:
                    player_data = await self.clash.get_player(player_tags[0])
                    ign = player_data.name + " | Guest"
                    await member.edit(nick=ign)
                except discord.HTTPException:
                    await simple_embed(
                        ctx,
                        "I don't have permission to change nick for this user.",
                        False,
                    )
                else:
                    output_msg += "Nickname changed to **{}**\n".format(ign)

                clan_roles.append("Guest")
                try:
                    await self.discord_helper._add_roles(
                        member, clan_roles, reason="used nick"
                    )
                    output_msg += f"**{humanize_list(clan_roles)}** role added. \n*If you are a part of {legend_servers[guild.id][1]}, please save the tag of your account in {legend_servers[guild.id][1]} too.*"
                except discord.Forbidden:
                    await ctx.send(
                        "{} does not have permission to edit {}’s roles.".format(
                            ctx.author.display_name, member.display_name
                        )
                    )
                except discord.HTTPException:
                    await ctx.send(
                        "Failed to add role {}.".format(humanize_list(clan_roles))
                    )
                except InvalidRole:
                    await ctx.send(
                        "Server roles are not setup properly. "
                        "Please check if you have {} roles in server.".format(
                            humanize_list(clan_roles)
                        )
                    )
                if output_msg:
                    return await simple_embed(ctx, output_msg, True)
        except clashroyale.RequestError:
            return await simple_embed(
                ctx, "Error: cannot reach Clash Royale Servers. Please try again later."
            )

class Helper:
    def __init__(self, bot):
        self.bot = bot
        self.constants = self.bot.get_cog("ClashRoyaleTools").constants

    @staticmethod
    async def get_user_count(guild: discord.Guild, name: str):
        """Returns the numbers of people with the member role"""
        role = discord.utils.get(guild.roles, name=name)
        return len(role.members)

    @staticmethod
    async def _add_roles(member: discord.Member, role_names: List[str], reason=""):
        """Add roles"""
        roles = [
            discord.utils.get(member.guild.roles, name=role_name)
            for role_name in role_names
        ]
        if any([x is None for x in roles]):
            raise InvalidRole
        try:
            await member.add_roles(*roles, reason="From clashroyaleclans: " + reason)
        except discord.Forbidden:
            raise
        except discord.HTTPException:
            raise

    @staticmethod
    async def _remove_roles(member: discord.Member, role_names: List[str], reason=""):
        """Remove roles"""
        roles = [
            discord.utils.get(member.guild.roles, name=role_name)
            for role_name in role_names
        ]
        roles = [r for r in roles if r is not None]
        try:
            await member.remove_roles(*roles, reason="From clashroyaleclans: " + reason)
        except Exception:
            pass

    @staticmethod
    async def _is_member(member: discord.Member, guild: discord.Guild):
        """
            Check if member already has any of roles
        """
        """
            Credits: Gr8
        """
        _membership_roles = [
            discord.utils.get(guild.roles, name=r)
            for r in [
                "Member",
                "Co-Leader",
                "Hub Officer",
                "Hub Supervisor" "Clan Deputy",
                "Clan Manager",
            ]
        ]
        _membership_roles = set(_membership_roles)
        author_roles = set(member.roles)
        return bool(len(author_roles.intersection(_membership_roles)) > 0)

    async def clanwar_readiness(self, cards):
        """Calculate clanwar readiness"""
        readiness = {}
        league_levels = {"legendary": 12, "gold": 11, "silver": 10, "bronze": 9}

        for league in league_levels.keys():
            readiness[league] = {
                "name": league.capitalize(),
                "percent": 0,
                "cards": [],
                "levels": str(league_levels[league]),
            }
            for card in cards:
                if await self.constants.get_new_level(card) >= league_levels[league]:
                    readiness[league]["cards"].append(card.name)

            readiness[league]["percent"] = int(
                (len(readiness[league]["cards"]) / len(cards)) * 100
            )

        readiness["gold"]["cards"] = list(
            set(readiness["gold"]["cards"]) - set(readiness["legendary"]["cards"])
        )
        readiness["silver"]["cards"] = list(
            set(readiness["silver"]["cards"])
            - set(readiness["gold"]["cards"])
            - set(readiness["legendary"]["cards"])
        )
        readiness["bronze"]["cards"] = list(
            set(readiness["bronze"]["cards"])
            - set(readiness["silver"]["cards"])
            - set(readiness["gold"]["cards"])
            - set(readiness["legendary"]["cards"])
        )

        return readiness

    def emoji(self, name: str):
        """Emoji by name."""
        for emoji in self.bot.emojis:
            if emoji.name == name.replace(" ", "").replace("-", "").replace(".", ""):
                return "<:{}:{}>".format(emoji.name, emoji.id)
        return ""

    def getLeagueEmoji(self, trophies: int):
        """Get clan war League Emoji"""
        mapLeagues = {
            "legendleague": [3000, 99999],
            "gold3league": [2500, 2999],
            "gold2league": [2000, 2499],
            "goldleague": [1500, 1999],
            "silver3league": [1200, 1499],
            "silver2league": [900, 1199],
            "silverleague": [600, 899],
            "bronze3league": [400, 599],
            "bronze2league": [200, 399],
            "bronzeleague": [0, 199],
        }
        for league in mapLeagues.keys():
            if mapLeagues[league][0] <= trophies <= mapLeagues[league][1]:
                return self.emoji(league)

    def grouper(self, iterable, n):
        args = [iter(iterable)] * n
        return itertools.zip_longest(*args)

    async def get_best_league(self, cards):
        """Get best leagues using readiness"""
        readiness = await self.clanwar_readiness(cards)

        legend = readiness["legendary"]["percent"]
        gold = readiness["gold"]["percent"] - legend
        silver = readiness["silver"]["percent"] - gold - legend
        bronze = readiness["bronze"]["percent"] - silver - gold - legend

        readiness_count = {
            "legendary": legend,
            "gold": gold,
            "silver": silver,
            "bronze": bronze,
        }
        max_key = max(readiness_count, key=lambda k: readiness_count[k])

        return "{} League ({}%)".format(
            max_key.capitalize(), readiness[max_key]["percent"]
        )

    async def get_card_emoji(self, card_name: str):
        card_key = await self.constants.card_to_key(card_name)
        emoji = ""
        if card_key:
            emoji = self.emoji(card_key)
        if emoji == "":
            emoji = self.emoji(card_name)
        return emoji
