from .rep import Reputation

def setup(bot):
    cog = Reputation(bot)
    bot.add_cog(cog)