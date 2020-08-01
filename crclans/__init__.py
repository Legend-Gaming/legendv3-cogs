from .crclans import ClashRoyaleClans


async def setup(bot):
    cog = ClashRoyaleClans(bot=bot)
    await cog.crtoken()
    # data_manager.load_bundled_data(cog, 'constants.json')
    bot.add_cog(cog)