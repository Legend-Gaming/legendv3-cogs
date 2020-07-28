from .crtoolsdb import ClashRoyaleTools
from redbot.core import data_manager


async def setup(bot):
    cog = ClashRoyaleTools(bot=bot)
    await cog.crtoken()
    data_manager.load_bundled_data(cog, 'constants.json')
    bot.add_cog(cog)
