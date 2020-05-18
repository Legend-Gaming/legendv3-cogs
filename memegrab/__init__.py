from .memegrab import MemeGrab


async def setup(bot):
    MemeCog = MemeGrab(bot)
    await MemeCog.check()
    bot.add_cog(MemeCog)
