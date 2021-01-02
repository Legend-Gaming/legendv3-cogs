from .coctools import ClashOfClans


async def setup(bot):
    cog = ClashOfClans(bot=bot)
    await cog.coctoken()
    bot.add_cog(cog)
