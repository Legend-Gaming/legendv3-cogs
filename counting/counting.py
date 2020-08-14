import discord
from redbot.core import commands, bank, checks, Config

bot_credits = 'Bot by: Legend Gaming | Generaleoley'
base_help = """
__**Welcome to Counting!**__
• You guys are working together to count to various numbers. Do `!counting info` for more details!
• Count starts at 1
• Count must rotate users (you can't go 1,2,3,4... by yourself)
• Anything that isn't the next number will reset the count. Such as:
     - Message edits
     - Duplicate numbers
     - More than just number (eg. 69 NICE)
     - Talking
     - Bot commands
     - etc.
• **EXCEPT**:
    - Bot Messages (like this one)
    - Manager exceptions
    - Server messages
• Various payouts can be found at `!counting payouts`
• The bot will announce once a milestone is reached
• Do not cheat. You will be reset along with other punishments.
• The bot will react with ✅ if the next number is correct.
• The bot will react with 🎉 if a new record has been set.
• Enjoy the counting!

*This message does not reset the count.*
"""


class Counting(commands.Cog):
    """Counting Cog for Counting Game"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=903428736)
        default_guild = {
            'channel': None,
            # }
            # default_channel = {
            'payout': {
                '100': 50,
                '250': 150,
                '500': 300,
                '1000': 1000,
                '2000': 3000,
                '5000': 10000,
            },
            'record': 1,
            'expected': '1',
            'user': None,
            'players': {},
        }
        self.config.register_guild(**default_guild)
        # self.config.register_channel(**default_channel)
    @commands.group()
    async def counting(self, ctx):
        """Base group for counting"""

    @counting.command(aliases=['info'])
    async def help(self, ctx):
        """Get information about the counting cog"""
        await ctx.send(base_help)

    @counting.command()
    async def record(self, ctx):
        """Get the highest count record"""
        record = await self.config.guild(ctx.guild).record()
        await ctx.send(record)

    @counting.command(aliases=['payout'])
    async def payouts(self, ctx):
        """Get payout information"""
        payouts = await self.config.guild(ctx.guild).payout()
        embed = discord.Embed(title='Payouts',
                              description='Each number counted is the amount of credits given below when the count below is reached.',
                              color=0x008000)
        marks = ''
        payment = ''
        newpayout = {}
        for item in payouts:
            newpayout[int(item)] = payouts[item]
            # del payouts[item]
        for item in sorted(newpayout):
            marks += str(item) + '\n'
            payment += str(newpayout[item]) + '\n'
        embed.add_field(name='Count to Reach', value=marks)
        embed.add_field(name='Credits', value=payment)
        embed.set_footer(text=bot_credits)
        await ctx.send(embed=embed)

    @commands.group(aliases=['setcounting'])
    async def setcount(self, ctx):
        """Use the following commands to configure counting"""

    @checks.admin_or_permissions()
    @setcount.command()
    async def channel(self, ctx, channel: discord.TextChannel):
        """Set the channel in which the counting will take place"""
        await self.config.guild(ctx.guild).channel.set(channel.id)
        # todo confirmation
        await ctx.send("Done... channel set.")

    @checks.admin_or_permissions()
    @setcount.command()
    async def payoutst(self, ctx, count: int, payout: int):
        """Configuration of Payouts"""
        vals = await self.config.guild(ctx.guild).payout()

        if payout == 0:
            del vals[str(count)]
        else:
            vals[str(count)] = payout

        await self.config.guild(ctx.guild).payout.set(vals)
        await ctx.send("Done...")

    @checks.admin_or_permissions()
    @setcount.command()
    async def expected(self, ctx, count: int):
        """Manually set the count, note that this will mess up the payouts and nothing will be paid for the skipped numbers"""
        await self.config.guild(ctx.guild).expected.set(str(count))
        await ctx.send("Done... ")

    # Listeners
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        data = self.config.guild(message.guild)
        channel_check = await data.channel()
        # payouts = await self.config.guild(message.guild).payout()
        # milestones = []
        # for payout in payouts:
        #     milestones.append(payout)
        if message.channel.id != channel_check:
            return

        expected = await data.expected()
        user = await data.user()

        num = str(message.content)

        if num[:2] == '\%':
            return

        author = str(message.author.id)

        if num == expected and user != author:
            new = int(expected) + 1
            await data.expected.set(str(new))
            players = await data.players()
            # print(players)
            winpay = await data.payout()
            record = await data.record()
            await message.add_reaction(emoji='✅')
            await data.user.set(author)
            if players.get(author) is None:
                players[author] = 1
                # print("here")
                # print(players[message.author.id])
            else:
                players[author] += 1
                # print(players[message.author.id])

            # print(players)
            await data.players.set(players)

            # print(record)
            # print(winpay[expected])

            # check record
            if int(expected) > record:
                await data.record.set(int(expected))
                await message.add_reaction(emoji='🎉')

            # check win
            if winpay.get(expected) is not None:
                await message.channel.send(
                    "Congrats! On reaching {}... the following rewards are to follow: (ps. don't celebrate here as it will reset scores)".format(
                        expected))
                # print(players)
                for player in players:
                    if player == 0 or player == '0':
                        continue
                    memb = message.guild.get_member(int(player))
                    amount = winpay[expected] * players[player]
                    await bank.deposit_credits(memb, amount)
                    await message.channel.send("- {} has received {}".format(memb.mention, str(amount)))

                await message.channel.send(
                    "You may continue counting without loss at {} (say that number)".format(str(new)))


        else:
            await message.add_reaction(emoji='❌')
            await message.channel.send("Reset back to 1.")
            await data.user.set(None)
            await data.expected.set('1')
            await data.players.set({})
