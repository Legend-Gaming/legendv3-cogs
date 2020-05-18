from redbot.core import commands, Config, bank, checks
import discord
import random

credit = "Bot by Generaleoley | LeGeND eSports"


class fortune(commands.Cog):
    """Basic Fortune Teller"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=987558324)
        default_guild = {'fortunes': ["That is true",
                                      "Possibly false",
                                      "You are completely wrong",
                                      "This is 100% true with a certificate of authenticity",
                                      "No comment",
                                      "Why are you asking me? This is a YOU question...",
                                      ":thinking:",
                                      ":joy: SOOOOOOOOOO FALSE :joy:",
                                      "This is so false that I could search the universe and I wouldn't be able to find truth",
                                      "Are **YOU** Dumb?",
                                      "I don't understand",
                                      "You know how they say there isn't any stupid questions... **WELL YOU JUST PROVED THEM WRONG WITH THAT QUESTION**",
                                      "That is false",
                                      "Leave me alone"],
                         'cost': 1000}
        self.config.register_guild(**default_guild)

    async def good_embed(self, title, description, ctx):
        embed = discord.Embed(color=0x2ecc71, title=title, description=description)
        embed.set_footer(text=credit)
        await ctx.send(embed=embed)

    async def bad_embed(self, title, description, ctx):
        embed = discord.Embed(color=0xe74c3c, title=title, description=description)
        embed.set_footer(text=credit)
        await ctx.send(embed=embed)



    @commands.command()
    async def askbot(self, ctx, *, message):
        """Ask the bot a question"""
        user_bal = int(await bank.get_balance(ctx.author))
        usage_cost = int(await self.config.guild(ctx.guild).cost())
        if user_bal < usage_cost:
            await self.bad_embed("Insufficient Balance",
                                                "You don'have enough credits ask the bot a question. "
                                                "You need {} credits, you have {}".format(str(usage_cost),
                                                                                          str(user_bal)), ctx)
            return

        await bank.withdraw_credits(ctx.author, usage_cost)
        fortunes = await self.config.guild(ctx.guild).fortunes()

        response = random.choice(fortunes)

        await self.good_embed("The Bot has Spoken!", response, ctx)

    @commands.group()
    async def setfortune(self, ctx):
        """Fortune cog configuration"""

    @checks.mod_or_permissions()
    @setfortune.command()
    async def cost(self, ctx, fee: int):
        """Set usage cost"""
        try:
            await self.config.guild(ctx.guild).cost.set(fee)
            await self.good_embed("Success!", "The cost to ask the bot a question is now {}!".format(str(fee)), ctx)
        except Exception as e:
            await self.bad_embed("An Error Occurred!",
                                                "Error message: {} \n Please DM the ModMail bot or report this bug".format(e), ctx)


    @setfortune.command()
    async def info(self, ctx):
        """Get Cog Info"""
        embed = discord.Embed(color=0x2ecc71, title="Fortune Info", description="Values for Fortune Cog")
        cost = await self.config.guild(ctx.guild).cost()
        embed.add_field(name="Cost", value=cost)
        await ctx.send(embed=embed)
