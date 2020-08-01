from .clashroyalestats import ClashRoyale


async def setup(bot):
    cog = ClashRoyale(bot=bot)
    await cog.crtoken()
    bot.add_cog(cog)
