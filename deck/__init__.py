from .deck import Deck


async def setup(bot):
    cog = Deck(bot=bot)
    bot.add_cog(cog)
