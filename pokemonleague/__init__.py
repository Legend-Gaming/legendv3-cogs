from .pokemonleague import PokemonLeague


async def setup(bot):
    cog = PokemonLeague(bot)
    bot.add_cog(cog)
