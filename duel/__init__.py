from .duel import Duel

def setup(bot):
    cog = Duel(bot)
    bot.add_cog(cog)