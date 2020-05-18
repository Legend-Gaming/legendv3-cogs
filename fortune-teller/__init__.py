from .fortuneteller import fortune

def setup(bot):
    bot.add_cog(fortune(bot))