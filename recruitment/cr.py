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
        default_guild = {
            "mentions": {
                "on_show_clan": {"users": True, "roles": True},
                "on_approve": {"users": True, "roles": True},
                "on_nm": True,
                "on_newrecruit": True,
                "on_waitlist_add": True,
            },
            "global_channel_id": 374596069989810178,
            "new_recruits_channel_id": 375839851955748874,
            "player_info_legend": True,
        }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.discord_helper = Helper(bot)

        self.claninfo_path = str(cog_data_path(self) / "clans.json")
        with open(self.claninfo_path) as file:
            self.family_clans = dict(json.load(file))

        self.greetings_path = str(bundled_data_path(self) / "welcome_messages.json")
        with open(self.greetings_path) as file:
            self.greetings = list((json.load(file)).get("GREETING"))

        self.rules_path = str(bundled_data_path(self) / "rules.txt")
        with open(self.rules_path) as file:
            self.rules_text = file.read()

        self.esports_path = str(bundled_data_path(self) / "esports.txt")
        with open(self.esports_path) as file:
            self.esports_text = file.read()

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

    @commands.command(name="legend")
    async def command_legend(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
        account: int = 1,
    ):
        """
        Show Legend clans.
        Can also show clans based on a member's stats
        """
        async with ctx.channel.typing():
            # Show all clans if member is None.
            player_trophies = 9999
            player_pb = 9999
            player_cwr = {
                "legendary": {"percent": 0},
                "gold": {"percent": 0},
                "silver": {"percent": 0},
                "bronze": {"percent": 0},
            }
            player_wd_wins = 0
            if member is not None:
                try:
                    player_tag = self.tags.getTag(member.id, account)
                    if player_tag is None:
                        await ctx.send(
                            "You must associate a tag with this member first using "
                            "``{}save #tag @member``".format(ctx.prefix)
                        )
                        return
                    player_data = await self.clash.get_player(player_tag)
                    player_trophies = player_data.trophies
                    player_cards = player_data.cards
                    player_pb = player_data.best_trophies
                    player_maxwins = player_data.challenge_max_wins
                    player_cwr = await self.discord_helper.clanwar_readiness(
                        player_cards
                    )
                    player_wd_wins = player_data.warDayWins

                    if player_data.clan is None:
                        player_clanname = "*None*"
                    else:
                        player_clanname = player_data.clan.name

                    ign = player_data.name
                # REMINDER: Order is important. RequestError is base exception class.
                except AttributeError:
                    return await ctx.send(
                        "Cannot connect to database. Please notify the devs."
                    )
                except clashroyale.NotFoundError:
                    return await ctx.send("Player tag is invalid.")
                except clashroyale.RequestError:
                    return await ctx.send(
                        "Error: cannot reach Clash Royale Servers. "
                        "Please try again later."
                    )

            embed = discord.Embed(color=0xFAA61A)
            embed.set_author(
                name="Legend Family Clans",
                url="http://royaleapi.com/clan/family/legend",
                icon_url="https://cdn.discordapp.com/attachments/423094817371848716/425389610223271956/legend_logo-trans.png",
            )
            embed.set_footer(text=credits, icon_url=credits_icon)

            found_clan = False
            total_members = 0
            total_waiting = 0
            clans = await self.config.clans()
            if clans is None or len(clans) == 0:
                return await ctx.send(
                    "Use `{}refresh` to get clan data.".format(ctx.prefix)
                )

            for clan in clans:
                cwr_fulfilled = True

                clan_name = clan["name"]
                clan_requirements = self.family_clans[clan_name].get(
                    "requirements", dict()
                )
                waiting = self.family_clans[clan_name].get("waiting", list())
                num_waiting = len(waiting)
                total_waiting += num_waiting

                req_pb = clan_requirements.get("personalbest", 0)
                req_cwr = clan_requirements.get(
                    "cwr", {"legendary": 0, "gold": 0, "silver": 0, "bronze": 0}
                )
                req_bonus_str = clan_requirements.get("bonus", "")
                req_wd_wins = clan_requirements.get("wdwins", 0)

                member_count = clan.get("members")
                total_members += member_count

                if num_waiting > 0:
                    title = f"[{str(num_waiting)} Waiting] "
                else:
                    title = ""
                if str(clan.get("type")) != "inviteOnly":
                    title += f"[{str(clan.get('type')).title()}] "
                title += f"{clan['name']} ({clan['tag']}) "
                if req_pb > 0:
                    title += f"PB: {str(req_pb)}+  "
                for league in req_cwr:
                    if req_cwr[league] > 0:
                        title += "{}: {}%  ".format(
                            league[:1].capitalize(), req_cwr[league]
                        )
                        if player_cwr[league]["percent"] < req_cwr[league]:
                            cwr_fulfilled = False
                if req_wd_wins > 0:
                    title += "{}+ War Day Wins ".format(req_wd_wins)
                if req_bonus_str is not None:
                    title += req_bonus_str

                emoji = self.family_clans[clan_name].get("emoji", "")
                if member_count < 50:
                    shown_members = str(member_count) + "/50"
                else:
                    shown_members = "**FULL**ΓÇé "

                desc = "{}ΓÇé{} ΓÇéΓÇé{} {}+ΓÇéΓÇé{} {}ΓÇéΓÇé{}{}".format(
                    self.discord_helper.emoji(emoji),
                    shown_members,
                    self.discord_helper.emoji("PB"),
                    clan["required_trophies"],
                    self.discord_helper.getLeagueEmoji(clan["clan_war_trophies"]),
                    clan["clan_war_trophies"],
                    self.discord_helper.emoji("crtrophy"),
                    clan["clan_score"],
                )

                if (
                    (member is None)
                    or (
                        (player_trophies >= clan["required_trophies"])
                        and (player_pb >= req_pb)
                        and (cwr_fulfilled)
                        and (player_trophies - clan["required_trophies"] < 1500)
                        and (clan["type"] != "closed")
                        and (player_wd_wins >= req_wd_wins)
                    )
                    or (
                        (clan["required_trophies"] < 4000)
                        and (member_count != 50)
                        and (2000 < player_trophies < 5500)
                        and (clan["type"] != "closed")
                        and (player_wd_wins >= req_wd_wins)
                        and (cwr_fulfilled)
                    )
                ):
                    found_clan = True
                    embed.add_field(name=title, value=desc, inline=False)

            if not found_clan:
                embed.add_field(
                    name="uh oh!",
                    value="There are no clans available for you at the moment, "
                    "please type !legend to see all clans.",
                    inline=False,
                )

            embed.description = (
                "Our Family is made up of {} "
                "clans with a total of {} "
                "members. We have {} spots left "
                "and {} members in waiting lists.".format(
                    len(clans),
                    total_members,
                    (len(clans) * 50) - total_members,
                    total_waiting,
                )
            )
            await ctx.send(embed=embed)

            if member is not None:
                show_playerinfo = await self.config.guild(
                    ctx.guild
                ).player_info_legend()
                if not show_playerinfo:
                    return await ctx.send(
                        embed=discord.Embed(
                            color=0xFAA61A,
                            description=":warning: **YOU WILL BE REJECTED IF YOU JOIN ANY CLAN WITHOUT APPROVAL**",
                        )
                    )
                return await ctx.send(
                    embed=discord.Embed(
                        color=0xFAA61A,
                        description=(
                            "Hello **{}**, above are all the clans "
                            "you are allowed to join, based on your statistics. "
                            "Which clan would you like to join? \n\n"
                            "**Name:** {} (#{})\n**Trophies:** {}/{}\n"
                            "**CW Readiness:** {}\n"
                            "**Max Challenge Wins:** {}\n"
                            "**Clan:** {}\n\n"
                            ":warning: **YOU WILL BE REJECTED "
                            "IF YOU JOIN ANY CLAN WITHOUT "
                            "APPROVAL**".format(
                                ign,
                                ign,
                                player_tag,
                                player_trophies,
                                player_pb,
                                await self.discord_helper.get_best_league(player_cards),
                                player_maxwins,
                                player_clanname,
                            )
                        ),
                    )
                )
                # )

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

    @commands.command(name="clanaudit")
    async def clanaudit(self, ctx, nickname: str):
        async with ctx.channel.typing():
            clan_info = self.get_clan_by_nickname(nickname)
            if clan_info is None:
                embed = discord.Embed(
                    title="Unknown nickname",
                    description="You entered a nickname not found found in clans.json",
                    color=0xFF0000,
                )
                await ctx.channel.send(embed=embed)
                return

            clan_role = clan_info["clanrole"]
            clan_tag = clan_info["tag"]

            # List of all clan member tags from ClashRoyalAPI
            clan_member_by_name_by_tags = await self.get_clan_members(clan_tag)

            # Obtain all members with the clanrole
            role = discord.utils.get(ctx.guild.roles, name=clan_role)

            unknown_members = []  # People w/ role and no tags
            orphan_members = (
                []
            )  # People w/ role and have a tag and can't be found in the ClashRoyalAPI
            absent_names = []  # Tags (URLS?) of people who aren't in Discord
            processed_tags = []

            async for member in AsyncIter(role.members):
                member_tags = self.tags.quickGetAllTags(member.id)
                if len(member_tags) == 0:
                    unknown_members.append(f"{member.name}")

                found = False
                for tag in member_tags:
                    if tag in clan_member_by_name_by_tags:
                        found = True
                        processed_tags.append(tag)

                if not found:
                    orphan_members.append(f"{member.name}")

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
                absent_names_str = absent_names_str[
                    :1024
                ]  # max length allowed for discord
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
            embed.add_field(
                name=f"({absent_count}) Players in **{clan_info['name']}**, but have **NOT** joined discord",
                value=absent_names_str,
                inline=False,
            )

            await ctx.channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=True, roles=True),
            )

    def get_clan_by_nickname(self, nickname: str):
        for name, data in self.family_clans.items():
            if data.get("nickname").lower() == nickname:
                return data
        return None

    async def get_clan_members(self, clan_tag: str):
        members_names_by_tag = {}

        clan_data = await self.get_clandata_by_tag(clan_tag)
        for member in clan_data["member_list"]:
            members_names_by_tag[member["tag"].strip("#")] = member["name"]
        return members_names_by_tag

    async def get_clandata_by_tag(self, clan_tag):
        if clan_tag[0] != "#":
            clan_tag = "#" + clan_tag

        clans = await self.config.clans()
        for clan in clans:
            if clan["tag"] == clan_tag:
                return clan
        return None

    @commands.command(name="refresh")
    @checks.mod_or_permissions()
    async def command_refresh(self, ctx: commands.Context):
        async with self.claninfo_lock:
            with open(self.claninfo_path) as file:
                self.family_clans = dict(json.load(file))
        clan_data = list()
        for k, v in self.family_clans.items():
            try:
                clan_tag = v["tag"]
                clan = await self.clash.get_clan(clan_tag)
                clan_data.append(dict(clan))
            # REMINDER: Order is important. RequestError is base exception class.
            except clashroyale.NotFoundError:
                log.critical("Invalid clan tag.")
                return await ctx.send(
                    "Invalid Clan Tag. Please inform a dev about this."
                )
            except clashroyale.RequestError:
                log.error("Error: Cannot reach ClashRoyale Server.")
                return await ctx.send(
                    "Error: cannot reach Clash Royale Servers. Please try again later."
                )
            else:
                log.info("Updated data for clan {}.".format(k))
        clan_data = sorted(
            clan_data,
            key=lambda x: (
                x["clan_war_trophies"],
                x["required_trophies"],
                x["clan_score"],
            ),
            reverse=True,
        )
        await self.config.clans.set(clan_data)
        log.info(
            "Updated data for all clans at {}.".format(
                datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            )
        )
        await simple_embed(
            ctx,
            "Use this command only when automated refresh is not working. Inform devs if that happens.",
        )
        self.last_updated = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        await ctx.tick()

    @commands.command(name="approve")
    @checks.mod_or_permissions()
    async def command_approve(
        self,
        ctx: commands.Context,
        member: discord.Member,
        clankey: str,
        account: int = 1,
    ):
        guild = ctx.guild
        valid_keys = [k["nickname"].lower() for k in self.family_clans.values()]
        if clankey.lower() not in valid_keys:
            return await simple_embed(
                ctx,
                "Please use a valid clanname:\n{}".format(
                    humanize_list(list(valid_keys))
                ),
                False,
            )
        clan_info = {}
        # Get requirements for clan to approve
        for name, data in self.family_clans.items():
            if data.get("nickname").lower() == clankey.lower():
                clan_info = data
        clan_name: str = clan_info.get("name")
        clan_tag = clan_info.get("tag")
        clan_role = clan_info.get("clanrole")
        clan_pb = clan_info["requirements"].get("personalbest")
        clan_cwr = clan_info["requirements"].get("cwr")
        clan_private = clan_info["requirements"].get("private")
        clan_waiting = clan_info["waiting"]
        clan_wd_wins = clan_info["requirements"].get("wdwins")

        is_in_clan = True
        try:
            player_tag = self.tags.getTag(member.id, account)
            if player_tag is None:
                return await simple_embed(
                    ctx,
                    "You must associate a tag with this member first using ``{}save #tag @member``".format(
                        ctx.prefix
                    ),
                    False,
                )
            player_data = await self.clash.get_player(player_tag)
            # Clan data for clan to approve
            app_clan_data = await self.clash.get_clan(clan_tag)

            ign = player_data.name
            if player_data.clan is None:
                is_in_clan = False
                player_clantag = ""
            else:
                player_clantag = player_data.clan.tag.strip("#")
        # REMINDER: Order is important. RequestError is base exception class.
        except AttributeError:
            return await ctx.send("Cannot connect to database. Please notify the devs.")
        except clashroyale.NotFoundError:
            return await ctx.send("Player tag is invalid.")
        except clashroyale.RequestError:
            return await simple_embed(
                ctx, "Error: cannot reach Clash Royale Servers. Please try again later."
            )

        # Check if member is already in a clan of family
        membership = False
        for name, data in self.family_clans.items():
            if data["tag"] == player_clantag:
                membership = True

        if not membership:
            player_trophies = player_data.trophies
            player_cards = player_data.cards
            player_pb = player_data.best_trophies
            player_wd_wins = player_data.warDayWins
            player_cwr = await self.discord_helper.clanwar_readiness(player_cards)

            if app_clan_data.get("members") == 50:
                return await simple_embed(
                    ctx, "Approval failed, the clan is Full.", False
                )

            if (player_trophies < app_clan_data.required_trophies) or (
                player_pb < clan_pb
            ):
                return await simple_embed(
                    ctx,
                    "Approval failed, you don't meet the trophy requirements.",
                    False,
                )

            cwr_met = True
            for league in clan_cwr:
                if clan_cwr[league] > 0:
                    if player_cwr[league]["percent"] < clan_cwr[league]:
                        cwr_met = False
            if not cwr_met:
                return await simple_embed(
                    ctx,
                    "Approval failed, you don't meet the CW Readiness requirements.",
                    False,
                )

            if player_wd_wins < clan_wd_wins:
                return await simple_embed(
                    ctx,
                    "Approval failed, you don't meet requirements for war day wins.",
                    False,
                )

            if app_clan_data.type == "closed":
                return await simple_embed(
                    ctx, "Approval failed, the clan is currently closed.", False
                )

            if clan_private:
                if clan_role not in [y.name for y in ctx.author.roles]:
                    return await simple_embed(
                        ctx,
                        "Approval failed, only {} staff can approve new recruits for this clan.".format(
                            clan_name
                        ),
                        False,
                    )

            await self.remove_from_waiting(clan_name, member)
            if is_in_clan:
                warning = (
                    "\n\n:warning: **YOU WILL BE REJECTED "
                    "IF YOU JOIN ANY CLAN WITHOUT "
                    "APPROVAL**"
                )
                await ctx.send(
                    (
                        "{} Please leave your current clan now. "
                        "Your recruit code will arrive in 3 minutes.{}".format(
                            member.mention, warning
                        )
                    ),
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
                await asyncio.sleep(180)

            try:
                recruit_code = "".join(
                    random.choice(string.ascii_uppercase + string.digits)
                    for _ in range(6)
                )

                await simple_embed(
                    member,
                    "Congratulations, You have been approved to join "
                    f"[{clan_name} (#{clan_tag})](https://link.clashroyale.com/?clanInfo?id={clan_tag})."
                    "\n\n"
                    f"Your **RECRUIT CODE** is: ``{recruit_code}`` \n\n"
                    f"Click [here](https://link.clashroyale.com/?clanInfo?id={clan_tag}) "
                    f"or search for #{clan_tag} in-game.\n"
                    "Send a request **using recruit code** above and wait for your clan leadership to accept you. "
                    + "It usually takes a few minutes to get accepted, but it may take up to a few hours. \n\n"
                    + "**IMPORTANT**: Once your clan leadership has accepted your request, "
                    + "let a staff member in discord know that you have been accepted. "
                    + "They will then unlock all the member channels for you.",
                )
                await ctx.send(
                    (
                        member.mention
                        + " has been approved for **"
                        + clan_name
                        + "**. Please check your DM for instructions on how to join."
                    ),
                    allowed_mentions=discord.AllowedMentions(users=True),
                )

                try:
                    new_name = ign + " (Approved)"
                    await member.edit(nick=new_name)
                except discord.Forbidden:
                    await simple_embed(
                        ctx,
                        "I don't have permission to change nick for this user.",
                        False,
                    )

                role_to_ping = discord.utils.get(guild.roles, name=clan_role)

                embed = discord.Embed(color=0x0080FF)
                embed.set_author(
                    name="New Recruit", icon_url="https://i.imgur.com/dtSMITE.jpg"
                )
                embed.add_field(name="Name", value=ign, inline=True)
                embed.add_field(name="Recruit Code", value=recruit_code, inline=True)
                embed.add_field(name="Clan", value=clan_name, inline=True)
                embed.set_footer(text=credits, icon_url=credits_icon)

                channel = self.bot.get_channel(
                    await self.config.guild(ctx.guild).new_recruits_channel_id()
                )
                if channel and role_to_ping:
                    await channel.send(
                        role_to_ping.mention,
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(
                            roles=(await self.config.guild(ctx.guild).mentions())[
                                "on_newrecruit"
                            ]
                        ),
                    )
                elif not channel:
                    await ctx.send(
                        "Cannot find channel. Please contact a admin or a dev."
                    )
                elif not role_to_ping:
                    await ctx.send(f"Connot find role {clan_role}.")
            except discord.errors.Forbidden:
                return await ctx.send(
                    "Approval failed, {} please fix your privacy settings, "
                    "we are unable to send you Direct Messages.".format(member.mention),
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
        else:
            await simple_embed(
                ctx,
                f"Approval failed, {member.display_name} is already a part of {player_data.clan.name}, "
                f"a clan in the family.",
                False,
            )

    @commands.command(name="newmember")
    @checks.mod()
    async def command_newmember(self, ctx, member: discord.Member):
        """
            Setup nickname, and roles for a new member
        """
        guild = ctx.guild

        # if not (await self.bot.is_mod(ctx.author)):
        #     return await ctx.send(
        #         "Sorry! You do not have enough permissions to run this command."
        #     )

        # Check if user already has any of member roles:
        # Use `!changeclan` to change already registered member's clan cause it needs role checking to remove existing roles
        # if await self.discord_helper._is_member(member, guild=ctx.guild):
        #     return await ctx.send("Error, " + member.mention + " is not a new member.")

        is_clan_member = False
        try:
            player_tags = self.tags.getAllTags(member.id)
        except AttributeError:
            return await ctx.send("Cannot connect to database. Please notify the devs.")
        clans_joined = []
        clan_roles = []
        discord_invites = []
        clan_nicknames = []
        ign = ""
        if len(player_tags) == 0:
            return await ctx.send(
                "You must associate a tag with this member first using ``{}save #tag @member``".format(
                    ctx.prefix
                )
            )

        # Get a list of all family clans joined.
        try:
            for tag in player_tags:
                player_data = await self.clash.get_player(tag)
                if player_data.clan is None:
                    player_clan_tag = ""
                    player_clan_name = ""
                else:
                    player_clan_tag = player_data.clan.tag.strip("#")
                    player_clan_name = player_data.clan.name
                for name, data in self.family_clans.items():
                    if data["tag"] == player_clan_tag:
                        is_clan_member = True
                        clans_joined.append(name)
                        clan_roles.append(data["clanrole"])
                        clan_nicknames.append(data["nickname"])
                        if data.get("invite"):
                            discord_invites.append(data["invite"])
                # Set ign to first available name
                if not ign and player_data.name:
                    ign = player_data.name
        except clashroyale.RequestError:
            return await simple_embed(
                ctx, "Error: cannot reach Clash Royale Servers. Please try again later."
            )

        if ign:
            newname = ign
        else:
            return await simple_embed(ctx, "Cannot find ign for user.", False)

        output_msg = ""
        if is_clan_member:
            newclanname = " | ".join(clan_nicknames)
            newname += " | " + newclanname

            try:
                await member.edit(nick=newname)
            except discord.HTTPException:
                await simple_embed(
                    ctx, "I don't have permission to change nick for this user.", False
                )
            else:
                output_msg += "Nickname changed to **{}**\n".format(newname)

            clan_roles.append("Member")
            try:
                await self.discord_helper._add_roles(
                    member, clan_roles, reason="used newmember"
                )
                output_msg += f"**{humanize_list(clan_roles)}** roles added."
            except discord.Forbidden:
                await ctx.send(
                    "{} does not have permission to edit {}ΓÇÖs roles.".format(
                        ctx.author.display_name, member.display_name
                    )
                )
            except discord.HTTPException:
                await ctx.send(
                    "Failed to add roles {}.".format(humanize_list(clan_roles))
                )
            except InvalidRole:
                await ctx.send(
                    "Server roles are not setup properly. "
                    "Please check if you have {} roles in server.".format(
                        humanize_list(clan_roles)
                    )
                )
            if output_msg:
                await simple_embed(ctx, output_msg, True)

            # TODO: Add welcome message to global chat
            await self.discord_helper._remove_roles(
                member, ["Guest"], reason="used newmwmber"
            )

            roleName = discord.utils.get(guild.roles, name=clan_roles[0])
            recruitment_channel = self.bot.get_channel(
                await self.config.guild(ctx.guild).new_recruits_channel_id()
            )
            if recruitment_channel:
                await recruitment_channel.send(
                    "**{}** recruited **{} (#{})** to {}".format(
                        ctx.author.display_name, ign, tag, roleName.mention
                    ),
                    allowed_mentions=discord.AllowedMentions(
                        roles=(await self.config.guild(ctx.guild).mentions())["on_nm"]
                    ),
                )

            global_channel = self.bot.get_channel(
                await self.config.guild(ctx.guild).global_channel_id()
            )
            if global_channel:
                greeting_to_send = (random.choice(self.greetings)).format(member)
                await global_channel.send(
                    greeting_to_send,
                    allowed_mentions=discord.AllowedMentions(users=True),
                )

            try:
                await simple_embed(
                    member,
                    "Hi There! Congratulations on getting accepted into our family. "
                    "We have unlocked all the member channels for you in LeGeND Discord Server. "
                    "DM <@598662722821029888> if you have any problems.\n"
                    "Please do not leave our Discord server while you are in the clan. Thank you.",
                )
                if discord_invites:
                    await member.send(
                        (
                            "Please click on the link below to join your clan Discord server. \n\n"
                            "{invites}".format(invites="\n".join(discord_invites))
                            + "\n\n"
                            "Please do not leave our main or clan servers while you are in the clan. Thank you."
                        )
                    )

                await asyncio.sleep(60)
                for page in pagify(self.rules_text, delims=["\n\n\n"]):
                    await simple_embed(member, page)
                await asyncio.sleep(60)
                for page in pagify(self.esports_text, delims=["\n\n\n"]):
                    await member.send(page)
            except discord.errors.Forbidden:
                await ctx.send(
                    (
                        "{} please fix your privacy settings, "
                        "we are unable to send you Direct Messages.".format(
                            member.mention
                        )
                    ),
                    allowed_mentions=discord.AllowedMentions(users=True),
                )

        else:
            await ctx.send(
                "You must be accepted into a clan before I can give you clan roles. "
                "Would you like me to check again in 2 minutes? (Yes/No)"
            )
            pred = MessagePredicate.yes_or_no(ctx)
            await self.bot.wait_for("message", check=pred)
            if not pred.result:
                return
            await ctx.send("Okay, I will retry this command in 2 minutes.")
            await asyncio.sleep(120)
            message = ctx.message
            message.content = ctx.prefix + "newmember {}".format(member.mention)
            await self.bot.process_commands(message)

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
                            "{} does not have permission to edit {}ΓÇÖs roles.".format(
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
                        "{} does not have permission to edit {}ΓÇÖs roles.".format(
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

    @commands.command(name="inactive")
    async def command_inactive(self, ctx, member: discord.Member):
        all_clan_roles = [c["clanrole"] for c in self.family_clans.values()]
        member_roles = set(member.roles)
        all_clan_roles += [
            "Member",
        ]
        await self.discord_helper._remove_roles(
            member, all_clan_roles, reason="used inactive"
        )
        # If tag is not saved or connection to CR server is not available use current name to determine ign
        try:
            tag = self.tags.getTag(member.id)
        except AttributeError:
            return await ctx.send("Cannot connect to database. Please notify the devs.")
        if tag is None:
            new_nickname = (member.display_name.split("|")[0]).strip()
        try:
            new_nickname = (await self.clash.get_player(tag)).name
        except discord.HTTPException:
            new_nickname = (member.display_name.split("|")[0]).strip()
        try:
            await member.edit(nick=new_nickname)
        except discord.Forbidden:
            await simple_embed(
                ctx, "I don't have permission to change nick for this user.", False
            )
        member_newroles = set(member.roles)
        removed_roles = [r.mention for r in member_roles.difference(member_newroles)]
        if len(removed_roles) == 0:
            removed_roles = ["None"]
        await simple_embed(
            ctx,
            f"Removed roles: {humanize_list(removed_roles)}\nReset nickname to {new_nickname}",
        )

    @commands.command(name="clanwarreadiness", aliases=["cwr"])
    async def command_cwr(
        self, ctx, member: Optional[discord.Member] = None, account: int = 1
    ):
        """View yours or other's clash royale CWR"""
        member = member or ctx.author
        pages = list()
        async with ctx.channel.typing():
            try:
                player_tag = self.tags.getTag(member.id, account)
                if player_tag is None:
                    return await ctx.send(
                        "You need to first save your profile using ``{}save #tag``".format(
                            ctx.prefix
                        )
                    )
                player_data = await self.clash.get_player(player_tag)
                leagues = await self.discord_helper.clanwar_readiness(player_data.cards)
            # REMINDER: Order is important. RequestError is base exception class.
            except AttributeError:
                return await ctx.send(
                    "Cannot connect to database. Please notify the devs."
                )
            except clashroyale.NotFoundError:
                return await ctx.send("Player tag is invalid.")
            except clashroyale.RequestError:
                return await ctx.send(
                    "Error: cannot reach Clash Royale Servers. Please try again later."
                )

            emote_mapper = {
                "legendary": self.discord_helper.emoji("legendleague"),
                "gold": self.discord_helper.emoji("goldleague"),
                "silver": self.discord_helper.emoji("silverleague"),
                "bronze": self.discord_helper.emoji("bronzeleague"),
            }

            embed = discord.Embed(color=0xFAA61A,)
            embed.set_author(
                name=player_data.name + " (" + player_data.tag + ")",
                icon_url=await self.constants.get_clan_image(player_data),
                url="https://royaleapi.com/player/" + player_data.tag.strip("#"),
            )
            embed.set_footer(text=credits, icon_url=credits_icon)
            embed.add_field(
                name="War Day Wins",
                value="{} {}".format(
                    self.discord_helper.emoji("warwin"), player_data.war_day_wins,
                ),
                inline=True,
            )
            embed.add_field(
                name="War Cards Collected",
                value="{} {}".format(
                    self.discord_helper.emoji("card"), player_data.clan_cards_collected,
                ),
                inline=True,
            )
            highest_league = None
            for l in leagues.keys():
                highest_league = l
                if leagues[l]["percent"] == 100:
                    break
            for league in leagues.keys():
                f_title = "{} {} League (Lvl {}) - {}%\n\u200b".format(
                    emote_mapper[league],
                    leagues[league]["name"],
                    leagues[league]["levels"],
                    leagues[league]["percent"],
                )
                value = []
                if len(leagues[league]["cards"]) > 20:
                    group = leagues[league]["cards"][:20]
                else:
                    group = leagues[league]["cards"]
                for card in group:
                    if card is not None:
                        emoji = await self.discord_helper.get_card_emoji(card)
                        if emoji:
                            value.append(emoji)
                        else:
                            value.append(f" {card} ")
                if len(value):
                    not_shown = len(leagues[league]["cards"]) - len(value)
                    value = " ".join(value)
                    value += f"+{not_shown} more\n\n\n" if not_shown else "\n\n\n"
                    embed.add_field(
                        name=f_title, value=value, inline=False,
                    )
                    if league != highest_league:
                        embed.add_field(name="\u200b", value="\u200b", inline=False)
            pages.append(embed)

            for league in leagues.keys():
                f_title = "{} {} League (Lvl {}) - {}%\n\u200b".format(
                    emote_mapper[league],
                    leagues[league]["name"],
                    leagues[league]["levels"],
                    leagues[league]["percent"],
                )
                embed = discord.Embed(color=0xFAA61A, title="Clan War Readiness",)
                embed.set_author(
                    name=player_data.name + " (" + player_data.tag + ")",
                    icon_url=await self.constants.get_clan_image(player_data),
                    url="https://royaleapi.com/player/" + player_data.tag.strip("#"),
                )
                embed.set_footer(text=credits, icon_url=credits_icon)
                groups = list(self.discord_helper.grouper(leagues[league]["cards"], 15))

                for index, group in enumerate(groups):
                    value = []
                    for card in group:
                        if card is not None:
                            emoji = await self.discord_helper.get_card_emoji(card)
                            if emoji:
                                value.append(emoji)
                            else:
                                value.append(f" {card} ")

                    if len(value):
                        value = " ".join(value)

                        embed.add_field(
                            name=f_title if index == 0 else "\u200b",
                            value=value,
                            inline=False,
                        )
                if groups:
                    pages.append(embed)
        return await menu(ctx, pages, DEFAULT_CONTROLS, timeout=60)

    @commands.group(name="waiting", autohelp=False)
    async def waiting(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            command = "waiting list"
            cmd = self.bot.get_command(command)
            if not cmd:
                return await ctx.send(
                    f"{command} is not currently available in the bot"
                )

            await ctx.invoke(cmd)

    @waiting.command(name="add")
    @checks.mod()
    async def waiting_add(
        self, ctx: commands.Context, member: discord.Member, clan_name, account: int = 1
    ):
        """Add people to the waiting list for a clan"""
        async with ctx.channel.typing():
            clan_name = clan_name.lower()

            valid_keys = [k["nickname"].lower() for k in self.family_clans.values()]
            if clan_name not in valid_keys:
                return await simple_embed(
                    ctx,
                    "Please use a valid clanname:\n{}".format(
                        humanize_list(list(valid_keys))
                    ),
                    False,
                )
            # Get requirements for clan to approve
            clan_info = None
            for name, data in self.family_clans.items():
                if data.get("nickname").lower() == clan_name:
                    clan_info = data

            clan_name = clan_info.get("name")
            clan_tag = clan_info.get("tag")
            clan_role = clan_info.get("clanrole")
            clan_pb = clan_info["requirements"].get("personalbest")
            clan_cwr = clan_info["requirements"].get("cwr")
            clan_private = clan_info["requirements"].get("private")
            clan_waiting = clan_info["waiting"]
            clan_wd_wins = clan_info["requirements"].get("wdwins")

            try:
                player_tag = self.tags.getTag(member.id, account)
                if player_tag is None:
                    return await simple_embed(
                        ctx,
                        "You must associate a tag with this member first using ``{}save #tag @member``".format(
                            ctx.prefix
                        ),
                        False,
                    )
                player_data = await self.clash.get_player(player_tag)
                # Clan data for clan to approve
                wait_clan_data = await self.clash.get_clan(clan_tag)

                player_ign = player_data.name
            # REMINDER: Order is important. RequestError is base exception class.
            except AttributeError:
                return await ctx.send(
                    "Cannot connect to database. Please notify the devs."
                )
            except clashroyale.NotFoundError:
                return await ctx.send("Player tag is invalid.")
            except clashroyale.RequestError:
                return await simple_embed(
                    ctx,
                    "Error: cannot reach Clash Royale Servers. Please try again later.",
                )

            player_ign = player_data.name
            player_trophies = player_data.trophies
            player_cards = player_data.cards
            player_pb = player_data.best_trophies
            player_cwr = await self.discord_helper.clanwar_readiness(player_cards)
            player_wd_wins = player_data.warDayWins

            if (
                player_trophies < wait_clan_data.required_trophies
                or player_pb < clan_pb
            ):
                return await simple_embed(
                    ctx,
                    "Cannot add you to the waiting list, you don't meet the trophy requirements.",
                )

            player_cwr_good = True
            for league in clan_cwr:
                if clan_cwr[league] > 0:
                    if player_cwr[league]["percent"] < clan_cwr[league]:
                        player_cwr_good = False

            if not player_cwr_good:
                return await simple_embed(
                    ctx,
                    "Cannot add you to the waiting lists, you don't meet the CW Readiness requirements.",
                )

            if player_wd_wins < clan_wd_wins:
                return await simple_embed(
                    ctx,
                    "Approval failed, you don't meet requirements for war day wins.",
                    False,
                )

            if not await self.add_to_waiting(clan_name, member):
                return await ctx.send(
                    "You are already in a waiting list for this clan."
                )

            waiting_role = discord.utils.get(ctx.guild.roles, name="Waiting")
            if not waiting_role:
                await simple_embed(ctx, "Cannot find a role named waiting.")
            try:
                if waiting_role:
                    await member.add_roles(waiting_role, reason="added to waiting list")
            except discord.Forbidden:
                raise
            except discord.HTTPException:
                raise
            await ctx.send(
                (
                    f"{member.mention} You have been added to the waiting list for **"
                    f"{clan_name}"
                    "**. We will mention you when a spot is available."
                ),
                allowed_mentions=discord.AllowedMentions(users=True),
            )

            role = discord.utils.get(ctx.guild.roles, name=clan_role)
            to_post = self.bot.get_channel(
                await self.config.guild(ctx.guild).new_recruits_channel_id()
            )
            if to_post:
                await to_post.send(
                    "**{} (#{})** added to the waiting list for {}".format(
                        player_ign, player_tag, role.mention
                    ),
                    allowed_mentions=discord.AllowedMentions(
                        roles=(await self.config.guild(ctx.guild).mentions())[
                            "on_waitlist_add"
                        ]
                    ),
                )
        await ctx.tick()

    @waiting.command(name="list")
    async def waiting_list(self, ctx: commands.Context):
        """Show status of the waiting list."""
        message = ""
        num_clans = 0
        num_players = 0

        async with ctx.channel.typing():

            embed = discord.Embed(color=discord.Colour.blue())

            for clan_name, clan_data in self.family_clans.items():
                if len(clan_data.get("waiting", {})) > 0:
                    num_clans += 1
                    message = ""
                    for index, user_ID in enumerate(clan_data.get("waiting", {})):
                        user = discord.utils.get(ctx.guild.members, id=user_ID)
                        try:
                            message += str(index + 1) + ". " + user.display_name + "\n"
                            num_players += 1
                        except AttributeError:
                            await self.remove_from_waiting(clan_name, user_ID)
                            message += f"{str(index+1)}.*user {user_ID} not found*\n"
                    embed.add_field(name=clan_name, value=message, inline=False)

        if not message:
            return await ctx.send("The waiting list is empty.")
        else:
            embed.description = (
                "We have "
                + str(num_players)
                + " people waiting for "
                + str(num_clans)
                + " clans."
            )
            embed.set_author(
                name="Legend Family Waiting List",
                icon_url="https://cdn.discordapp.com/attachments/423094817371848716/425389610223271956/legend_logo-trans.png",
            )
            embed.set_footer(text=credits, icon_url=credits_icon)
            return await ctx.send(embed=embed)

    @waiting.command(name="remove")
    @checks.mod()
    async def waiting_remove(
        self, ctx, member: discord.Member, clan_key, account: int = 1
    ):
        """Delete people from the waiting list for a clan"""
        async with ctx.channel.typing():
            clan_key = clan_key.lower()
            valid_keys = [k["nickname"].lower() for k in self.family_clans.values()]
            if clan_key not in valid_keys:
                return await simple_embed(
                    ctx,
                    "Please use a valid clanname:\n{}".format(
                        humanize_list(list(valid_keys))
                    ),
                    False,
                )
            clan_name = None
            for name, data in self.family_clans.items():
                if data.get("nickname").lower() == clan_key:
                    clan_name = name

            if not await self.remove_from_waiting(clan_name, member):
                return await simple_embed(ctx, "Recruit not found in the waiting list.")
            else:
                await ctx.send(
                    (
                        f"{member.mention} has been removed from the waiting list for **{clan_name}**."
                    ),
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
            waiting_role = discord.utils.get(ctx.guild.roles, name="Waiting")
            if not waiting_role:
                await simple_embed(ctx, "Cannot find a role named waiting.")
            try:
                if waiting_role:
                    await member.remove_roles(
                        waiting_role, reason="removing from waitlist"
                    )
            except discord.Forbidden:
                return await simple_embed(
                    ctx, "No permission to remove roles for this user."
                )
            except discord.HTTPException:
                raise
        await ctx.tick()

    async def add_to_waiting(self, clan_name: str, member: discord.Member):
        data = self.family_clans
        try:
            clan_data = data[clan_name]
        except IndexError:
            # This should never happen
            log.error(f"Cannot find clan named {clan_name}")
            raise
        if member.id in clan_data["waiting"]:
            return False
        clan_data["waiting"].append(member.id)
        async with self.claninfo_lock:
            with open(self.claninfo_path, "w") as file:
                json.dump(self.family_clans, file)
        return True

    async def remove_from_waiting(self, clan_name: str, member: discord.Member):
        try:
            clan_data = self.family_clans[clan_name]
        except IndexError:
            # This should never happen
            log.error(f"Cannot find clan named {clan_name}")
            raise
        if member.id not in clan_data["waiting"]:
            return False
        self.family_clans[clan_name]["waiting"].remove(member.id)
        async with self.claninfo_lock:
            with open(self.claninfo_path, "w") as file:
                json.dump(self.family_clans, file)
        return True

    @commands.group(name="clans")
    @checks.admin()
    async def clans(self, ctx):
        """ Set requirements for clan """
        pass

    @clans.command(name="cwr")
    async def clans_cwr(self, ctx, clankey, league, percent: int):
        """ Set cwr as requirement for clan """
        clan_name = None
        for name, data in self.family_clans.items():
            if data["nickname"].lower() == clankey.lower():
                clan_name = name
        if not clan_name:
            return await ctx.send(f"No clan named {clankey}.")
        try:
            current = self.family_clans[clan_name]["requirements"]["cwr"]
        except KeyError:
            return await ctx.send("There is something wrong with clan database.")
        if league.lower() in current.keys():
            if percent < 0:
                return await ctx.send(
                    "Invalid value for value. Cwr cannot be less than 0."
                )
            current[league.lower()] = int(percent)
        else:
            return await ctx.send(
                f"{league} is not a valid league. Valid leagues are: {humanize_list(list(current.keys()))}"
            )
        async with self.claninfo_lock:
            with open(self.claninfo_path, "w") as file:
                json.dump(self.family_clans, file)
        await ctx.tick()

    @clans.command(name="pb")
    async def clans_pb(self, ctx, clankey, value: int):
        """ Set personal best as requirements"""
        clan_name = None
        for name, data in self.family_clans.items():
            if data["nickname"].lower() == clankey.lower():
                clan_name = name
        if not clan_name:
            return await ctx.send(f"No clan named {clankey}.")
        try:
            if value < 0:
                return await ctx.send(
                    "Invalid value for value. Trophies cannot be less than 0."
                )
            self.family_clans[clan_name]["requirements"]["personalbest"] = value
        except KeyError:
            return await ctx.send("There is something wrong with clan database.")
        async with self.claninfo_lock:
            with open(self.claninfo_path, "w") as file:
                json.dump(self.family_clans, file)
        await ctx.tick()

    @clans.command(name="bonus")
    async def clans_bonus(self, ctx, clankey, value: str):
        """ Set bonus requirements for clan. Note that these values must be checked manually by hub officers. """
        clan_name = None
        for name, data in self.family_clans.items():
            if data["nickname"].lower() == clankey.lower():
                clan_name = name
        if not clan_name:
            return await ctx.send(f"No clan named {clankey}.")
        try:
            self.family_clans[clan_name]["requirements"]["bonus"] = value
        except KeyError:
            return await ctx.send("There is something wrong with clan database.")
        async with self.claninfo_lock:
            with open(self.claninfo_path, "w") as file:
                json.dump(self.family_clans, file)
        await ctx.tick()

    @clans.command(name="cwthreshold")
    async def clans_cwthreshold(self, ctx, clankey, value: int):
        """ Set fame threshold for clan """
        clan_name = None
        for name, data in self.family_clans.items():
            if data["nickname"].lower() == clankey.lower():
                clan_name = name
        if not clan_name:
            return await ctx.send(f"No clan named {clankey}.")
        try:
            self.family_clans[clan_name]["cwthreshold"] = value
        except KeyError:
            return await ctx.send("There is something wrong with clan database.")
        async with self.claninfo_lock:
            with open(self.claninfo_path, "w") as file:
                json.dump(self.family_clans, file)
        await ctx.tick()

    @clans.command(name="wdwins")
    async def clans_wdwins(self, ctx, clankey, value: int):
        """ Set warday wins requirements for clan """
        clan_name = None
        for name, data in self.family_clans.items():
            if data["nickname"].lower() == clankey.lower():
                clan_name = name
        if not clan_name:
            return await ctx.send(f"No clan named {clankey}.")
        try:
            self.family_clans[clan_name]["requirements"]["wdwins"] = value
        except KeyError:
            return await ctx.send("There is something wrong with clan database.")
        async with self.claninfo_lock:
            with open(self.claninfo_path, "w") as file:
                json.dump(self.family_clans, file)
        await ctx.tick()

    @commands.group(name="crclansset")
    @commands.guild_only()
    @checks.admin()
    async def crclansset(self, ctx):
        """ Set variables used by ClashRoylaleClans cog """
        pass

    @crclansset.group(name="clanmention")
    async def crclansset_clanmention(self, ctx):
        """ Set whether clan will be mentioned """
        pass

    @crclansset_clanmention.command(name="nm")
    async def crclanset_clanmention_nm(self, ctx, value: bool):
        """ Set whether clan will be mentioned on successful newmember """
        await self.config.guild(ctx.guild).mentions.on_nm.set(value)
        await ctx.tick()

    @crclansset_clanmention.command(name="waiting")
    async def crclanset_clanmention_waiting(self, ctx, value: bool):
        """ Set whether clan will be mentioned on successful addition to waiting list """
        await self.config.guild(ctx.guild).mentions.on_waitlist_add.set(value)
        await ctx.tick()

    @crclansset_clanmention.command(name="newrecruit")
    async def crclanset_clanmention_newrecruit(self, ctx, value: bool):
        """ Set whether clan will be mentioned when recruit is approved """
        await self.config.guild(ctx.guild).mentions.on_newrecruit.set(value)
        await ctx.tick()

    @crclansset.command(name="global")
    async def crclansset_global(self, ctx, channel: discord.TextChannel):
        """ Set channel used to welcome newly recruited members """
        await self.config.guild(ctx.guild).global_channel_id.set(channel.id)
        await ctx.tick()

    @crclansset.command(name="newrecruits")
    async def crclansset_newrecruits(self, ctx, channel: discord.TextChannel):
        """ Set channel used to inform staff about new recruits """
        await self.config.guild(ctx.guild).new_recruits_channel_id.set(channel.id)
        await ctx.tick()

    @crclansset.command(name="playerinfo")
    async def crclansset_playerinfo(self, ctx, value: bool):
        """ Set if player info is shown in output of legend """
        await self.config.guild(ctx.guild).player_info_legend.set(value)
        await ctx.tick()


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
