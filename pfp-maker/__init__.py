from redbot.core import data_manager
from .pfpmaker import PFPMaker

def setup(bot):
    cog = PFPMaker(bot)
    data_manager.load_bundled_data(cog, __file__)
    bot.add_cog(cog)