from .counting import Counting


def setup(bot):
    cog = Counting(bot)
    bot.add_cog(cog)
