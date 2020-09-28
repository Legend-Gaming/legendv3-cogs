from redbot.core import data_manager

from .crtoolsdb import ClashRoyaleTools


async def setup(bot):
    cog = ClashRoyaleTools(bot=bot)
    # await cog.crtoken()
    bot.add_cog(cog)
