from .welcome import Welcome

async def setup(bot):
    cog = Welcome(bot=bot)
    await cog.crtoken()
    bot.add_cog(cog)