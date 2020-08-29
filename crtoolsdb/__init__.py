from .crtoolsdb import ClashRoyaleTools
from redbot.core import data_manager


async def setup(bot):
    cog = ClashRoyaleTools(bot=bot)
    # await cog.crtoken()
    bot.add_cog(cog)
