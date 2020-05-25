from redbot.core import commands

class Tutorial_Cog(commands.Cog):
    """Minimal tutorial bot"""
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def simple_cog(self, ctx):
        pass

    @simple_cog.command()
    async def hello(self, ctx, *, message):
        """Says something in a text channel"""
        await ctx.send(f"Cog says: Hello World! {message}")


