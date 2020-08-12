from discord import role
from redbot.core import Config, commands, bank, checks
import discord
import random
from redbot.core.utils.chat_formatting import humanize_number

credit = "By: king slayer | Legend Gaming"

class Raffle(commands.Cog):

    def __init__(self, bot):
        self.bot = bot 
        self.config = Config.get_conf(self, identifier=132424523513)
        default_guild = {"raffle_name": None,
                        "participants": [],
                        "raffle_running": False,
                        "base_ticket_price": 5000000,
                        "total_prizes": None
                        }

        default_role = {"new_price": 0}

        self.config.register_guild(**default_guild)
        self.config.register_role(**default_role)

    async def less_participants(self, ctx):
        total_winners = await self.config.guild(ctx.guild).total_prizes()
        async with self.config.guild(ctx.guild).participants() as lst:

            temp_lst = []
            for i in lst:
                if i in temp_lst:
                    continue
                else:
                    temp_lst.append(i)

            if len(temp_lst) > total_winners:
                return False
            else:
                return True 

    async def get_lowest_amount(self, ctx, user:discord.Member):
        base_credits = await self.config.guild(ctx.guild).base_ticket_price()
        if base_credits is None:
            return None
        role_wise_prices = [base_credits]
        for role in user.roles:
            role_credits = await self.config.role(role).new_price()
            if role_credits == 0:
                continue
            role_wise_prices.append(role_credits)
        final_credits = min(role_wise_prices)
        return final_credits

    async def get_winners(self, ctx):
        number = await self.config.guild(ctx.guild).total_prizes()
        description = ""
        rafflename = await self.config.guild(ctx.guild).raffle_name()
        title = "The following users have won the {} raffle".format(rafflename)
        async with self.config.guild(ctx.guild).participants() as lst:
            winner_list = []
            status = False
            while status is False:
                i = random.choice(lst)
                if (i not in winner_list) and (status is False):
                    winner_list.append(i)
    
                elif len(winner_list) == number:
                    status = True

        for winner in winner_list:
            winner_obj = ctx.guild.get_member(winner)        
            description += "Congratulations to {} for winning the raffle\n".format(winner_obj.mention)

        embed = discord.Embed(color=0xFFFF00, title=title, description=description)
        embed.set_footer(text=credit)
        await ctx.send(embed=embed)
        winner_list.clear()
        



    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def startraffle(self, ctx, prizes:int, *,raffle_name:str):
        guild_data = self.config.guild(ctx.guild)
        running = await guild_data.raffle_running()

        if running:
            name = await guild_data.raffle_name()
            await ctx.send("There is already a raffle going on by the name {}, there can only be one raffle running per guild".format(name))
        else:
            await guild_data.total_prizes.set(int(prizes))
            await guild_data.raffle_name.set(raffle_name)
            await guild_data.raffle_running.set(True)
            await ctx.send("A raffle by the name **{}** has been started\nType {}stopraffle if you want to stop it".format(raffle_name, ctx.prefix))


    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def stopraffle(self, ctx):
        """Stops the raffle and gets the winners"""
        guild_data = self.config.guild(ctx.guild)
        running = await guild_data.raffle_running()
        participants = await guild_data.participants()
        prizes = await guild_data.total_prizes()
        if running:
            if participants is not None and prizes is not None:
                less_participants = await self.less_participants(ctx)
                if less_participants is False:
                    await ctx.send("Ending the raffle and getting the winners....")
                    await self.get_winners(ctx)
                    await guild_data.base_ticket_price.clear()
                    for role in ctx.guild.roles:
                        await self.config.role(role).clear()
                    await guild_data.total_prizes.clear()
                    await guild_data.raffle_name.clear()
                    await guild_data.raffle_running.set(False)
                    await guild_data.participants.clear()
                else:
                    await ctx.send("The number of winners is more than the number of participants, so raffle can't be stopped.")
            
            else:
                await ctx.send("Couldn't end the raffle as config isn't setup correctly")

        else: 
            await ctx.send("There is no raffle running.")

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def rafflesettings(self, ctx):
        """Use this to change the settings of raffle in config"""
        pass

    @rafflesettings.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def totalwinners(self, ctx, number:int):
        """Set the number of prizes to be distrubuted"""  
        await self.config.guild(ctx.guild).total_prizes.set(number)
        await ctx.send("There will be {} winner/winners in total".format(number)) # yeah I'm lazy



    @rafflesettings.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def baseprice(self, ctx, number:int):
        """Sets the baseprice of one ticket"""
        await self.config.guild(ctx.guild).base_ticket_price.set(number)
        await ctx.send("You set the cost of one ticket as {} credits by default".format(humanize_number(number)))



    @rafflesettings.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def rafflename(self, ctx, *, raffle_name:str):
        """Sets the name of the raffle, should mostly be the name of the prize for ex. Discord/pass royale raffle"""
        await self.config.guild(ctx.guild).raffle_name.set(raffle_name)
        await ctx.send("You set the name of raffle as {}".format(raffle_name))



    @rafflesettings.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def roleprice(self, ctx, role: discord.Role, new_price:int):
        """Sets the price of tickets according to roles, setting prices higher than base price has no affect"""
        await self.config.role(role).new_price.set(new_price)
        price = await self.config.role(role).new_price()
        final_price = humanize_number(price)
        await ctx.send("You set the cost of one ticket as {} credits for the corresponding role".format(final_price))

    
    @commands.command(aliases=['buyticket'])
    @commands.guild_only()
    async def buytickets(self, ctx, tickets: int = 1):
        """Buy tickets for a raffle that is going on"""
        initial_tickets = tickets
        price = await self.get_lowest_amount(ctx, user=ctx.author)
        guild_data = self.config.guild(ctx.guild)
        running = await guild_data.raffle_running()
        if running:
            if price is None:
                await ctx.send("The base credits have not been set please contact a clan manager or a dev ASAP")
            else:
                final_price = price*tickets
                user_credits = await bank.get_balance(ctx.author)
                if final_price <= user_credits:
                    async with self.config.guild(ctx.guild).participants() as lst:
                        while tickets > 0:
                            lst.append(ctx.author.id)
                            tickets = tickets - 1
                        await bank.withdraw_credits(ctx.author, final_price)
                        await ctx.send("{} credits have been withdrawn and {} tickets have been added".format(humanize_number(final_price), initial_tickets))

                else:
                    await ctx.send("You don't have enough money to buy these number of tickets")
        else:
            await ctx.send("No raffle is running right now")



    @commands.command()
    @commands.guild_only()
    async def mytickets(self, ctx):
        """shows how many tickets you have and percentage of winning"""

        guild_data = self.config.guild(ctx.guild)
        running = await guild_data.raffle_running()
        if running:
            tickets = 0
            authorid = ctx.author.id
            lst = await self.config.guild(ctx.guild).participants()
            if len(lst) <= 0:
                await ctx.send("You have no tickets, try `{}buytickets` to get started".format(ctx.prefix))
            else:
                for i in lst:
                    if i == authorid:
                        tickets += 1
                    else:
                        continue

                total_tickets = len(lst)
                percentage = tickets/total_tickets*100
                new_percentage = round(percentage)
                description = "You have **{} tickets** and your chances of winning are **{}%**".format(tickets, new_percentage)
                embed = discord.Embed(color=0xFFFF00, description=description)
                embed.set_footer(text=credit)
                await ctx.send(embed=embed)

        else:
            await ctx.send("There is no raffle is running right now.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def addtickets(self, ctx, user:discord.Member, number:int = 1):
        """Administratively Adds the amount of tickets specified to a member"""
        temp_num = number
        if number > 500:
            await ctx.send("Please enter a number below 500")
        else:
            async with self.config.guild(ctx.guild).participants() as lst:
                while number > 0:
                    lst.append(user.id)
                    number = number - 1
            await ctx.send("{} tickets have been given to {}".format(temp_num, user.name))
            
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def removetickets(self, ctx, user:discord.Member, number:int = 1):
        """Administratively removes the amount of tickets specified to a member"""
        temp_num = number
        if number > 500:
            await ctx.send("Please enter a number below 500")
        else:
            async with self.config.guild(ctx.guild).participants() as lst:
                number_of_tickets = 0
                for i in lst:
                    if i == user.id:
                        number_of_tickets += 1
                if number_of_tickets > number:
                    while number > 0:
                        lst.remove(user.id)
                        number = number - 1
                    await ctx.send("{} tickets have been given to {}".format(temp_num, user.name))

                else:
                    await ctx.send("The user has {} tickets and you requested to remove {} which is more than the tickets user has".format(number_of_tickets, number))



    @commands.command()
    @commands.guild_only()
    async def getsettings(self, ctx):
        """Displays all the setable values from the config"""
        data = self.config.guild(ctx.guild)
        name = await data.raffle_name()
        running = await data.raffle_running()
        baseprice = await data.base_ticket_price()
        total_prizes = await data.total_prizes()

        embed = discord.Embed(color=0x008000, title="Raffle settings")
        embed.add_field(name="Name of the Raffle:", value=name, inline=False)
        embed.add_field(name="Raffle running:",value=running,inline=False)
        embed.add_field(name="Base ticket price:",value=baseprice,inline=False)
        embed.add_field(name="Total prizes:",value=total_prizes,inline=False)
        embed.set_footer(text=credit)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def getrolesettings(self, ctx, role:discord.Role):
        """Tells the price of one ticket corresponding to the role"""
        role_price = await self.config.role(role).new_price()
        base_credits = await self.config.guild(ctx.guild).base_ticket_price()
        if role_price == 0:
            final_credits = humanize_number(base_credits)
        else:
            final_credits = humanize_number(role_price)

        await ctx.send("People having the {} role have to pay {} credits for one ticket".format(role.name, final_credits))

    @commands.command()
    @commands.guild_only()
    async def ticketcost(self, ctx):
        """Gets the credits author has to spend to get one ticket"""
        cost = await self.get_lowest_amount(ctx, user=ctx.author)
        if cost is None:
            await ctx.send("Base credits have not been set please let a CM or Dev know about it ASAP")

        else:
            await ctx.send("One ticket costs {} for {}".format(humanize_number(cost), ctx.author.mention))
