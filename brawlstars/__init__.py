from .brawlstars import BrawlStars

async def setup(bot):
    cog = BrawlStars(bot)
    await cog.api_init()
    bot.add_cog(cog)
