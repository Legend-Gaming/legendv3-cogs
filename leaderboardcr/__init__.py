from .leaderboardcr import CRLeaderBoard

def setup(bot):
    cog = CRLeaderBoard(bot=bot)
    bot.add_cog(cog)
