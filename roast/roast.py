from redbot.core import commands, Config, checks
from redbot.core.data_manager import bundled_data_path
import random as rand
import discord


credit = "Bot by TheChosenOne07 (Yeah u wish... getting carried by Suven and Generaleoley)"


class Roast(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=5678424364)
        default_guild = {'VIP': []}
        self.config.register_guild(**default_guild)

    async def green_emb(self, title, description, ctx):
        embed = discord.Embed(color=0x2ecc71, title=title, description=description)
        embed.set_footer(text=credit)
        await ctx.send(embed=embed)

    async def red_emb(self, title, description, ctx):
        embed = discord.Embed(color=0xe74c3c, title=title, description=description)
        embed.set_footer(text=credit)
        await ctx.send(embed=embed)

    @commands.command()
    async def roast(self, ctx, *, user: discord.Member = None):
        """Roast The User"""
        if user is None:
            user = ctx.author
        if user == self.bot.user:
            await self.red_emb("LMAO YOU WISH", "WOW UR SO FUNNY... What an original idea, getting the bot to roast itself? Get a life loser.", ctx)
            return 
        file_path = bundled_data_path(self) / 'roasts.txt'
        vip_users = await self.config.guild(ctx.guild).VIP()
        if user.id in vip_users:
            await self.red_emb("Not Roasted", "You can't roast him peasant", ctx)
        else:
            with file_path.open('r') as file:
                roasts = file.readlines()
            # message = await self.config.guild(ctx.guild).roasts()
            response = user.mention + "  " + (rand.choice(roasts)).strip()
            await self.green_emb("Roasted", response, ctx)

    @checks.mod_or_permissions()
    @commands.command()  # broken
    async def setvip(self, ctx, new_vip: discord.Member):
        """Adding a VIP Member"""
        current = await self.config.guild(ctx.guild).VIP()
        if new_vip in current:
            await ctx.send("Already an elite")
        else:
            current.append(new_vip.id)
            await self.config.guild(ctx.guild).VIP.set(current)
            await ctx.send("Done {} is now an elite".format(new_vip.mention))

    @checks.mod_or_permissions()
    @commands.command()
    async def removevip(self, ctx, new_vip: discord.Member):
        """Remove a VIP Member"""
        current = await self.config.guild(ctx.guild).VIP()
        if new_vip.id in current:
            current.remove(new_vip.id)
            await self.config.guild(ctx.guild).VIP.set(current)
            await ctx.send("Done {} is not an elite anymore".format(new_vip.mention))
        else:
            await ctx.send("You can't remove anyone from elite if he is not an elite")


