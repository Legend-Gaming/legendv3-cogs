from .legendesports import LegendEsports

async def setup(bot):
    cog = LegendEsports(bot=bot)
    await cog.crtoken()
    bot.add_cog(cog) 