from .riverrace import RiverRace

def setup(bot):
    cog = RiverRace(bot)
    bot.add_cog(cog)