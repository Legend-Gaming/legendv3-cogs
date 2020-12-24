import asyncio
from collections import namedtuple
import json
import logging
import random
import string
from typing import List, Optional, Literal, Union

import clashroyale
import discord
from discord.ext.commands.errors import BadArgument
from redbot.core import checks, commands
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils.chat_formatting import humanize_list, pagify
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.predicates import MessagePredicate

from crtoolsdb.crtoolsdb import Constants
from .helper import InvalidRole, Helper
from clashroyaleclansv2 import ClashRoyaleClans2
from crtoolsdb import ClashRoyaleTools

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]
credits = "Bot by Legend Gaming"
credits_icon = "https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1"
author = "Legend family clans"
family_name = "Legend"
family_url = "http://royaleapi.com/clan/family/legend"
log = logging.getLogger("red.cogs.clashroyaleclans")

CRClansData = namedtuple('CRClansData', ["clankey", "clan", "waiting", "requirements"])
CRClansDescription = (
    "Our Family is made up of {} "
    "clans with a total of {} "
    "members. We have {} spots left "
    "and {} members in waiting lists.\n"
)

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


class NoToken(Exception):
    pass


class CogNotFound(Exception):
    pass


class PlayerTag(discord.ext.commands.Converter):
    def __str__(self):
        return self.tag

    async def convert(self, ctx, tag: str):
        self.tag = None
        tag = tag.strip("#").upper().replace("O", "0")
        allowed = "0289PYLQGRJCUV"
        if len(tag[3:]) < 3:
            raise discord.CommandError(
                f"Member {tag} not found.\n{tag} is not a valid tag."
            )
        for c in tag[3:]:
            if c not in allowed:
                raise discord.CommandError(
                    f"Member {tag} not found.\n{tag} is not a valid tag."
                )
        self.tag = tag
        return self


class Recruitment(commands.Cog):
    """
    Recruitment helper for clash royale
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot

        self.crtools_cog: ClashRoyaleTools = self.bot.get_cog("ClashRoyaleTools")
        if not self.crtools_cog:
            # Allow loading cog even if db server is down
            log.error("Cog clashroyaletools is not loaded. Some functions may not work.")

        # TODO: Use get_cog
        self.crclans_cog: ClashRoyaleClans2 = self.bot.get_cog("ClashRoyaleClans2")
        if not self.crclans_cog:
            raise CogNotFound("Cog clashroyaleclans is not found. It is critical to have cog loaded.")

        self.tags = getattr(self.crtools_cog, "tags", None)
        self.constants = Constants()

        self.config = Config.get_conf(
            self,
            identifier=932473985763,
            force_registration=True,
        )
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
            "player_info_crclans": True,
            "hyperlink_crclans": False,
        }
        self.config.register_guild(**default_guild)
        self.discord_helper = Helper(bot)

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

        self.token_task = self.bot.loop.create_task(self.init_clash())
        self.last_updated = None

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    async def init_clash(self):
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
        if self.token_task:
            self.token_task.cancel()
        if self.clash:
            self.bot.loop.create_task(self.clash.close())

    async def check_member_eligibility(self, clankey: str, player):
        clankey = self.crclans_cog.get_static_clankey(clankey)
        if clankey is None:
            raise BadArgument("Invalid clankey passed to check_requirement.")
        static_clan_data = self.crclans_cog.get_static_clandata(clankey)
        clan_data = await self.crclans_cog.clan_data(clankey)
        cwr_fulfilled = True

        player_trophies = player['trophies']
        player_cards = player['cards']
        player_pb = player['best_trophies']
        player_cwr = await self.discord_helper.clanwar_readiness(
            player_cards
        )
        player_wd_wins = player['warDayWins']

        clan_requirements = static_clan_data['requirements']
        req_pb = clan_requirements.get("personalbest", 0)
        req_wd_wins = clan_requirements.get("wdwins", 0)
        req_cwr = clan_requirements.get(
            "cwr", {"legendary": 0, "gold": 0, "silver": 0, "bronze": 0}
        )
        for league in req_cwr:
            if req_cwr[league] > 0:
                if player_cwr[league]["percent"] < req_cwr[league]:
                    return False
        if (
            (
                (player_trophies < clan_data["required_trophies"])
                or (player_pb < req_pb)
                or (clan_data["type"] == "closed")
                or (player_wd_wins < req_wd_wins)
            )
        ):
            return False
        return True

    async def crclans_footer(self, player):
        embed=discord.Embed(
            color=0xFAA61A,
            description=(
                "Hello **{}**, above are all the clans "
                "you are allowed to join, based on your statistics. "
                "Which clan would you like to join? \n\n"
                "**Name:** {} ({})\n**Trophies:** {}/{}\n"
                "**CW Readiness:** {}\n"
                "**Max Challenge Wins:** {}\n"
                "**Clan:** {}\n\n"
                ":warning: **YOU WILL BE REJECTED "
                "IF YOU JOIN ANY CLAN WITHOUT "
                "APPROVAL**".format(
                    player["name"],
                    player["name"],
                    player["tag"],
                    player['trophies'],
                    player['best_trophies'],
                    await self.discord_helper.get_best_league(player['cards']),
                    player.get('warDayWins', 0),
                    player.get("clan", {}).get("name", "None"),
                )
            )
        )
        return embed

    async def crclans_title(self, ctx, req_data: CRClansData):
        clan = req_data.clan
        waiting = req_data.waiting
        clan_requirements = req_data.requirements

        req_pb = clan_requirements.get("personalbest", 0)
        req_cwr = clan_requirements.get(
            "cwr",
            {"legendary": 0, "gold": 0, "silver": 0, "bronze": 0}
        )
        req_bonus_str = clan_requirements.get("bonus", "")
        req_wd_wins = clan_requirements.get("wdwins", 0)
        num_waiting = len(waiting)

        # Prepare title
        if num_waiting > 0:
            title = f"[{str(num_waiting)} Waiting] "
        else:
            title = ""
        if str(clan.get("type")) != "inviteOnly":
            title += f"[{str(clan.get('type')).title()}] "
        use_hyperlink = await self.config.guild(ctx.guild).hyperlink_crclans()
        if use_hyperlink:
            url = f"https://royaleapi.com/clan/{clan['tag'].strip('#')}"
            title += "[{} ({})]({}) ".format(clan["name"], clan["tag"], url)
        else:
            title += f"{clan['name']} ({clan['tag']}) "
        if req_pb > 0:
            title += f"PB: {str(req_pb)}+  "
        for league in req_cwr:
            if req_cwr[league] > 0:
                title += "{}: {}%  ".format(
                    league[:1].capitalize(), req_cwr[league]
                )
        if req_wd_wins > 0:
            title += "{}+ War Day Wins ".format(req_wd_wins)
        if req_bonus_str is not None:
            title += req_bonus_str
        return title

    async def crclans_description(self, ctx, req_data: CRClansData):
        clankey = req_data.clankey
        clan = req_data.clan

        emoji_name = self.crclans_cog.get_static_clandata(clankey, "emoji")
        emoji = self.discord_helper.emoji(emoji_name)
        member_count = clan['members']
        if member_count < 50:
            shown_members = str(member_count) + "/50"
        else:
            shown_members = "**FULL** "
        spacing = " \u200b \u200b \u200b \u200b  "
        desc = "{} \u200b {} {} {} \u200b {}+ {} {} \u200b {} {} {} \u200b {}".format(
            emoji,
            shown_members,
            spacing,
            self.discord_helper.emoji("PB"),
            clan["required_trophies"],
            spacing,
            self.discord_helper.getLeagueEmoji(clan["clan_war_trophies"]),
            clan["clan_war_trophies"],
            spacing,
            self.discord_helper.emoji("crtrophy"),
            clan["clan_score"],
        )
        return desc

    @commands.command(name="crclans")
    async def command_crclans(
        self,
        ctx: commands.Context,
        member: Union[discord.Member, PlayerTag, None] = None,
        account: Optional[int] = 1,
        orderByMemberCount: bool = False,
    ):
        """
        Show all family clans.
        Can also show clans based on a member's stats
        """
        player_tag = None
        player = None
        async with ctx.channel.typing():
            if (
                    (isinstance(member, discord.member.Member)
                    or isinstance(member, discord.Member))
                    and player_tag is None
                ):
                try:
                    player_tag = self.tags.getTag(member.id, account)
                    if player_tag is None:
                        await ctx.send(
                            "You must associate a tag with this member first using "
                            "``{}save #tag @member``".format(ctx.prefix)
                        )
                        return
                except AttributeError as e:
                    log.exception("Attribute Error in crclans.", exc_info=e)
                    await ctx.send(
                        "Cannot connect to database. Please notify the devs."
                    )
                    return
            elif isinstance(member, PlayerTag):
                player_tag = str(member)
        if player_tag:
            try:
                player = await self.clash.get_player(player_tag)
            except AttributeError as e:
                log.exception("Attribute Error in crclans.", exc_info=e)
                await ctx.send(
                    "Cannot connect to database. Please notify the devs."
                )
                return
            except clashroyale.NotFoundError:
                return await ctx.send("Player tag is invalid.")
            except clashroyale.RequestError as e:
                log.exception("Request Error in crclans.", exc_info=e)
                await simple_embed(
                    ctx,
                    "Error: cannot reach Clash Royale Servers. Please try again later.",
                )
                return
        embed = discord.Embed(color=0xFAA61A)
        embed.set_author(
            name=author,
            url=family_url,
            icon_url=credits_icon,
        )
        embed.set_footer(text=credits, icon_url=credits_icon)
        found_clan = False
        total_members = 0
        total_waiting = 0
        if orderByMemberCount:
            sortKey = lambda x: (
                        x[1]["members"],
                        x[1]["clan_war_trophies"],
                        x[1]["required_trophies"],
                        x[1]["clan_score"],
                    )
            all_clans = await self.crclans_cog.all_clans_data(sortKey, False)
        else:
            all_clans = await self.crclans_cog.all_clans_data()
        use_hyperlink = await self.config.guild(ctx.guild).hyperlink_crclans()
        description_clan = ""
        for clankey, clan in all_clans.items():
            if player_tag is None or await self.check_member_eligibility(clankey, player=player):
                found_clan = True
                clan_requirements = self.crclans_cog.get_static_clandata(clankey, "requirements")
                waiting = self.crclans_cog.get_static_clandata(clankey, "waiting")
                member_count = clan["members"]
                total_members += member_count
                num_waiting = len(waiting)
                total_waiting += num_waiting
                req_fields = CRClansData(clankey, clan, waiting, clan_requirements)
                # Prepare title
                title = await self.crclans_title(ctx, req_fields)
                desc = await self.crclans_description(ctx, req_fields)
                if use_hyperlink:
                    description_clan += f"**{title}**\n{desc}\n"
                else:
                    embed.add_field(name=title, value=desc, inline=False)
        description = (
            CRClansDescription.format(
            len(all_clans),
            total_members,
            (len(all_clans) * 50) - total_members,
            total_waiting,
            )
        ) + description_clan
        if not found_clan:
            embed.add_field(
                name="uh oh!",
                value="There are no clans available for you at the moment, "
                "please type {}{} to see all clans.".format(ctx.prefix, ctx.command.name),
                inline=False,
            )
        embed.description = description
        try:
            await ctx.send(embed=embed)
        except discord.HTTPException as e:
            if use_hyperlink:
                await self.config.guild(ctx.guild).hyperlink_crclans.set(False)
                await ctx.invoke(ctx.command, member=member, account=account)
                await self.config.guild(ctx.guild).hyperlink_crclans.set(True)
                return
            else:
                await ctx.send("Failed to send embed message")
                log.exception("Exeception when sending embed from crclans.", exc_info=e)
                return

        if player_tag:
            show_playerinfo = await self.config.guild(
                ctx.guild
            ).player_info_crclans()
            if not show_playerinfo:
                return await ctx.send(
                    embed=discord.Embed(
                        color=0xFAA61A,
                        description=":warning: **YOU WILL BE REJECTED IF YOU JOIN ANY CLAN WITHOUT APPROVAL**",
                    )
                )
            return await ctx.send(
                embed=await self.crclans_footer(player)
            )

    @commands.command(name="mcrclans")
    async def command_mcrclans(
        self,
        ctx: commands.Context,
        member: Union[discord.Member, PlayerTag, None] = None,
        account: Optional[int] = 1,
    ):
        await ctx.invoke(self.bot.get_command('crclans'), member=member, account=account, orderByMemberCount=True);
    
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
        clan_info = await self.crclans_cog.clan_data(clankey)
        clan_role = self.crclans_cog.get_static_clandata(clankey, "clanrole")
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
            ign = player_data.name
            if player_data.clan is None:
                is_in_clan = False
                player_clantag = ""
            else:
                player_clantag = player_data.clan.tag.strip("#")
        # REMINDER: Order is important. RequestError is base exception class.
        except AttributeError:
            await ctx.send("Cannot connect to database. Please notify the devs.")
            return
        except clashroyale.NotFoundError:
            await ctx.send("Player tag is invalid.")
            return
        except clashroyale.RequestError:
            await simple_embed(
                ctx, "Error: cannot reach Clash Royale Servers. Please try again later."
            )
            return
        membership = player_clantag in self.crclans_cog.clan_tags()
        if not membership:
            if clan_info.get("members") == 50:
                await simple_embed(
                    ctx, "Approval failed, the clan is Full.", False
                )
                return
            if not await self.check_member_eligibility(clankey, player_data):
                await simple_embed(ctx, "Approval failed, player does not meet requirements for the clan.")
                return
            if clan_info["type"] == "closed":
                await simple_embed(
                    ctx, "Approval failed, the clan is currently closed.", False
                )
            if self.crclans_cog.get_static_clandata(clankey, "requirements")["private"]:
                if clan_role not in [y.name for y in ctx.author.roles]:
                    return await simple_embed(
                        ctx,
                        "Approval failed, only {} staff can approve new recruits for this clan.".format(
                            clan_info["name"]
                        ),
                        False,
                    )

            await self.crclans_cog.remove_waiting_member(clankey, member.id)
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
                    f"[{clan_info['name']} ({clan_info['tag']})](https://link.clashroyale.com/?clanInfo?id={clan_info['tag']})."
                    "\n\n"
                    f"Your **RECRUIT CODE** is: ``{recruit_code}`` \n\n"
                    f"Click [here](https://link.clashroyale.com/?clanInfo?id={clan_info['tag'].strip('#')}) "
                    f"or search for {clan_info['tag']} in-game.\n"
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
                        + clan_info["name"]
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
                embed.add_field(name="Clan", value=clan_info["name"], inline=True)
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
                for name, data in self.crclans_cog.get_all_static_clan_data().items():
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
            clan_roles.append("Clash Royale")
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
                    "DM Legend ModMail, <@598662722821029888> if you have any problems.\n"
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

    @commands.command(name="inactive")
    async def command_inactive(self, ctx, member: discord.Member):
        all_clan_roles = self.crclans_cog.clan_roles()
        member_roles = set(member.roles)
        # TODO: Refactor into get nickname
        try:
            tag = self.tags.getTag(member.id)
        except AttributeError as e:
            log.exception("Attribute Error in inactive.", exc_info=e)
            await ctx.send("Cannot connect to database. Please notify the devs.")
            return
        if tag is None:
            await ctx.send("Player's tag is not saved. Please use `{}crtools save` to save tag.".format(ctx.prefix))
            return
        try:
            new_nickname = (await self.clash.get_player(tag)).name
        except clashroyale.NotFoundError:
            await ctx.send("Player tag is invalid.")
            return
        except clashroyale.RequestError as e:
            log.exception("Request Error in inactive.", exc_info=e)
            await simple_embed(
                ctx,
                "Error: cannot reach Clash Royale Servers. Please try again later.",
            )
            return
        try:
            await member.edit(nick=new_nickname)
        except discord.Forbidden:
            await simple_embed(
                ctx, "I don't have permission to change nick for this user.", False
            )
        await self.discord_helper._remove_roles(
            member, all_clan_roles, reason="used inactive"
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
        self, ctx: commands.Context, member: Union[discord.Member, PlayerTag, None] = None, account: int = 1
    ):
        """View yours or other's clash royale CWR"""
        player_tag = None
        async with ctx.channel.typing():
            if member is None:
                member = ctx.author
            if (
                    (isinstance(member, discord.member.Member)
                    or isinstance(member, discord.Member))
                    and player_tag is None
                ):
                try:
                    player_tag = self.tags.getTag(member.id, account)
                    if player_tag is None:
                        await ctx.send(
                            "You must associate a tag with this member first using "
                            "``{}save #tag @member``".format(ctx.prefix)
                        )
                        return
                except AttributeError as e:
                    log.exception("Attribute Error in cwr.", exc_info=e)
                    await ctx.send(
                        "Cannot connect to database. Please notify the devs."
                    )
                    return
            elif isinstance(member, PlayerTag):
                player_tag = str(member)

        pages = list()
        try:
            player_data = await self.clash.get_player(player_tag)
        except AttributeError as e:
            log.exception("Attribute Error in cwr.", exc_info=e)
            await ctx.send(
                "Cannot connect to database. Please notify the devs."
            )
            return
        except clashroyale.NotFoundError:
            return await ctx.send("Player tag is invalid.")
        except clashroyale.RequestError as e:
            log.exception("Request Error in cwr.", exc_info=e)
            await simple_embed(
                ctx,
                "Error: cannot reach Clash Royale Servers. Please try again later.",
            )
            return
        leagues = await self.discord_helper.clanwar_readiness(player_data.cards)
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
        self, ctx: commands.Context, member: discord.Member, clankey, account: int = 1
    ):
        """Add people to the waiting list for a clan"""
        async with ctx.channel.typing():
            clan_name = self.crclans_cog.get_static_clandata(clankey, "name")
            if clan_name is None:
                return await simple_embed(
                    ctx,
                    "{} is not a valid clankey. Please use a valid clanname:\n{}".format(
                        clankey,
                        humanize_list(list(self.crclans_cog.keys()))
                    ),
                    False,
                )
        try:
            player_tag = self.tags.getTag(member.id, account)
            if player_tag is None:
                await ctx.send(
                    "You must associate a tag with this member first using "
                    "``{}save #tag @member``".format(ctx.prefix)
                )
                return
        except AttributeError as e:
            log.exception("Attribute Error in crclans.", exc_info=e)
            await ctx.send(
                "Cannot connect to database. Please notify the devs."
            )
            return
        try:
            player = await self.clash.get_player(player_tag)
        except AttributeError as e:
            log.exception("Attribute Error in crclans.", exc_info=e)
            await ctx.send(
                "Cannot connect to database. Please notify the devs."
            )
            return
        except clashroyale.NotFoundError:
            return await ctx.send("Player tag is invalid.")
        except clashroyale.RequestError as e:
            log.exception("Request Error in crclans.", exc_info=e)
            await simple_embed(
                ctx,
                "Error: cannot reach Clash Royale Servers. Please try again later.",
            )
            return
        if not await self.check_member_eligibility(clankey, player):
            await simple_embed(ctx, f"Player not not meet all requirements for clan {clankey}")
            return
        if not await self.crclans_cog.add_waiting_member(clankey, member.id):
            await simple_embed(ctx, "Member already in waiting list for clan.")
            return
        clan_role = self.crclans_cog.get_static_clandata(clankey, "clanrole")
        waiting_role = discord.utils.get(ctx.guild.roles, name="Waiting")
        if not waiting_role:
            await simple_embed(ctx, "Cannot find a role named waiting.")
        try:
            if waiting_role:
                await member.add_roles(waiting_role, reason="added to waiting list")
        except discord.Forbidden:
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
                    player["ign"], player_tag, role.mention
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
            for clan_name, clan_data in self.crclans_cog.static_clandata.items():
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
                name=f"{family_name} Family Waiting List",
                icon_url=family_url,
            )
            embed.set_footer(text=credits, icon_url=credits_icon)
            return await ctx.send(embed=embed)

    @waiting.command(name="remove")
    @checks.mod()
    async def waiting_remove(
        self, ctx: commands.Context, member: discord.Member, clankey, account: int = 1
    ):
        """Delete people from the waiting list for a clan"""
        if not await self.crclans_cog.remove_waiting_member(clankey, member.id):
            await simple_embed(ctx, "Member not found in waiting list.")
            return
        await ctx.send(
            (
                f"{member.mention} has been removed from the waiting list for **{clankey}**."
            ),
            allowed_mentions=discord.AllowedMentions(users=True),
        )
        waiting_role = discord.utils.get(ctx.guild.roles, name="Waiting")
        if not waiting_role:
            await simple_embed(ctx, "Cannot find a role named waiting.")
        if waiting_role:
            await member.remove_roles(
                waiting_role, reason="removing from waitlist"
            )
        await ctx.tick()

    @commands.group(name="recruitmentset")
    @commands.guild_only()
    @checks.admin()
    async def recruitmentset(self, ctx: commands.Context):
        """ Set variables used by ClashRoylaleClans cog """
        pass

    @recruitmentset.command(name="showsettings")
    async def recruitmentset_settings(self, ctx: commands.Context):
        msg = ""
        msg += "Mentions:\n"
        mentions = await self.config.guild(ctx.guild).mentions()
        for key, data in mentions.items():
            msg += f"\u200b \u200b {key}: {data}\n"

        data = await self.config.guild(ctx.guild).global_channel_id()
        data = self.bot.get_channel(data) if data else None
        msg += f"Global channel: {str(data.mention) if data else 'None'}\n"

        data = await self.config.guild(ctx.guild).new_recruits_channel_id()
        data = self.bot.get_channel(data) if data else None
        data = self.bot.get_channel(data) if data else None
        msg += f"New recruits channel: {str(data.mention) if data else 'None'}\n"

        data = await self.config.guild(ctx.guild).player_info_crclans()
        msg += f"Show player info after crclans: {str(data)}\n"

        data = await self.config.guild(ctx.guild).hyperlink_crclans()
        msg += f"Show hyperlink in crclans: {str(data)}\n"
        await simple_embed(ctx, msg, True)

    @recruitmentset.group(name="clanmention")
    async def recruitmentset_clanmention(self, ctx):
        """ Set whether clan will be mentioned """
        pass

    @recruitmentset_clanmention.command(name="nm")
    async def recruitmentset_clanmention_nm(self, ctx: commands.Context, value: bool = None):
        """ Set whether clan will be mentioned on successful newmember """
        if value is None:
            value = not await self.config.guild(ctx.guild).mentions.on_nm()
        await self.config.guild(ctx.guild).mentions.on_nm.set(value)
        await ctx.tick()

    @recruitmentset_clanmention.command(name="waiting")
    async def recruitmentset_clanmention_waiting(self, ctx: commands.Context, value: bool = None):
        """ Set whether clan will be mentioned on successful addition to waiting list """
        if value is None:
            value = not await self.config.guild(ctx.guild).mentions.on_waitlist_add()
        await self.config.guild(ctx.guild).mentions.on_waitlist_add.set(value)
        await ctx.tick()

    @recruitmentset_clanmention.command(name="newrecruit")
    async def recruitmentset_clanmention_newrecruit(self, ctx: commands.Context, value: bool = None):
        """ Set whether clan will be mentioned when recruit is approved """
        if value is None:
            value = not await self.config.guild(ctx.guild).mentions.on_newrecruit()
        await self.config.guild(ctx.guild).mentions.on_newrecruit.set(value)
        await ctx.tick()

    @recruitmentset.command(name="global")
    async def recruitmentset_global(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """ Set channel used to welcome newly recruited members """
        if channel:
            channel = channel.id
        await self.config.guild(ctx.guild).global_channel_id.set(channel)
        await ctx.send(f"Set new global channel to: {channel.mention if channel else 'None'}")
        await ctx.tick()

    @recruitmentset.command(name="newrecruits")
    async def recruitmentset_newrecruits(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """ Set channel used to inform staff about new recruits """
        if channel:
            channel = channel.id
        await self.config.guild(ctx.guild).new_recruits_channel_id.set(channel)
        await ctx.send(f"Set new recruits channel to: {channel.mention if channel else 'None'}")
        await ctx.tick()

    @recruitmentset.command(name="playerinfo")
    async def recruitmentset_playerinfo(self, ctx: commands.Context, value: bool = None):
        """ Set if player info is shown in output of crclans """
        if value is None:
            value = not await self.config.guild(ctx.guild).player_info_crclans()
        await self.config.guild(ctx.guild).player_info_crclans.set(value)
        await ctx.send(f"Set show player info to: {value}")
        await ctx.tick()

    @recruitmentset.command(name="hyperlink")
    async def recruitmentset_hyperlink(self, ctx: commands.Context, value: bool = None):
        """ Set if hyperlink is used where possible """
        if value is None:
            value = not await self.config.guild(ctx.guild).hyperlink_crclans()
        await self.config.guild(ctx.guild).hyperlink_crclans.set(value)
        await ctx.send(f"Set hyperlink to: {value}")
        await ctx.tick()

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
