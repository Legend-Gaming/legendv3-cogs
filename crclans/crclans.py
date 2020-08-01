import discord
import clashroyale
from redbot.core import commands, checks, Config
from redbot.core.data_manager import bundled_data_path
import os
import json

credits = "Bot by Legend Gaming"
creditIcon = "https://cdn.discordapp.com/emojis/402178957509918720.png?v=1"


class ClashRoyaleClans(commands.Cog):
    """Commands for Clash Royale Family Management"""

    def __init__(self, bot):
        self.bot = bot
        self.tags = self.bot.get_cog('ClashRoyaleTools').tags
        self.constants = self.bot.get_cog('ClashRoyaleTools').constants

        # ADDED
        self.config = Config.get_conf(self, identifier=2286464642345664456)
        default_global = {"clans": list()}
        self.config.register_global(**default_global)
        location = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__))
        )
        with open(os.path.join(location, "data/clans.json")) as file:
            self.clan_info = dict(json.load(file))
        # --

    async def crtoken(self):
        # Clash Royale API
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token['token'] is None:
            print("CR Token is not SET. Use !set api clashroyale token,YOUR_TOKEN to set it")
        self.cr = clashroyale.official_api.Client(token=token['token'], is_async=True,
                                                  url="https://proxy.royaleapi.dev/v1")


    @commands.command()
    async def legend(self, ctx, member: discord.Member = None, account=1):
        """ Show Legend clans, can also show clans based on a member's trophies"""
        if member is None:
            # Show all clans
            trophies = 9999
            maxtrophies = 9999
            plyrLeagueCWR = {"legend": 0, "gold": 0, "silver": 0, "bronze": 0}
        else:
            try:
                profiletag = self.tags.getTag(member.id, account)
                if profiletag is None:
                    await ctx.send(
                        "You must associate a tag with this member first using ``{}save #tag @member``".format(
                            ctx.prefix))
                    return
                profiledata = await self.cr.get_player(profiletag)
                trophies = profiledata.trophies
                cards = profiledata.cards
                maxtrophies = profiledata.best_trophies
                maxwins = profiledata.challenge_max_wins
                plyrLeagueCWR = await self.clanwarReadiness(cards)

                if profiledata.clan is None:
                    clanname = "*None*"
                else:
                    clanname = profiledata.clan.name

                ign = profiledata.name
            except clashroyale.RequestError:
                return await ctx.send("Error: cannot reach Clash Royale Servers. Please try again later.")
            except KeyError:
                return await ctx.send(
                    "You must associate a tag with this member first using ``{}save #tag @member``".format(ctx.prefix))

        embed = discord.Embed(color=0xFAA61A)
        embed.set_author(name="Legend Family Clans",
                         url="http://royaleapi.com/clan/family/legend",
                         icon_url="https://i.imgur.com/dtSMITE.jpg")

        embed.set_footer(text=credits, icon_url=creditIcon)

        foundClan = False
        totalMembers = 0
        totalWaiting = 0
        clans = await self.config.clans()
        if clans is None or len(clans) == 0:
            return await ctx.send("Use `{}refresh` to get clan data.".format(ctx.prefix))
        for clan in clans:
            personalbest = 0
            bonustitle = None
            plyrCWRGood = True

            numWaiting = self.clan_info[clan.get("name")].get('numWaiting', 0)
            personalbest = self.clan_info[clan.get("name")].get('personalbest', 0)
            cwr = self.clan_info[clan.get("name")].get('cwr', {"legend": 0, "gold": 0, "silver": 0, "bronze": 0})
            bonustitle = self.clan_info[clan.get("name")].get('bonustitle', None)
            emoji = self.clan_info[clan.get("name")].get('emoji', "")
            totalWaiting += numWaiting

            if numWaiting > 0:
                title = "[" + str(numWaiting) + " Waiting] "
            else:
                title = ""

            member_count = clan.get("members")
            totalMembers += member_count

            if member_count < 50:
                showMembers = str(member_count) + "/50"
            else:
                showMembers = "**FULL**  "

            if str(clan.get("type")) != 'inviteOnly':
                title += "[" + str(clan.get("type")).title() + "] "

            title += clan.get("name") + " (" + clan.get("tag") + ") "

            if personalbest > 0:
                title += "PB: " + str(personalbest) + "+  "

            for league in cwr:
                if cwr[league] > 0:
                    title += "{}: {}%  ".format(league[:1].capitalize(), cwr[league])
                    if plyrLeagueCWR[league] < cwr[league]:
                        plyrCWRGood = False

            if bonustitle is not None:
                title += bonustitle

            desc = ("{} {}  🏆 "
                    "{}+  {} {}".format(
                emoji,
                showMembers,
                clan["required_trophies"],
                self.getLeagueEmoji(clan["clan_war_trophies"]),
                clan["clan_war_trophies"]))

            if (member is None) or ((clan["required_trophies"] <= trophies) and
                                    (maxtrophies > personalbest) and
                                    (plyrCWRGood) and
                                    (trophies - clan["required_trophies"] < 1200) and
                                    (clan["type"] != 'closed')) or ((clan["required_trophies"] < 2000) and
                                                                    (member_count != 50) and
                                                                    (2000 < trophies < 4000) and
                                                                    (clan["type"] != 'closed')):
                foundClan = True
                embed.add_field(name=title, value=desc, inline=False)

        if not foundClan:
            embed.add_field(name="uh oh!",
                            value="There are no clans available for you at the moment, "
                                  "please type !legend to see all clans.",
                            inline=False)

        embed.description = ("Our Family is made up of {} "
                             "clans with a total of {} "
                             "members. We have {} spots left "
                             "and {} members in waiting lists.".format(
            len(clans),
            totalMembers,
            (len(clans) * 50) - totalMembers,
            totalWaiting
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
                                                profiletag,
                                                trophies,
                                                maxtrophies,
                                                await self.getBestLeague(cards),
                                                maxwins,
                                                clanname)))

    async def clanwarReadiness(self, cards):
        """Calculate clanwar readiness"""
        readiness = {}
        leagueLevels = {
            "legend": 12,
            "gold": 11,
            "silver": 10,
            "bronze": 9
        }

        for league in leagueLevels.keys():
            readiness[league] = 0
            for card in cards:
                if await self.constants.get_new_level(card) >= leagueLevels[league]:
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

    @commands.command()
    async def refresh(self, ctx):
        clandata = []
        location = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__))
        )
        with open(os.path.join(location, "data/clans.json")) as file:
            self.clan_info = dict(json.load(file))
        print(os.path.join(location, "data/clans.json"))
        for clankey in (self.clan_info.keys()):
            try:
                await ctx.send(f"Getting data for {clankey}")
                clan_tag = self.clan_info[clankey].get('tag')
                clan = await self.cr.get_clan(clan_tag)
                clandata.append(dict(clan))
            except clashroyale.RequestError:
                return await ctx.send("Error: cannot reach Clash Royale Servers. Please try again later.")
            except clashroyale.NotFoundError:
                return await ctx.send("Invalid Clan Tag. Please try again.")

        clandata = sorted(clandata, key=lambda x: (x["clan_war_trophies"], x["required_trophies"], x["clan_score"]),
                          reverse=True)
        await self.config.clans.set(clandata)

        await ctx.tick()