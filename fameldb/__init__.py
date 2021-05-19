from .fameldb import FameLeaderboard

async def setup(bot):
    cog = FameLeaderboard(bot)
    await cog.crtoken()
    bot.add_cog(cog)