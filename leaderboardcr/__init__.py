from .leaderboardcr import CRLeaderBoard

def setup(bot):
    cog = CRLeaderBoard(bot=bot)
    await cog.crtoken()
    bot.add_cog(cog)
