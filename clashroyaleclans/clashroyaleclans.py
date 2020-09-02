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
from redbot.core.utils.chat_formatting import humanize_list, pagify
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu, start_adding_reactions
from redbot.core.utils.predicates import MessagePredicate

credits = "Bot by Legend Gaming"
creditIcon = "https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1"
newrecruitsChannelId = 375839851955748874
globalChannelId = 374596069989810178
log = logging.getLogger("red.cogs.clashroyaleclans")


class InvalidRole(Exception):
    pass


class NoToken(Exception):
    pass


async def simple_embed(
    ctx: commands.Context, message: str, success: Optional[bool] = None
) -> discord.Message:
    """Helper function for embed"""
    if success is True:
        colour = discord.Colour.dark_green()
    elif success is False:
        colour = discord.Colour.dark_red()
    else:
        colour = discord.Colour.blue()
    embed = discord.Embed(description=message, color=colour)
    embed.set_footer(text=credits, icon_url=creditIcon)
    return await ctx.send(
        embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=True)
    )


class ClashRoyaleClans(commands.Cog):
    """Commands for Clash Royale Family Management"""

    def __init__(self, bot):
        self.bot = bot
        self.tags = self.bot.get_cog("ClashRoyaleTools").tags
        self.constants = self.bot.get_cog("ClashRoyaleTools").constants
        self.config = Config.get_conf(self, identifier=2286464642345664456)
        default_global = {"clans": list()}
        self.config.register_global(**default_global)
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

        self.token_task = self.bot.loop.create_task(self.crtoken())
        self.refresh_task = self.refresh_data.start()
        self.last_updated = None


    async def crtoken(self):
        # Initialize clashroyale API
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token["token"] is None:
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
        self.bot.loop.create_task(self.clash.close())


    @commands.command(name="tl")
    async def commandLegend(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
        account: int = 1,
    ):
        """
        Show TL clans.
        Can also show clans based on a member's stats
        """
        async with ctx.channel.typing():
            # Show all clans if member is None.
            player_trophies = 9999
            player_maxtrophies = 9999
            player_cwr = {
                "legendary": {"percent": 0},
                "gold": {"percent": 0},
                "silver": {"percent": 0},
                "bronze": {"percent": 0},
            }
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
                    player_maxtrophies = player_data.best_trophies
                    player_maxwins = player_data.challenge_max_wins
                    player_cwr = await self.discord_helper.clanwarReadiness(
                        player_cards
                    )
                    player_wd_wins = player_data.warDayWins

                    if player_data.clan is None:
                        player_clanname = "*None*"
                    else:
                        player_clanname = player_data.clan.name

                    ign = player_data.name
                # REMINDER: Order is important. RequestError is base exception class.
                except clashroyale.NotFoundError:
                    return await ctx.send("Player tag is invalid.")
                except clashroyale.RequestError:
                    return await ctx.send(
                        "Error: cannot reach Clash Royale Servers. "
                        "Please try again later."
                    )

            embed = discord.Embed(color=0xFAA61A)
            embed.set_author(
                name="Threat Level Family Clans",
                url="http://royaleapi.com/clan/family/threatlevel",
                icon_url="https://cdn.discordapp.com/attachments/423094817371848716/425389610223271956/legend_logo-trans.png",
            )

            embed.set_footer(text=credits, icon_url=creditIcon)

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

                pb = clan_requirements.get("personalbest", 0)
                cwr = clan_requirements.get(
                    "cwr", {"legendary": 0, "gold": 0, "silver": 0, "bronze": 0}
                )
                bonus = clan_requirements.get("bonus", "")
                wd_wins = clan_requirements.get("wdwins", 0)

                member_count = clan.get("members")
                total_members += member_count

                if num_waiting > 0:
                    title = f"[{str(num_waiting)} Waiting] "
                else:
                    title = ""
                if str(clan.get("type")) != "inviteOnly":
                    title += f"[{str(clan.get('type')).title()}] "
                title += f"{clan['name']}({clan['tag']}) "
                if pb > 0:
                    title += f"PB: {str(pb)}+  "
                for league in cwr:
                    if cwr[league] > 0:
                        title += "{}: {}%  ".format(
                            league[:1].capitalize(), cwr[league]
                        )
                        if player_cwr[league]["percent"] < cwr[league]:
                            cwr_fulfilled = False
                if wd_wins > 0:
                    title += "{}+ War Day Wins ".format(wd_wins)
                if bonus is not None:
                    title += bonus

                emoji = self.family_clans[clan_name].get("emoji", "")
                if member_count < 50:
                    shown_members = str(member_count) + "/50"
                else:
                    shown_members = "**FULL**  "

                desc = "{}   {} {} " "{}+  {} {}".format(
                    self.discord_helper.emoji(emoji),
                    shown_members,
                    self.discord_helper.emoji("crtrophy"),
                    clan["required_trophies"],
                    self.discord_helper.getLeagueEmoji(clan["clan_war_trophies"]),
                    clan["clan_war_trophies"],
                )

                if (
                    (member is None)
                    or (
                        (player_trophies >= clan["required_trophies"])
                        and (player_maxtrophies >= pb)
                        and (cwr_fulfilled)
                        and (player_trophies - clan["required_trophies"] < 1500)
                        and (clan["type"] != "closed")
                        and (player_wd_wins >= wd_wins)
                    )
                    or (
                        (clan["required_trophies"] <= 4000)
                        and (member_count != 50)
                        and (2000 < player_trophies < 5500)
                        and (clan["type"] != "closed")
                        and (player_wd_wins >= wd_wins)
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
            return await ctx.send(embed=embed)

            if member is not None:
                return await ctx.send(
                    (
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
                            player_maxtrophies,
                            await self.discord_helper.getBestLeague(player_cards),
                            player_maxwins,
                            player_clanname,
                        )
                    ),
                    allowed_mentions=discord.AllowedMentions(users=True, roles=True),
                )

    @tasks.loop(seconds=120)
    async def refresh_data(self):
        try:
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
                except clashroyale.RequestError:
                    log.error("Error: Cannot reach ClashRoyale Server.")
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

    @commands.command(name="refresh")
    @checks.mod_or_permissions()
    async def command_refresh(self, ctx: commands.Context):
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
            "Use this command only when automated refresh is not working. Inform <@683771700386857026> if that happens.",
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
        if clankey not in valid_keys:
            return await simple_embed(
                ctx,
                "Please use a valid clanname:\n{}".format(
                    humanize_list(list(valid_keys))
                ),
                False,
            )

        # Get requirements for clan to approve
        for name, data in self.family_clans.items():
            if data.get("nickname").lower() == clankey.lower():
                clan_info = data
        clan_name = clan_info.get("name")
        clan_tag = clan_info.get("tag")
        clan_role = clan_info.get("clanrole")
        clan_pb = clan_info["requirements"].get("personalbest")
        clan_cwr = clan_info["requirements"].get("cwr")
        clan_private = clan_info["requirements"].get("private")
        clan_waiting = clan_info["waiting"]
        clan_wdwins = clan_info["requirements"].get("wdwins")

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
            clan_data = await self.clash.get_clan(clan_tag)

            ign = player_data.name
            if player_data.clan is None:
                is_in_clan = False
                player_clantag = ""
            else:
                player_clantag = player_data.clan.tag.strip("#")
        # REMINDER: Order is important. RequestError is base exception class.
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
            trophies = player_data.trophies
            cards = player_data.cards
            maxtrophies = player_data.best_trophies
            player_wd_wins = player_data.warDayWins
            player_cwr = await self.discord_helper.clanwarReadiness(cards)
            if clan_data.get("members") == 50:
                return await simple_embed(
                    ctx, "Approval failed, the clan is Full.", False
                )

            if (trophies < clan_data.required_trophies) or (maxtrophies < clan_pb):
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

            if player_wd_wins < clan_wdwins:
                return await simple_embed(
                    ctx,
                    "Approval failed, you don't meet requirements for war day wins.",
                    False,
                )

            if clan_data.type == "closed":
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
                    allowed_mentions=discord.AllowedMentions(users=True, roles=True),
                )
                await asyncio.sleep(180)

            try:
                recruitCode = "".join(
                    random.choice(string.ascii_uppercase + string.digits)
                    for _ in range(6)
                )

                await simple_embed(
                    member,
                    "Congratulations, You have been approved to join "
                    f"[{clan_name} (#{clan_tag})](https://link.clashroyale.com/?clanInfo?id={clan_tag})."
                    "\n\n"
                    f"Your **RECRUIT CODE** is: ``{recruitCode}`` \n\n"
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
                    allowed_mentions=discord.AllowedMentions(users=True, roles=True),
                )

                try:
                    newname = ign + " (Approved)"
                    await member.edit(nick=newname)
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
                embed.add_field(name="Recruit Code", value=recruitCode, inline=True)
                embed.add_field(name="Clan", value=clan_name, inline=True)
                embed.set_footer(text=credits, icon_url=creditIcon)

                channel = self.bot.get_channel(newrecruitsChannelId)
                if channel and role_to_ping:
                    await channel.send(
                        role_to_ping.mention,
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(
                            users=True, roles=True
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
        author = ctx.author

        # if not (await self.bot.is_mod(ctx.author)):
        #     return await ctx.send(
        #         "Sorry! You do not have enough permissions to run this command."
        #     )

        # Check if user already has any of member roles:
        # Use `!changeclan` to change already registered member's clan cause it needs role checking to remove existing roles
        # if await self.discord_helper._is_member(member, guild=ctx.guild):
        #     return await ctx.send("Error, " + member.mention + " is not a new member.")

        is_clan_member = False
        player_tags = self.tags.getAllTags(member.id)
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
                await self.discord_helper._add_roles(member, clan_roles)
                output_msg += f"**{humanize_list(clan_roles)}** roles added."
            except discord.Forbidden:
                await ctx.send(
                    "{} does not have permission to edit {}’s roles.".format(
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
            await self.discord_helper._remove_roles(member, ["Guest"])

            roleName = discord.utils.get(guild.roles, name=clan_roles[0])
            recruitment_channel = self.bot.get_channel(newrecruitsChannelId)
            if recruitment_channel:
                await recruitment_channel.send(
                    "**{}** recruited **{} (#{})** to {}".format(
                        ctx.author.display_name, ign, tag, roleName.mention
                    ),
                    allowed_mentions=discord.AllowedMentions(users=True, roles=True),
                )

            global_channel = self.bot.get_channel(globalChannelId)
            if global_channel:
                greeting_to_send = (random.choice(self.greetings)).format(member)
                await global_channel.send(
                    greeting_to_send,
                    allowed_mentions=discord.AllowedMentions(users=True, roles=True),
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
                    allowed_mentions=discord.AllowedMentions(users=True, roles=True),
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

    @commands.command(name="inactive")
    async def command_inactive(self, ctx, member: discord.Member):
        all_clan_roles = [c["clanrole"] for c in self.family_clans.values()]
        member_roles = set(member.roles)
        all_clan_roles += [
            "Member",
            "Clan Deputy",
            "Co-Leader",
            "Hub Supervisor",
            "Hub Officer",
            "Recruitment Officer",
        ]
        await self.discord_helper._remove_roles(member, all_clan_roles)
        # If tag is not saved or connecion to CR server is not available use current name to determine ign
        tag = self.tags.getTag(member.id)
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
                leagues = await self.discord_helper.clanwarReadiness(player_data.cards)
            # REMINDER: Order is important. RequestError is base exception class.
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
            embed.set_footer(text=credits, icon_url=creditIcon)
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
                        card_key = await self.constants.card_to_key(card)
                        emoji = ""
                        if card_key:
                            emoji = self.discord_helper.emoji(card_key)
                        if emoji == "":
                            emoji = self.discord_helper.emoji(card)
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
                embed.set_footer(text=credits, icon_url=creditIcon)
                groups = list(self.discord_helper.grouper(leagues[league]["cards"], 15))

                for index, group in enumerate(groups):
                    value = []
                    for card in group:
                        if card is not None:
                            card_key = await self.constants.card_to_key(card)
                            emoji = ""
                            if card_key:
                                emoji = self.discord_helper.emoji(card_key)
                            if emoji == "":
                                emoji = self.discord_helper.emoji(card)
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


class Helper:
    def __init__(self, bot):
        self.bot = bot
        self.constants = self.bot.get_cog("ClashRoyaleTools").constants

    @staticmethod
    async def getUserCount(guild: discord.Guild, name: str):
        """Returns the numbers of people with the member role"""
        role = discord.utils.get(guild.roles, name=name)
        return len(role.members)

    @staticmethod
    async def _add_roles(member: discord.Member, role_names: List[str]):
        """Add roles"""
        roles = [
            discord.utils.get(member.guild.roles, name=role_name)
            for role_name in role_names
        ]
        if any([x is None for x in roles]):
            raise InvalidRole
        try:
            await member.add_roles(*roles)
        except discord.Forbidden:
            raise
        except discord.HTTPException:
            raise

    @staticmethod
    async def _remove_roles(member: discord.Member, role_names: List[str]):
        """Remove roles"""
        roles = [
            discord.utils.get(member.guild.roles, name=role_name)
            for role_name in role_names
        ]
        roles = [r for r in roles if r is not None]
        try:
            await member.remove_roles(*roles)
        except e:
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

    async def clanwarReadiness(self, cards):
        """Calculate clanwar readiness"""
        readiness = {}
        leagueLevels = {"legendary": 12, "gold": 11, "silver": 10, "bronze": 9}

        for league in leagueLevels.keys():
            readiness[league] = {
                "name": league.capitalize(),
                "percent": 0,
                "cards": [],
                "levels": str(leagueLevels[league]),
            }
            for card in cards:
                if await self.constants.get_new_level(card) >= leagueLevels[league]:
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

    async def getBestLeague(self, cards):
        """Get best leagues using readiness"""
        readiness = await self.clanwarReadiness(cards)

        legend = readiness["legendary"]["percent"]
        gold = readiness["gold"]["percent"] - legend
        silver = readiness["silver"]["percent"] - gold - legend
        bronze = readiness["bronze"]["percent"] - silver - gold - legend

        readinessCount = {
            "legendary": legend,
            "gold": gold,
            "silver": silver,
            "bronze": bronze,
        }
        max_key = max(readinessCount, key=lambda k: readinessCount[k])

        return "{} League ({}%)".format(
            max_key.capitalize(), readiness[max_key]["percent"]
        )
