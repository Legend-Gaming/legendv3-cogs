from redbot.core import commands, bank, Config, checks
import discord
import asyncio

credit = "Bot by Generaleoley | LeGeND eSports"


class UserEnd(Exception):
    pass
class CommandInUse(Exception):
    pass

class Shop(commands.Cog):

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=32539819)
        default_guild = {
            'emoji_cost': 80000,
            'cc_cost': 90000,
            'rarecost': 250000,
            'epiccost': 750000,
            'legendarycost': 1000000,
            'passroyale_cost': 8888888,
            'nitroclassic_cost': 8888888,
            'rareid': 381056647721910281,
            'epicid': 381057151805816844,
            'legendaryid': 381057293963362307,
            'level100id': 618205748022738950,
            'logchannel': 711696407580377168,
        }
        self.config.register_guild(**default_guild)
        self.bot = bot
        self.cc = self.bot.get_cog('CustomCommands').cc_create
        self.prepare_args = self.bot.get_cog('CustomCommands').prepare_args


    async def buycc(self, ctx):
        await ctx.send("Please check your DM's...")

        user = ctx.author
        dm_channel = user.dm_channel

        if dm_channel is None:
            dm_channel = await user.create_dm()

        # checks to see if the response is truely from the User DM's
        def check(m):
            return m.channel == dm_channel and m.author == user

        # todo integrate into larger action_confirm function
        # confirmation of selection
        async def confirm(what, value):
            await user.send('Do you confirm "{}" as your {}?'.format(value, what))
            await user.send("Reply with YES for a confirmation. Anything else for NO")
            res = await self.bot.wait_for('message', timeout=60, check=check)
            return res.content.lower() == 'yes'

        try:
            await user.send("We got a few questions on the custom command... "
                            "\nType STOP to stop this and refund credits")

            # Choosing the command name
            confirmed = False
            while not confirmed:
                await user.send("What do you want the command to be (spaces will be automatically replaced with `_`)?")
                cmd = await self.bot.wait_for('message', timeout=60, check=check)
                final_command = cmd.content.replace(' ', '_')  # Auto replace spaces
                final_command = final_command.strip('!/.')  # Remove the prefix if they added one

                if cmd.content.lower() == "stop":
                    raise UserEnd

                if final_command in (
                        *self.bot.all_commands, *commands.RESERVED_COMMAND_NAMES):
                    await user.send("There already exists a command with the same name.")
                    break

                confirmed = await confirm("command", '!' + final_command)

            # Choosing the command response
            confirmed = False
            while not confirmed:
                await user.send("What do you want the command to say?")
                rsp = await self.bot.wait_for('message', timeout=60, check=check)

                if rsp.content.lower() == 'stop':
                    raise UserEnd

                confirmed = await confirm("commmand's response", rsp.content)

                final_response = rsp.content

        except asyncio.exceptions.TimeoutError:
            await user.send("Timeout... your credits have been refunded")
            return
        except UserEnd:
            await user.send("Stopped!")
            return

        # Creating the command
        try:
            await self.cc(ctx=ctx, command=final_command, text=final_response)
            await user.send("Great! Command has been created!")
        except Exception as e:
            await user.send("Error. Please DM ModMail with ```{}```".format(e))

    async def action_confirm(self, ctx):
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        res = await self.bot.wait_for('message', timeout=60, check=check)
        return res.content.lower() == 'yes'

    # todo make a seperate command called "shop" - don't put them together that's just lazy
    @commands.command()
    async def shop(self, ctx):
        await ctx.send("Insert Shop Here")

    @commands.command()
    async def buy(self, ctx, choice_no: int = 0):
        # Shows options if they don't have an option
        if choice_no == 0 or choice_no > 7:
            await self.shop(ctx)
            return

        guild_data = self.config.guild(ctx.guild)

        emoji_cost = await guild_data.emoji_cost()
        cc_cost = await guild_data.cc_cost()
        
        level100id = await guild_data.level100id()
        level100 = ctx.guild.get_role(level100id)

        legendaryid = await guild_data.legendaryid()
        legendary = ctx.guild.get_role(legendaryid)
        legendarycost = await guild_data.legendarycost()

        epicid = await guild_data.epicid()
        epic = ctx.guild.get_role(epicid)
        epiccost = await guild_data.epiccost()

        rareid = await guild_data.rareid()
        rare = ctx.guild.get_role(rareid)
        rarecost = await guild_data.rarecost()

        passroyale_cost = await guild_data.passroyale_cost()
        nitroclassic_cost = await guild_data.nitroclassic_cost()

        author = ctx.author
        current_role = author.roles

        user_bal = await bank.get_balance(author)

        # Buying Custom Command -- DONE
        if choice_no == 1 and user_bal >= cc_cost:
            await self.buycc(ctx)
            # await ctx.send("Custom Command was sucessfully created! You have been charged {}".format(cc_cost))
            return  # useless code

        # Getting Rare
        elif choice_no == 2 and user_bal >= rarecost:  # if user wants a rare role
            for role in current_role:
                if role == rare or role == epic or role == legendary:
                    await ctx.send("BRUH IF U WASTE MY TIME I MIGHT BS YOU")  # if user already has rare or higher roles
                    return
                else:
                    await author.add_roles(rare)
                    await bank.withdraw_credits(author, rarecost)
                    await ctx.send("Done. You have been given the rare role {} \n {} credits have been removed".format(
                        author.mention, rarecost))
                    return
        elif choice_no == 3 and user_bal >= epiccost:  # if user wants an epic role
            for role in current_role:
                if role != rare:  # checks if the user has a rare role
                    await ctx.send("Get the rare role first.{}".format(author.mention))
                    return
                elif role == epic or role == legendary:  # checks if the user already has the role or higher
                    await ctx.send("BRUH IF U WASTE MY TIME I MIGHT BS YOU")
                    return
                else:
                    await author.add_roles(epic)
                    await bank.withdraw_credits(author, epiccost)
                    await ctx.send("Done. You have been given the epic role {} \n {} credits have been removed".format(
                        author.mention, epiccost))
                    return
        elif choice_no == 4 and user_bal >= legendarycost:  # if user wants a legendary role
            for role in current_role:
                if role != epic:  # checks if the user has required roles
                    await ctx.send("Get the epic role first.{}".format(author.mention))
                    return
                elif role == legendary:  # checks if the user already has the role required
                    await ctx.send("DON'T WASTE YOUR TIME HERE GO ABUSE GENS WALLET. ")
                    return
                else:
                    await author.add_roles(legendary)
                    await bank.withdraw_credits(author, legendarycost)
                    await ctx.send(
                        "Done. You have been given the Legendary role {} \n {} credits have been removed".format(
                            author.mention, legendarycost))
                    return

        # Custom Emote -- DONE
        elif choice_no == 5 and user_bal >= int(emoji_cost):
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                await ctx.send("Enter your emote:")
                resp = await self.bot.wait_for('message', timeout=60, check=check)
                emoji = resp.content

                # if len(emoji) != 1:
                #     await ctx.send("That wasn't an emote")
                #     return

                # todo len check
                user_nick = ctx.author.display_name
                if user_nick.find('|') < 2:
                    await ctx.send("Unknown username format")
                    return

                pos = user_nick.find('|') - 1

                user_nick = user_nick[:pos] + emoji + user_nick[pos:]

                await ctx.send(
                    "`{}` will be your new nickname. Type 'Yes' to confirm, anything else to deny".format(user_nick))
                res = await self.bot.wait_for('message', timeout=60, check=check)
                if res.content.lower() == 'yes':
                    try:
                        await ctx.author.edit(nick=user_nick)
                        await bank.withdraw_credits(ctx.author, emoji_cost)
                        await ctx.send("Done!")
                    except discord.Forbidden:
                        await ctx.send("I don't have the permission to do that. Please DM ModMail!")
                    except discord.HTTPException:
                        await ctx.send("Name too long. Please DM ModMail")
                else:
                    await ctx.send("Alright! We kept your current nickname!")
            except asyncio.exceptions.TimeoutError:
                await user.send("Timeout... your credits have been refunded")

        # Nitro classic / pass royale -- COMPLETE
        elif choice_no == 6 and user_bal >= passroyale_cost:
            for role in current_role:
                if role == legendary or role == level100:
                    await ctx.send("Are you sure you would like to buy pass royale?")
                    try:
                        if await self.action_confirm(ctx):
                            await bank.withdraw_credits(author, passroyale_cost)
                            channel_id = await guild_data.logchannel()

                            channel = ctx.guild.get_channel(int(channel_id))

                            if channel is None:
                                await ctx.send("Log channel not set")
                                return

                            await channel.send('**Pass Royale Purchase** : {}'.format(author.mention))

                            await ctx.send("Request sent. Please check DM's in 24 hours")
                        else:
                            await ctx.send("Request Ignored")
                            return
                    except asyncio.exceptions.TimeoutError:
                        await user.send("Timeout... your credits have been refunded")

                else:
                    await ctx.send("You need the legendary role before buying this.")

                    return

        elif choice_no == 7 and user_bal >= nitroclassic_cost:
            for role in current_role:
                if role == legendary or role == level100:
                    await ctx.send("Are you sure you would like to buy Nitro Classic?")
                    try:
                        if await self.action_confirm(ctx):
                            await bank.withdraw_credits(author, nitroclassic_cost)
                            channel_id = await guild_data.logchannel()
                            channel = ctx.guild.get_channel(int(channel_id))

                            if channel is None:
                                await ctx.send("Log channel not set")
                                return

                            await channel.send('**Discord Nitro Purchase** : {}'.format(author.mention))

                            await ctx.send("Request sent. Please check DM's in 24 hours")
                        else:
                            await ctx.send("Request Ignored")
                            return
                    except asyncio.exceptions.TimeoutError:
                        await user.send("Timeout... your credits have been refunded")
                        return

                else:
                    await ctx.send("You need the legendary role before buying this.")


        # Useless code. See above why
        # if choice_no >= 5:
        #     await ctx.send("Huh, I don't seem to have the item you want.")
        #     return

        else:  # if user can't buy anything
            await ctx.send("Hehe, you need to earn more money {}".format(author.mention))
            return


    # todo probably remove this or make it better (very weak rn)
    @checks.mod_or_permissions()
    @commands.command()
    async def setshop(self, ctx, attr, val):
        """Advanced settings configuration"""
        await self.config.guild(ctx.guild).get_attr(attr).set(int(val))
        a = self.config.guild(ctx.guild).get_attr(attr)
        await ctx.send("Set {} to {}".format(attr, await a()))
        
        
    @checks.mod_or_permissions()
    @commands.command()
    async def setrole(self, ctx, attr, role: discord.Role):
        """Set Role ID"""
        id = role.id
        await self.config.guild(ctx.guild).get_attr(attr).set(int(id))
        a = self.config.guild(ctx.guild).get_attr(attr)
        await ctx.send("Set {} to {}".format(attr, await a()))


    @commands.command()
    async def getval(self, ctx, attr: str):
        # await ctx.send(await self.config.guild(ctx.guild).get_attr(attr))
        a = self.config.guild(ctx.guild).get_attr(attr)
        await ctx.send(await a())

