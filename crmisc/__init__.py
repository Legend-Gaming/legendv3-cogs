from .cr import ClashRoyaleCog

async def setup(bot):
  cog = ClashRoyaleCog(bot)
  await cog.initialize()
  bot.add_cog(cog)
