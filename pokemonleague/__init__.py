import challonge

from .pokemonleague import PokemonLeague


async def setup(bot):
    cog = PokemonLeague(bot)
    await cog.challongetoken()
    bot.add_cog(cog)
