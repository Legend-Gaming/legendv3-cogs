# Standard Library
import asyncio
import itertools
import random
import discord
import contextlib
from discord import player
import time

from redbot.core.bank import cost
from redbot.core.config import Value

# Russian Roulette
from .kill import outputs

# Red
from redbot.core import Config, bank, checks, commands
from redbot.core.errors import BalanceTooHigh


__version__ = "3.1.06"
__author__ = "Redjumpman"


class RussianRoulette(commands.Cog):
    defaults = {
        "last_used": None,
        "Cost": 5000,
        "Chamber_Size": 6,
        "Wait_Time": 300,
        "useable_cost": None,
        "roulette_role": 737857454095990825, 
        "Session": {"Pot": 0, "Players": [], "Active": False},
    }

    def __init__(self):
        self.config = Config.get_conf(self, 5074395004, force_registration=True)
        self.config.register_guild(**self.defaults)

    @commands.guild_only()
    @commands.command()
    async def russian(self, ctx, cost:int=None):
        """Start or join a game of russian roulette.

        The game will not start if no players have joined. That's just
        suicide.

        The maximum number of players in a circle is determined by the
        size of the chamber. For example, a chamber size of 6 means the
        maximum number of players will be 6.
        """
        last_used = await self.config.guild(ctx.guild).last_used()
        wait_time = await self.config.guild(ctx.guild).Wait_Time()
        a = time.time()
        if last_used is None or a >= last_used + wait_time :
            basecost = await self.config.guild(ctx.guild).Cost()
            settings = await self.config.guild(ctx.guild).all()
            if cost is None:
                cost = basecost
                await self.game_checks(ctx, settings, cost)
            else:
                if cost > basecost:
                    await self.game_checks(ctx, settings, cost)
                else:
                    await ctx.send("Hahahaha, your disgraceful offer has been rejected, at least put {} credits on the line.".format(basecost))

        else:
            time_left = (wait_time - (a - last_used))//60
            formatted_minutes = round(time_left)
            formatted_seconds = int((wait_time - (a - last_used))%60)
            
            await ctx.send("The musketeer is sleeping right now, try again after approximately {} minutes and {} seconds.".format(formatted_minutes, formatted_seconds))
                         
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    @commands.command(hidden=True)
    async def rusreset(self, ctx):
        """ONLY USE THIS FOR DEBUGGING PURPOSES"""
        await self.config.guild(ctx.guild).Session.clear()
        await self.config.guild(ctx.guild).last_used.clear()
        await self.config.guild(ctx.guild).useable_cost.clear()
        await ctx.send("The Russian Roulette sesssion on this server has been cleared.")

    @commands.command()
    async def russianversion(self, ctx):
        await ctx.send("You are using russian roulette version {}".format(__version__))

    @commands.group(autohelp=True)
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def setrussian(self, ctx):
        """Russian Roulette Settings group."""
        pass

    @setrussian.command()
    async def chamber(self, ctx, size: int):
        """Sets the chamber size of the gun used. MAX: 12."""
        if not 1 < size <= 12:
            return await ctx.send("Invalid chamber size. Must be in the range of 2 - 12.")
        await self.config.guild(ctx.guild).Chamber_Size.set(size)
        await ctx.send("Chamber size set to {}.".format(size))

    @setrussian.command()
    async def cost(self, ctx, amount: int):
        """Sets the required cost to play."""
        if amount < 0:
            return await ctx.send("You are an idiot.")
        await self.config.guild(ctx.guild).Cost.set(amount)
        currency = await bank.get_currency_name(ctx.guild)
        await ctx.send("Required cost to play set to {} {}.".format(amount, currency))

    @setrussian.command()
    async def wait(self, ctx, seconds: int):
        """Set the wait time (seconds) before starting the game."""
        if seconds <= 0:
            return await ctx.send("You are an idiot.")
        await self.config.guild(ctx.guild).Wait_Time.set(seconds)
        await ctx.send("The time before a roulette game starts is now {} seconds.".format(seconds))

    @setrussian.command()
    async def role(self, ctx, role: discord.Role):
        await self.config.guild(ctx.guild).roulette_role.set(role.id)
        await ctx.send("Roulette will now ping the {} role.".format(role.name))

    async def game_checks(self, ctx, settings, cost:int):
        if settings["Session"]["Active"]:
            with contextlib.suppress(discord.Forbidden):
                return await ctx.author.send("You cannot join or start a game of russian roulette while one is active.")

        if ctx.author.id in settings["Session"]["Players"]:
            return await ctx.send("You are already in the roulette circle.")

        if len(settings["Session"]["Players"]) == settings["Chamber_Size"]:
            return await ctx.send("The roulette circle is full. Wait for this game to finish to join.")
        try:
            players = await self.config.guild(ctx.guild).Session.get_raw("Players")
            if len(players) < 1:
                await bank.withdraw_credits(ctx.author, cost)
                await self.config.guild(ctx.guild).useable_cost.set(cost)
                await self.add_player(ctx, cost)
            else:
                cost = await self.config.guild(ctx.guild).useable_cost()
                await bank.withdraw_credits(ctx.author, cost)
                await self.add_player(ctx, cost)

        except ValueError:

            currency = await bank.get_currency_name(ctx.guild)
            return await ctx.send("Insufficient funds! This game requires {} {}.".format(settings["useable_cost"], currency))
                

    async def add_player(self, ctx, cost):
        current_pot = await self.config.guild(ctx.guild).Session.Pot()
        await self.config.guild(ctx.guild).Session.Pot.set(value=(current_pot + cost))
        role_id = await self.config.guild(ctx.guild).roulette_role()
        role = ctx.guild.get_role(role_id)

        async with self.config.guild(ctx.guild).Session.Players() as players:
            players.append(ctx.author.id)
            num_players = len(players)

        if num_players == 1:
            wait = await self.config.guild(ctx.guild).Wait_Time()
            await ctx.send(
                "{0} {1.author.mention} is gathering players for a game of russian "
                "roulette!\nType `{1.prefix}russian` to enter. "
                "The round will start in {2} seconds. "
                "The bet is set to **{3}** credits.".format(role.mention, ctx, wait, cost)
            )
            await asyncio.sleep(wait)
            await self.start_game(ctx)
        else:
            await ctx.send("{} was added to the roulette circle.\nOnly the **first players** bet is considered.".format(ctx.author.mention))

    async def start_game(self, ctx):
        await self.config.guild(ctx.guild).Session.Active.set(True)
        data = await self.config.guild(ctx.guild).Session.all()
        players = [ctx.guild.get_member(player) for player in data["Players"]]
        filtered_players = [player for player in players if isinstance(player, discord.Member)]
        if len(filtered_players) < 2:
            try:
                await bank.deposit_credits(ctx.author, data["Pot"])
            except BalanceTooHigh as e:
                await bank.set_balance(ctx.author, e.max_balance)
            await self.reset_game(ctx)
            return await ctx.send("You can't play by youself. That's just suicide.\nGame reset and cost refunded.")
        chamber = await self.config.guild(ctx.guild).Chamber_Size()

        counter = 1
        while len(filtered_players) > 1:
            await ctx.send(
                "**Round {}**\n*{} one round into the musket and gives it to the musketeer "
                "and with a flick of the wrist it locks into "
                "place.*".format(counter, ctx.bot.user.name)
            )
            await asyncio.sleep(3)
            await self.start_round(ctx, chamber, filtered_players)
            counter += 1
        await self.game_teardown(ctx, filtered_players)

    async def start_round(self, ctx, chamber, players):
        position = random.randint(1, chamber)
        while True:
            for turn, player in enumerate(itertools.cycle(players), 1):
                await ctx.send(
                    "{} watches as the musketeer slowly takes aim and squeezes the trigger...".format(player.name)
                )
                await asyncio.sleep(5)
                if turn == position:
                    players.remove(player)
                    msg = "**BANG!** {0} is now dead.\n"
                    msg += random.choice(outputs)
                    await ctx.send(msg.format(player.mention, random.choice(players).name, ctx.guild.owner))
                    await asyncio.sleep(3)
                    break
                else:
                    await ctx.send("**CLICK!** ```{} survived!!```".format(player.name))
                    await asyncio.sleep(3)
            break

    async def game_teardown(self, ctx, players):
        winner = players[0]
        currency = await bank.get_currency_name(ctx.guild)
        total = await self.config.guild(ctx.guild).Session.Pot()
        wait_time = await self.config.guild(ctx.guild).Wait_Time()
        try:
            await bank.deposit_credits(winner, total)
        except BalanceTooHigh as e:
            await bank.set_balance(winner, e.max_balance)
        await ctx.send(
            "Congratulations {}! You are the last person standing and have "
            "won a total of {} {}."
            "Please dont disturb the musketeer for the next {} mins. She needs some rest.".format(winner.mention, total, currency, int(wait_time/60))
        )
        await self.reset_game(ctx)

    async def reset_game(self, ctx):
        await self.config.guild(ctx.guild).Session.clear()
        await self.config.guild(ctx.guild).last_used.clear()
        await self.config.guild(ctx.guild).useable_cost.clear()
        a = time.time()
        await self.config.guild(ctx.guild).last_used.set(a)


