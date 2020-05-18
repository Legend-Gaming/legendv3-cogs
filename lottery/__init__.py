from .lottery import lottery

def setup(bot):
    bot.add_cog(lottery(bot))