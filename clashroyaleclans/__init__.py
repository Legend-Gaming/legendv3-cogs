from .clashroyaleclans import ClashRoyaleClans


async def setup(bot):
    cog = ClashRoyaleClans(bot=bot)
    await cog.crtoken()
    # data_manager.load_bundled_data(cog, 'clans.json')
    bot.add_cog(cog)