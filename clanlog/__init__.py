from .clanlog import ClanLog

async def setup(bot):
    cog = ClanLog(bot=bot)
    bot.add_cog(cog)
