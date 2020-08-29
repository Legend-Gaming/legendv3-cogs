from .clashroyaleclans import ClashRoyaleClans


async def setup(bot):
    cog = ClashRoyaleClans(bot=bot)
    # await cog.crtoken()
    # await cog.refresh_data()
    bot.add_cog(cog)
