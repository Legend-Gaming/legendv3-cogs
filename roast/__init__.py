from .roast import Roast
from redbot.core import data_manager

def setup(bot):
    cog = Roast(bot)
    data_manager.load_bundled_data(cog, 'roasts.txt')
    bot.add_cog(cog)
