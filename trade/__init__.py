from .trade import Trade

def setup(bot):
    cog = Trade(bot)
    bot.add_cog(cog)
