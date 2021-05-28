from .nonitroemoji import NonNitroEmoji
def setup(bot):
    cog = NonNitroEmoji(bot=bot)
    bot.add_cog(cog)