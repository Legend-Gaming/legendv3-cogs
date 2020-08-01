from .jailed import Jail

async def setup(bot):
    cog = Jail(bot)
    await cog.initialize(bot)
    bot.add_cog(cog)
    
