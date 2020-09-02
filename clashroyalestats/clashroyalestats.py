import discord
import clashroyale
from redbot.core import commands, checks, Config


class ClashRoyale(commands.Cog):
    """Clash royale commands and functions"""

    def __init__(self, bot):
        self.bot = bot
        self.tags = self.bot.get_cog('ClashRoyaleTools').tags
        self.constants = self.bot.get_cog('ClashRoyaleTools').constants

    async def crtoken(self):
        # Clash Royale API config
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token['token'] is None:
            print("CR Token is not SET. Make sure to have royaleapi ip added (128.128.128.128) Use !set api "
                  "clashroyale token,YOUR_TOKEN to set it")
        self.clash = clashroyale.official_api.Client(token=token['token'], is_async=True,
                                                     url="https://proxy.royaleapi.dev/v1")

    def cog_unload(self):
        if self.clash:
            self.bot.loop.create_task(self.clash.close())

    def getCards(self, maxPlayers):
        """Converts maxPlayers to Cards

        Credit Gr8"""
        cards = {
            "50": 25,
            "100": 100,
            "200": 400,
            "1000": 2000
        }
        return cards[str(maxPlayers)]

    def getArenaEmoji(self, trophies):
        """Get Arena and League Emoji"""
        arenaMap = {
            "arena1": [0, 299],
            "arena2": [300, 599],
            "arena3": [600, 999],
            "arena4": [1000, 1299],
            "arena5": [1300, 1599],
            "arena6": [1600, 1999],
            "arena7": [2000, 2299],
            "arena8": [2300, 2599],
            "arena9": [2600, 2999],
            "arena10": [3000, 3299],
            "arena11": [3300, 3599],
            "arena12": [3600, 3999],
            "league1": [4000, 4299],
            "league2": [4300, 4599],
            "league3": [4600, 4999],
            "league4": [5000, 5299],
            "league5": [5300, 5599],
            "league6": [5500, 5999],
            "arena19": [6000, 6299],
            "league7": [6200, 6699],
            "league8": [6600, 6999],
            "league9": [7000, 99999]
        }
        for arena in arenaMap.keys():
            if arenaMap[arena][0] <= trophies <= arenaMap[arena][1]:
                return self.emoji(arena)

    def getArenaImage(self, trophies):
        """Get Arena and League Emoji"""
        arenaMap = {
            "arena1": [0, 299],
            "arena2": [300, 599],
            "arena3": [600, 999],
            "arena4": [1000, 1299],
            "arena5": [1300, 1599],
            "arena6": [1600, 1999],
            "arena7": [2000, 2299],
            "arena8": [2300, 2599],
            "arena9": [2600, 2999],
            "arena10": [3000, 3299],
            "arena11": [3300, 3599],
            "arena12": [3600, 3999],
            "league1": [4000, 4299],
            "league2": [4300, 4599],
            "league3": [4600, 4999],
            "league4": [5000, 5299],
            "league5": [5300, 5599],
            "league6": [5500, 5999],
            "arena19": [6000, 6299],
            "league7": [6200, 6699],
            "league8": [6600, 6999],
            "league9": [7000, 99999]
        }
        for arena in arenaMap.keys():
            if arenaMap[arena][0] <= trophies <= arenaMap[arena][1]:
                return 'https://royaleapi.github.io/cr-api-assets/arenas/' + arena + '.png'

    def getCoins(self, maxPlayers):
        """Converts maxPlayers to Coins

        credit gr8"""
        coins = {
            "50": 175,
            "100": 700,
            "200": 2800,
            "1000": 14000
        }
        return coins[str(maxPlayers)]

    def emoji(self, name):
        """Emoji by name."""
        name = str(name)
        for emote in self.bot.emojis:
            if emote.name == name.replace(" ", "").replace("-", "").replace(".", ""):
                return '<:{}:{}>'.format(emote.name, emote.id)
        return ''

    def roleNameConverter(self, role):
        """Just makes the role names look better"""
        if role == "leader":
            return "Leader"
        elif role == "coLeader":
            return "Co-Leader"
        elif role == "elder":
            return "Elder"
        else:
            return "Member"

    @commands.command()
    async def clashprofile(self, ctx, user: discord.Member = None, account: int = 1):
        """Show Clash Royale Stats"""

        # todo weird thing !cp accountnum

        if user is None:
            user = ctx.author

        try:
            profiletag = self.tags.getTag(user.id, account)
            if profiletag is None:
                return await ctx.send("You don't have a tag saved. "
                                      "Use !save <tag> to save a tag or that account number doesn't exist,"
                                      " use !accounts to see the accounts you have saved")
            profiledata = await self.clash.get_player(profiletag)
        except clashroyale.RequestError:
            return await ctx.send("Error: cannot reach Clash Royale Servers. Please try again later.")

        ccwins, gcwins = 0, 0

        badges_str = '**Badges:** 2020 Player'

        account_age = 'Indeterminate'

        for badge in profiledata.badges:
            if badge.name == 'Classic12Wins':
                ccwins = badge.progress
            elif badge.name == 'Grand12Wins':
                gcwins = badge.progress
            elif badge.name == 'Played1Year':
                account_age = str(badge.progress)
            elif badge.name == 'Played3Years':
                badges_str += ', OG Clash Royale Player'
            elif badge.name == "LadderTournamentTop1000_1":
                badges_str += ', Top 1000 Global Tournament Finish'
            elif badge.name == "LadderTop1000_1":
                badges_str += ', Top 1000 Ladder Finish'

        if profiletag == '90UVY2J8G':
            badges_str += ', Bot Developer'

        games1v1 = profiledata.battle_count - (profiledata.battle_count - (profiledata.wins + profiledata.losses))

        embed = discord.Embed(color=discord.Color.blue(), description=badges_str)
        embed.set_author(name=profiledata.name + " (" + profiledata.tag + ")",
                         icon_url=await self.constants.get_clan_image(profiledata),
                         url="https://royaleapi.com/player/" + profiledata.tag.strip("#"))
        embed.set_thumbnail(url=self.getArenaImage(profiledata.trophies))

        embed.add_field(name="Trophies",
                        value="{} {:,}".format(self.getArenaEmoji(profiledata.trophies), profiledata.trophies),
                        inline=True)

        # todo proper league stats with formatting (rank if applicable, prev season + best season)

        if getattr(profiledata, 'league_statistics', False):
            if not getattr(profiledata.league_statistics.current_season, 'best_trophies', False):
                season_best = profiledata.league_statistics.current_season.trophies
            else:
                season_best = profiledata.league_statistics.current_season.best_trophies
            embed.add_field(name="Season Best", value='{} {:,}'.format(self.getArenaEmoji(season_best),
                                                                       season_best), inline=True)

        embed.add_field(name="Highest Trophies", value="{} {:,}".format(self.getArenaEmoji(profiledata.best_trophies),
                                                                        profiledata.best_trophies), inline=True)
        level = self.emoji("level{}".format(profiledata.exp_level))
        if level is None or level == '':
            level = str(profiledata.exp_level)

        embed.add_field(name="Level", value=level, inline=True)
        if profiledata.exp_level > 12:
            embed.add_field(name="Star Points",
                            value="{} {:,}".format(self.emoji("starLevel"), profiledata.star_points), inline=True)
        if getattr(profiledata, "clan"):
            embed.add_field(name=f"{self.roleNameConverter(profiledata.role)} of",
                            value=f'{self.emoji("clans")} {profiledata.clan.name}')

        total_cards = await self.clash.get_all_cards()
        total_cards = len(total_cards)
        embed.add_field(name="Cards Found", value="{} {}/{}".format(self.emoji("card"), len(profiledata.cards),
                                                                    str(total_cards)),
                        inline=True)
        embed.add_field(name="Favourite Card", value="{} {}".format(self.emoji(profiledata.current_favourite_card.id),
                                                                    profiledata.current_favourite_card.name),
                        inline=True)
        embed.add_field(name="Games Played", value="{} {:,}".format(self.emoji("battle"), profiledata.battle_count),
                        inline=True)
        embed.add_field(name="Tourney Games Played",
                        value="{} {:,}".format(self.emoji("tourney"), profiledata.tournament_battle_count), inline=True)
        embed.add_field(name="Wins", value="{} {:,} ({:.1f}%)".format(self.emoji("blueCrown"), profiledata.wins,
                                                                      (profiledata.wins / games1v1) * 100), inline=True)
        embed.add_field(name="Losses", value="{} {:,} ({:.1f}%)".format(self.emoji("redCrown"), profiledata.losses,
                                                                        (profiledata.losses / games1v1) * 100),
                        inline=True)
        embed.add_field(name="Three Crown Wins",
                        value="{} {:,} ({:.1f}%)".format(self.emoji("3crown"), profiledata.three_crown_wins, (
                                    profiledata.three_crown_wins / profiledata.battle_count) * 100), inline=True)
        embed.add_field(name="Friendly Wins",
                        value="{} {:,}".format(self.emoji("members"), profiledata.achievements[9].value), inline=True)
        embed.add_field(name="War Day Wins", value="{} {}".format(self.emoji("warwin"), profiledata.war_day_wins),
                        inline=True)
        embed.add_field(name="Total Donations", value="{} {:,}".format(self.emoji("card"), profiledata.total_donations),
                        inline=True)
        embed.add_field(name="Donations Recieved",
                        value="{} {:,}".format(self.emoji("card"), profiledata.clan_cards_collected), inline=True)
        embed.add_field(name="Challenge Max Wins",
                        value="{} {}".format(self.emoji("tourney"), profiledata.challenge_max_wins), inline=True)
        embed.add_field(name="Grand Challenge Wins", value=f'🏅 {gcwins}', inline=True)
        embed.add_field(name="Classic Challenge Wins", value=f'🥈 {ccwins}', inline=True)
        if account_age != "Indeterminate":
            embed.add_field(name="Account Age", value=f'⏰ {account_age}', inline=True)
        embed.add_field(name="Challenge Cards Won",
                        value="{} {:,}".format(self.emoji("cards"), profiledata.challenge_cards_won), inline=True)
        embed.add_field(name="Tournament Cards Won",
                        value="{} {:,}".format(self.emoji("cards"), profiledata.tournament_cards_won), inline=True)
        embed.add_field(name="Hosted/Joined Tourneys",
                        value="{} {:,}/{:,}".format(self.emoji("tourney"), profiledata.achievements[6].value,
                                                    profiledata.achievements[7].value), inline=True)
        embed.add_field(name="Clans Joined",
                        value="{} {:,}".format(self.emoji("clan"), profiledata.achievements[0].value), inline=True)
        embed.set_footer(text="Bot by: Generaleoley | Legend Gaming")

        await ctx.send(embed=embed)

    # @commands.command(aliases=['clashdeck'])
    # async def clashDeck(self, ctx, member: discord.Member = None, account: int = 1):
    #     """View yours or other's clash royale Deck"""
    #
    #     member = member or ctx.message.author
    #
    #     await self.bot.type()
    #
    #     try:
    #         profiletag = self.tags.getTag(member.id, account)
    #         if profiletag is None:
    #             return await ctx.send("You don't have a tag saved. "
    #                                   "Use !save <tag> to save a tag or that account number doesn't exist,"
    #                                   " use !accounts to see the accounts you have saved")
    #         profiledata = await self.clash.get_player(profiletag)
    #     except clashroyaleAPI.RequestError:
    #         return await self.bot.say("Error: cannot reach Clash Royale Servers. Please try again later.")
    #
    #     message = ctx.message
    #     message.content = ctx.prefix + "deck gl " + await self.constants.decklink_url(profiledata.current_deck)
    #     message.author = member
    #
    #     await self.bot.process_commands(message)

