import asyncio
from datetime import datetime
import json
import os
import logging
import random
import string
from typing import Optional

import discord
import clashroyale
from redbot.core import commands, checks, Config
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils.chat_formatting import humanize_list

credits = "Bot by Legend Gaming"
creditIcon = "https://cdn.discordapp.com/emojis/402178957509918720.png?v=1"

log = logging.getLogger("red.cogs.clashroyaleclans")

async def smart_embed(ctx, message, success=None):
    if success is True:
        colour = discord.Colour.dark_green()
    elif success is False:
        colour = discord.Colour.dark_red()
    else:
        colour = await discord.Colour.blue()
    return await ctx.send(embed=discord.Embed(description=message, color=colour))


class ClashRoyaleClans(commands.Cog):
    """Commands for Clash Royale Family Management"""

    def __init__(self, bot):
        self.bot = bot
        self.tags = self.bot.get_cog('ClashRoyaleTools').tags
        self.constants = self.bot.get_cog('ClashRoyaleTools').constants
        self.config = Config.get_conf(self, identifier=2286464642345664456)
        default_global = {"clans": list()}
        self.config.register_global(**default_global)
        self.claninfo_path = str(bundled_data_path(self) / "clans.json")
        with open(self.claninfo_path) as file:
            self.family_clans = dict(json.load(file))
        self.bot.loop.create_task(self.refresh_data())

    async def crtoken(self):
        # Clash Royale API
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token['token'] is None:
            print("CR Token is not SET. Use !set api clashroyale token,YOUR_TOKEN to set it")
        self.cr = clashroyale.official_api.Client(token=token['token'],
                                                  is_async=True,
                                                  url="https://proxy.royaleapi.dev/v1")


    @commands.command(name="legend")
    async def command_legend(self, ctx, member: Optional[discord.Member] = None, account:int = 1):
        """ Show Legend clans, can also show clans based on a member's trophies"""
        if member is None:
            # Show all clans
            player_trophies = 9999
            player_maxtrophies = 9999
            player_cwr = {"legend": 0, "gold": 0, "silver": 0, "bronze": 0}
        else:
            try:
                player_tag = self.tags.getTag(member.id, account)
                if player_tag is None:
                    await ctx.send(
                        "You must associate a tag with this member first using ``{}save #tag @member``".format(
                            ctx.prefix))
                    return
                player_data = await self.cr.get_player(player_tag)
                player_trophies = player_data.trophies
                player_cards = player_data.cards
                player_maxtrophies = player_data.best_trophies
                player_maxwins = player_data.challenge_max_wins
                player_cwr = await self.clanwarReadiness(player_cards)

                if player_data.clan is None:
                    player_clanname = "*None*"
                else:
                    player_clanname = player_data.clan.name

                ign = player_data.name
            except clashroyale.RequestError:
                return await ctx.send("Error: cannot reach Clash Royale Servers. Please try again later.")

        embed = discord.Embed(color=0xFAA61A)
        embed.set_author(name="Legend Family Clans",
                         url="http://royaleapi.com/clan/family/legend",
                         icon_url="https://i.imgur.com/dtSMITE.jpg")

        embed.set_footer(text=credits, icon_url=creditIcon)

        found_clan = False
        total_members = 0
        total_waiting = 0
        clans = await self.config.clans()
        if clans is None or len(clans) == 0:
            return await ctx.send("Use `{}refresh` to get clan data.".format(ctx.prefix))
        for clan in clans:
            cwr_fulfilled = True
            clan_name = clan["name"]
            clan_requirements = self.family_clans.get("requirements", dict())
            waiting = clan_requirements.get("waiting", list())
            num_waiting = len(waiting)
            pb = clan_requirements.get('personalbest', 0)
            cwr = clan_requirements.get('cwr', {"legend": 0, "gold": 0, "silver": 0, "bronze": 0})
            bonus = clan_requirements.get('bonus', "")
            emoji = self.family_clans[clan_name].get('emoji', "")
            total_waiting += num_waiting

            if num_waiting > 0:
                title = "[" + str(num_waiting) + " Waiting] "
            else:
                title = ""

            member_count = clan.get("members")
            total_members += member_count

            if member_count < 50:
                shown_members = str(member_count) + "/50"
            else:
                shown_members = "**FULL**  "

            if str(clan.get("type")) != 'inviteOnly':
                title += f"[{str(clan.get('type')).title()}] "

            title += f"{clan['name']}({clan['tag']}) "

            if pb > 0:
                title += f"PB: {str(pb)}+  "

            for league in cwr:
                if cwr[league] > 0:
                    title += "{}: {}%  ".format(league[:1].capitalize(), cwr[league])
                    if player_cwr[league] < cwr[league]:
                        cwr_fulfilled = False

            if bonus is not None:
                title += bonus

            desc = ("{} {}  🏆 "
                    "{}+  {} {}".format(
                emoji,
                shown_members,
                clan["required_trophies"],
                self.getLeagueEmoji(clan["clan_war_trophies"]),
                clan["clan_war_trophies"]))

            if ((member is None)
                    or ((player_trophies >= clan["required_trophies"] ) and
                        (player_maxtrophies >= pb) and
                        (cwr_fulfilled) and
                        (player_trophies - clan["required_trophies"] < 1200) and
                        (clan["type"] != 'closed')
                    )
                    or ((clan["required_trophies"] < 2000) and
                        (member_count != 50) and
                        (2000 < player_trophies < 4000) and
                        (clan["type"] != 'closed'))
            ):
                found_clan = True
                embed.add_field(name=title, value=desc, inline=False)

        if not found_clan:
            embed.add_field(name="uh oh!",
                            value="There are no clans available for you at the moment, "
                                  "please type !legend to see all clans.",
                            inline=False)

        embed.description = ("Our Family is made up of {} "
                             "clans with a total of {} "
                             "members. We have {} spots left "
                             "and {} members in waiting lists.".format(
            len(clans),
            total_members,
            (len(clans) * 50) - total_members,
            total_waiting
        )
        )
        await ctx.send(embed=embed)

        if member is not None:
            await ctx.send(("Hello **{}**, above are all the clans "
                            "you are allowed to join, based on your statistics. "
                            "Which clan would you like to join? \n\n"
                            "**Name:** {} (#{})\n**Trophies:** {}/{}\n"
                            "**CW Readiness:** {}\n"
                            "**Max Challenge Wins:** {}\n"
                            "**Clan:** {}\n\n"
                            ":warning: **YOU WILL BE REJECTED "
                            "IF YOU JOIN ANY CLAN WITHOUT "
                            "APPROVAL**".format(ign,
                                                ign,
                                                player_tag,
                                                player_trophies,
                                                player_maxtrophies,
                                                await self.getBestLeague(player_cards),
                                                player_maxwins,
                                                player_clanname)))

    async def clanwarReadiness(self, cards):
        """Calculate clanwar readiness"""
        readiness = {}
        leagueLevels = {
            "maxed": 13,
            "legend": 12,
            "gold": 11,
            "silver": 10,
            "bronze": 9
        }

        for league in leagueLevels.keys():
            readiness[league] = 0
            for card in cards:
                if await self.constants.get_new_level(card) >= leagueLevels[league]:
                    print(league, card.name, "\n")
                    readiness[league] += 1
            readiness[league] = int((readiness[league] / len(cards)) * 100)

        return readiness

    def emoji(self, name):
        """Emoji by name."""
        for emoji in self.bot.emojis:
            if emoji.name == name.replace(" ", "").replace("-", "").replace(".", ""):
                return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

    def getLeagueEmoji(self, trophies):
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
            "bronzeleague": [0, 199]
        }
        for league in mapLeagues.keys():
            if mapLeagues[league][0] <= trophies <= mapLeagues[league][1]:
                return self.emoji(league)

    async def getBestLeague(self, cards):
        """Get best leagues using readiness"""
        readiness = await self.clanwarReadiness(cards)

        legend = readiness["legend"]
        gold = readiness["gold"] - legend
        silver = readiness["silver"] - gold - legend
        bronze = readiness["bronze"] - silver - gold - legend

        readinessCount = {"legend": legend, "gold": gold, "silver": silver, "bronze": bronze}
        max_key = max(readinessCount, key=lambda k: readinessCount[k])

        return "{} League ({}%)".format(max_key.capitalize(), readiness[max_key])

    async def refresh_data(self):
        await self.bot.wait_until_red_ready()
        while True:
            with open(self.claninfo_path) as file:
                self.family_clans = dict(json.load(file))
            clan_data = list()
            for k, v in self.family_clans.items():
                try:
                    clan_tag = v["tag"]
                    clan = await self.cr.get_clan(clan_tag)
                    clan_data.append(dict(clan))
                except clashroyale.RequestError:
                    log.error("Error: Cannot reach ClashRoyale Server.")
                except clashroyale.NotFoundError:
                    log.error("Invalid clan tag.")
            clan_data = sorted(
                clan_data,
                key=lambda x: (x["clan_war_trophies"], x["required_trophies"], x["clan_score"]), reverse=True
            )
            log.info("Updated data for all clans at {}.".format(datetime.now().strftime("%m/%d/%Y, %H:%M:%S")))
            await self.config.clans.set(clan_data)
            await asyncio.sleep(300)

    @commands.command(name="refresh")
    async def command_refresh_data(self, ctx):
        with open(self.claninfo_path) as file:
            self.family_clans = dict(json.load(file))
        clan_data = list()
        for k, v in self.family_clans.items():
            try:
                clan_tag = v["tag"]
                clan = await self.cr.get_clan(clan_tag)
                clan_data.append(dict(clan))
            except clashroyale.RequestError:
                log.error("Error: Cannot reach ClashRoyale Server.")
                return await ctx.send("Error: cannot reach Clash Royale Servers. Please try again later.")
            except clashroyale.NotFoundError:
                log.error("Invalid clan tag.")
                return await ctx.send("Invalid Clan Tag. Please try again.")
            else:
                log.info("Updated data for clan {}.".format(k))
        clan_data = sorted(clan_data, key=lambda x: (x["clan_war_trophies"], x["required_trophies"], x["clan_score"]),
                          reverse=True)
        await self.config.clans.set(clan_data)
        log.info("Updated data for all clans at {}.".format(datetime.now().strftime("%m/%d/%Y, %H:%M:%S")))
        await ctx.tick()

    @commands.command(name="approve")
    async def command_approve(self, ctx, member:discord.Member, clankey:str, account:int = 1):
        guild = ctx.guild
        legendServer = ["374596069989810176"]

        # if guild.id not in legendServer:
        #     return await ctx.send("This command can only be executed in the Legend Family Server")

        clankey = clankey.lower()

        valid_keys = [k['nickname'].lower() for k in self.family_clans.values()]
        if clankey not in valid_keys:
            return await smart_embed(ctx, "Please use a valid clanname:\n{}".format(humanize_list(list(valid_keys))), False)

        clan_to_approve = None
        for name, data in self.family_clans.items():
            if data.get('nickname').lower() == clankey:
                clan_to_approve = name
                clan_info = data
        clan_name = clan_info.get("name")
        clan_tag = clan_info.get("tag")
        clan_role = clan_info.get('clanrole')
        clan_pb = clan_info['requirements'].get('personalbest')
        clan_cwr = clan_info['requirements'].get('cwr')
        clan_private = clan_info['requirements'].get('private')
        clan_waiting = clan_info['waiting']
        clan_wdwins = clan_info["requirements"].get("wdwins")

        is_in_clan = True
        try:

            player_tag = self.tags.getTag(member.id, account)
            if player_tag is None:
                return await smart_embed(ctx, "You must associate a tag with this member first using ``{}save #tag @member``".format(ctx.prefix), False)
            player_data = await self.cr.get_player(player_tag)
            clan_data = await self.cr.get_clan(clan_tag)

            ign = player_data.name
            if player_data.clan is None:
                is_in_clan = False
                player_clantag = ""
            else:
                player_clantag = player_data.clan.tag.strip("#")
        except clashroyale.RequestError:
            return await smart_embed(ctx, "Error: cannot reach Clash Royale Servers. Please try again later.")

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
            player_cwr = await self.clanwarReadiness(cards)
            if (clan_data.get("members") == 50):
                return await smart_embed(ctx, "Approval failed, the clan is Full.", False)

            if ((trophies < clan_data.required_trophies) or (maxtrophies < clan_pb)):
                return await smart_embed(ctx, "Approval failed, you don't meet the trophy requirements.", False)

            cwr_met = True
            for league in clan_cwr:
                if clan_cwr[league] > 0:
                    if player_cwr[league] < clan_cwr[league]:
                        cwr_met = False
            if (not cwr_met):
                return await smart_embed(ctx, "Approval failed, you don't meet the CW Readiness requirements.", False)

            if player_wd_wins < clan_wdwins:
                return await smart_embed(ctx, "Approval failed, you don't meet requirements for war day wins.", False)

            if (clan_data.type == "closed"):
                return await smart_embed(ctx, "Approval failed, the clan is currently closed.", False)

            if clan_private:
                if clan_role not in [y.name for y in ctx.author.roles]:
                    return await smart_embed(ctx, "Approval failed, only {} staff can approve new recruits for this clan.".format(clan_name), False)


            if is_in_clan:
                warning = ("\n\n:warning: **YOU WILL BE REJECTED "
                           "IF YOU JOIN ANY CLAN WITHOUT "
                           "APPROVAL**")
                await ctx.send(("{} Please leave your current clan now. "
                                    "Your recruit code will arrive in 3 minutes.{}".format(member.mention, warning)))
                await asyncio.sleep(180)

            try:
                recruitCode = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))

                await member.send(embed=discord.Embed(description="Congratulations, You have been approved to join "
                                                    f"[{clan_name} (#{clan_tag})](https://link.clashroyale.com/?clanInfo?id={clan_tag})."
                                                    "\n\n"
                                                    f"Your **RECRUIT CODE** is: ``{recruitCode}`` \n\n"
                                                    f"Click [here](https://link.clashroyale.com/?clanInfo?id={clan_tag}) "
                                                    f"or search for #{clan_tag} in-game.\n"
                                                    "Send a request **using recruit code** above and wait for your clan leadership to accept you. " +
                                                    "It usually takes a few minutes to get accepted, but it may take up to a few hours. \n\n" +
                                                    "**IMPORTANT**: Once your clan leadership has accepted your request, " +
                                                    "let a staff member in discord know that you have been accepted. " +
                                                    "They will then unlock all the member channels for you.",
                                                    color = discord.Colour.blue())
                )
                await ctx.send(member.mention + " has been approved for **" + clan_name + "**. Please check your DM for instructions on how to join.")

                try:
                    newname = ign + " (Approved)"
                    await member.edit(nick=newname)
                except discord.HTTPException:
                    await ctx.send("I don’t have permission to change nick for this user.")

                role_to_ping = discord.utils.get(guild.roles, name=clan_role)

                embed = discord.Embed(color=0x0080ff)
                embed.set_author(name="New Recruit", icon_url="https://i.imgur.com/dtSMITE.jpg")
                embed.add_field(name="Name", value=ign, inline=True)
                embed.add_field(name="Recruit Code", value=recruitCode, inline=True)
                embed.add_field(name="Clan", value=clan_name, inline=True)
                embed.set_footer(text=credits, icon_url=creditIcon)

                channel = self.bot.get_channel(736892236134088735)  #375839851955748874)
                if channel and role_to_ping:
                    await channel.send(role_to_ping.mention, embed=embed)
                elif not channel:
                    await ctx.send("Cannot find channel. Please contact a dev.")
                elif not role_to_ping:
                    await ctx.send(f"Connot find role {clan_role}")
            except discord.errors.Forbidden:
                await ctx.send("Approval failed, {} please fix your privacy settings, "
                               "we are unable to send you Direct Messages.".format(member.mention)
                )
        else:
            await smart_embed(ctx, "Approval failed, {} is already a part of a clan in the family.".format(member.display_name), False)