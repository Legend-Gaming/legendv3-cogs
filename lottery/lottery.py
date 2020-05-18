from redbot.core import commands, bank, checks
from redbot.core import Config
import discord
import random
# import time

credit = "Bot by Generaleoley | LeGeND eSports"


class lottery(commands.Cog):
    """Lottery cog"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=437923106)
        default_guild = {"allowed": True,
                         "entry_fee": 10000,
                         "winnings": 250000,
                         "range": 100,
                         "running": False,
                         }
        default_member = {"entered": False,
                          "guess": None
                          }
        self.config.register_guild(**default_guild)
        self.config.register_member(**default_member)

    async def basic_embed(self, ctx, title, description):
        embed = discord.Embed(color=0x2ecc71, title=title, description=description)
        embed.set_footer(text=credit)
        await ctx.send(embed=embed)

    async def bad_embed(self, ctx, title, description):
        embed = discord.Embed(color=0xe74c3c, title=title, description=description)
        embed.set_footer(text=credit)
        await ctx.send(embed=embed)

    @commands.group()
    async def lottery(self, ctx):
        """Main element of lottery"""

    @checks.mod_or_permissions(manage_roles=True)
    @lottery.command(aliases=["start"])
    async def create(self, ctx):
        """Start a lottery"""
        running = await self.config.guild(ctx.guild).running()
        if running is True:
            await self.bad_embed(ctx=ctx, title="Lottery Already Running", description="There is aleadey a lottery running, "
                                                                                 "please "
                                                                            "wait until this one has ended to start "
                                                                                 "a new one")
            return
        await self.config.guild(ctx.guild).running.set(True)
        await self.basic_embed(ctx, "Success!", "Lottery Started! Use `!lottery enter <guess>` to enter!")


    @lottery.command()
    async def info(self, ctx):
        """Gets the lottery setting informations"""
        embed = discord.Embed(color=0x2ecc71, title="Lottery Setting Info",
                              description="The following are the set values for the server")

        allowed = await self.config.guild(ctx.guild).allowed()
        embed.add_field(name='Enabled', value=allowed)

        entry_fee = await self.config.guild(ctx.guild).entry_fee()
        embed.add_field(name='Entry Fee', value=entry_fee)

        winnings = await self.config.guild(ctx.guild).winnings()
        embed.add_field(name='Amount Won', value=winnings)

        range = await self.config.guild(ctx.guild).range()
        embed.add_field(name='Guess Range', value="1 - {}".format(str(range)))

        running = await self.config.guild(ctx.guild).running()
        embed.add_field(name='Lottery Running', value=running)

        embed.set_footer(text=credit)
        await ctx.send(embed=embed)

    @lottery.command()
    async def get(self, ctx):
        """Get your entered guess"""
        guess = await self.config.member(ctx.author).guess()
        if guess is None:
            await self.bad_embed(ctx, "No Guess Entered", "You have not entered a guess, please enter one through"
                                                          " `!lottery enter <guess>`")
            return
        await self.basic_embed(ctx, "Your Guess is:", guess)

    @lottery.command()
    async def enter(self, ctx, guess):
        """Enter into the lottery"""
        fee = await self.config.guild(ctx.guild).entry_fee()
        bal = await bank.get_balance(ctx.author)
        if bal < fee:
            await self.bad_embed(ctx, "Not enough credits", "You have {} credits, you neeed {} to enter."
                                                            " Come back when you have enough money!".format(bal, fee))
            return
        try:
            guess = int(guess)
            running = await self.config.guild(ctx.guild).running()
            range = await self.config.guild(ctx.guild).range()
            range = int(range)
            if running is False:
                await self.bad_embed(ctx=ctx, title="No Lottery Running", description="There is not a lottery running, please "
                                                                                "wait until there is a lottery running")
                return
            if guess is None or int(guess) > int(range) or int(guess) < 1:
                await self.bad_embed(ctx, "Invalid Guess Entered", "Please enter a guess between 1 and {}.".format(range))
                return
            await self.config.member(ctx.author).entered.set(True)
            await self.config.member(ctx.author).guess.set(guess)
            await bank.withdraw_credits(ctx.author, fee)
            await self.basic_embed(ctx, "Success!", "Your guess: **{}** has been recorded".format(guess))
        except TypeError as e:
            await self.bad_embed(ctx, "Invalid Guess", "Please enter a NUMBER between 1 and {} as your guess".format(range))
            print(e)
        except Exception as e:
            await self.bad_embed(ctx, "An Error Occurred",
                                 "Error message: {} \n Please DM the ModMail bot or report this bug".format(e))

    @lottery.command()
    async def edit(self, ctx, guess):
        """Edit your guess for the lottery"""
        try:
            guess = int(guess)
            running = await self.config.guild(ctx.guild).running()
            range = await self.config.guild(ctx.guild).range()
            if running is False:
                await self.bad_embed(ctx=ctx, title="No Lottery Running", description="There is not a lottery running, please "
                                                                                "wait until there is a lottery running")
                return
            if guess is None or guess > int(range) or guess < 1:
                await self.bad_embed(ctx, "Invalid Guess Entered", "Please enter a guess between 1 and {}.".format(range))
                return
            await self.config.member(ctx.author).guess.set(guess)
            await self.basic_embed(ctx, "Success!", "Your new guess: **{}** has been recorded".format(guess))
        except Exception as e:
            await self.bad_embed(ctx, "An Error Occurred",
                                 "Error message: {} \n Please DM the ModMail bot or report this bug".format(e))

    @checks.mod_or_permissions()
    @lottery.command()
    async def end(self, ctx):
        """Ends the lottery and determines the winner(s)"""
        running = await self.config.guild(ctx.guild).running()
        if running is False:
            await self.bad_embed(ctx=ctx, title="No Lottery Running", description="There is not a lottery running, please "
                                                                            "wait until there is a lottery running")
            return
        await self.basic_embed(ctx, "The lottery has ended", "Calculating winners and distributing spoils...")
        await self.config.guild(ctx.guild).running.set(False)

        max = await self.config.guild(ctx.guild).range()
        winnings = await self.config.guild(ctx.guild).winnings()
        winning_number = random.randint(1, int(max))
        members = await self.config.all_members(guild=ctx.guild)

        await self.config.clear_all_members(guild=ctx.guild)

        winner = []


        for m in members:
            info = members[m]
            if info["guess"] == winning_number:
                winner.append(m)

        if not winner:
            await self.bad_embed(ctx, "No Winners!", "Nobody got the right number,"
                                                     " it was: {} ... better luck next time!".format(winning_number))
            return

        embed = discord.Embed(color=0x2ecc71, title="Winners!",
                              description="Each of the following people won {} from the lottery!".format(winnings))
        val = ""
        for w in winner:
            user = discord.Guild.get_member(self=ctx.guild, user_id=int(w))
            val += "\n" + user.mention
            await bank.deposit_credits(user, winnings)

        embed.add_field(name="Winners:", value="{}".format(val))
        embed.set_footer(text=credit)
        await ctx.send(embed=embed)

    @commands.group()
    async def setlottery(self, ctx):
        """Lottery configuration for guild"""

    @checks.admin_or_permissions()
    @setlottery.command()
    async def state(self, ctx):
        """Enables or disables lottery"""
        state = await self.config.guild(ctx.guild).allowed()
        await self.config.guild(ctx.guild).allowed.set(not state)
        await self.basic_embed(title="Success!", description="Lottery enabled is now: {}".format(not state), ctx=ctx)

    @checks.mod_or_permissions(manage_roles=True)
    @setlottery.command()
    async def entry_fee(self, ctx, fee):
        """Sets the lottery entry fee"""
        if fee is None:
            await self.bad_embed(ctx, "No Entry Fee Entered", "Please enter a entry fee")
            return

        try:
            fee = int(fee)
            await self.config.guild(ctx.guild).entry_fee.set(fee)
            await self.basic_embed(title="Success!", description="The entry fee is now {}!".format(fee), ctx=ctx)
        except Exception as e:
            await self.bad_embed(ctx, "An Error Occurred", "Error message: {} \n Please DM the ModMail bot or report this bug".format(e))


    @checks.mod_or_permissions(manage_roles=True)
    @setlottery.command()
    async def winnings(self, ctx, winnings):
        """Sets the lottery winnings"""
        if winnings is None:
            await self.bad_embed(ctx, "No Winning Amount Entered", "Please enter a winning amount")
            return

        try:
            winnings = int(winnings)
            await self.config.guild(ctx.guild).winnings.set(winnings)
            await self.basic_embed(title="Success!", description="The win credits is now {}!".format(winnings), ctx=ctx)
        except Exception as e:
            await self.bad_embed(ctx, "An Error Occurred", "Error message: {} \n Please DM the ModMail bot or report this bug".format(e))

    @checks.mod_or_permissions(manage_roles=True)
    @setlottery.command()
    async def upper_range(self, ctx, range):
        """Sets the upper range for lottery number guessing"""
        if range is None:
            await self.bad_embed(ctx, "No Upper range entered", "Please enter a upper range")
            return
        try:
            range = int(range)
            await self.config.guild(ctx.guild).range.set(range)
            await self.basic_embed(title="Success!", description="The range upper bound is now {}!".format(range), ctx=ctx)
        except Exception as e:
            await self.bad_embed(ctx, "An Error Occurred",
                           "Error message: {} \n Please DM the ModMail bot or report this bug".format(e))

    # todo reset command
    # @checks.mod_or_permissions()
    # @setlottery.command()
    # async def reset(self, ctx):
    #     """Resets settings to default settings"""
    #     await self.config.clear_all_guilds()
    #     await ctx.send("Done...")
    #
    # @commands.command()
    # async def test(self, ctx):
    #     user = discord.Guild.get_member(self=ctx.guild, user_id=337240732739960833)
    #     await ctx.send(user.mention)
