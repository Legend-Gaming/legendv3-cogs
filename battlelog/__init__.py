from .battlelog import BattleLog


async def setup(bot):
    cog = BattleLog(bot=bot)
    bot.add_cog(cog)
