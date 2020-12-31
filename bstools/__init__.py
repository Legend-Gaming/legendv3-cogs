from .bstools import BSTools

def setup(bot):
    cog = BSTools(bot)
    bot.add_cog(cog)
