from .tutorial_cog import Tutorial_Cog

def setup(bot):
    bot.add_cog(Tutorial_Cog(bot))
