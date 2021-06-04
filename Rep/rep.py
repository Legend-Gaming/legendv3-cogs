from redbot.core import Config, commands, checks
from redbot.core.utils.chat_formatting import humanize_number
import discord
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

class Reputation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=54596)
        self.default_member = {
            'rep': 0
        }
        self.config.register_member(**self.default_member)
    @commands.command(cooldown_after_parsing=True)
    @commands.guild_only()
    @commands.cooldown(rate=1, per=1800, type=commands.BucketType.member)
    async def rep(self, ctx, member:discord.Member=None):
        """
        Give a user a reputation point.
        """
        if member == None:
            await ctx.send(f"**You can give a rep!**")
            ctx.command.reset_cooldown(ctx)
        elif member == ctx.author:
            await ctx.send("You can't rep yourself, that'd be cheating the system!")
            ctx.command.reset_cooldown(ctx)
        elif member.bot:
            await ctx.send("Repping bots? Nah")
            ctx.command.reset_cooldown(ctx)
        else:
            rep = await self.config.member(member=member).rep()
            rep += 1
            await self.config.member(member=member).rep.set(rep)
            f_dict = await self.config.all_members(guild=ctx.guild)
            data = sorted(f_dict.items(), key=lambda x: x[1]['rep'], reverse=True)
            final_dict = {x: y for x, y in data}
            ldb_users = final_dict.keys()
            position = list(ldb_users).index(member.id)
            await ctx.send(
                f"**You have just given {member.mention} a reputation point!** \n\n They now have {rep} reputation points \n\n They are currently #{humanize_number(position+1)} on the Rep Leaderboard!")

    @commands.command()
    @commands.guild_only()
    async def showrep(self, ctx, member:discord.Member=None):
        """
        Check a users rep points, use !showrep to check yours
        """
        f_dict = await self.config.all_members(guild=ctx.guild)
        data = sorted(f_dict.items(), key=lambda x:x[1]['rep'], reverse=True)
        final_dict = {x: y for x, y in data}
        ldb_users = final_dict.keys()
        if member == None or member==ctx.author:
            rep = await self.config.member(member=ctx.author).rep()
            try:
                position = list(ldb_users).index(ctx.author.id)
            except ValueError:
                position = len(ldb_users)
            await ctx.send(f"**You have {rep} reputation points!** \n\nYou are currently #{humanize_number(position+1)} on the Rep leaderboard!")
        else:
            rep = rep = await self.config.member(member=member).rep()
            try:
                position = list(ldb_users).index(member.id)
            except ValueError:
                position = len(ldb_users)
            await ctx.send(f"**The user has {rep} reputation points!** \n\nThe user is currently #{humanize_number(position+1)} on the Rep leaderboard!")
        
    @commands.command(name="repldb")
    @commands.guild_only()
    async def repleaderboard(self, ctx):
        """
        Show the guilds rep leaderboard
        """
        data = await self.config.all_members(guild=ctx.guild)
        data = sorted(data.items(), key=lambda x:x[1]['rep'], reverse=True)
        final_dict = {x:y for x,y in data}
        #await ctx.send(final_dict)
        desc = ""
        embeds = []
        for position, individual in enumerate(final_dict, start=1):
            #indivdual is user id
            rep = final_dict[individual]['rep']
            mem = ctx.guild.get_member(int(individual))
            desc += f"**{position}. {mem.mention} ({mem.name}) \u200b \u200b \u200b \u200b Total Rep: {rep}**\n"
            if position%10 == 0:
                embed = discord.Embed(
                    color=0xFAA61A, description=desc)
                embed.set_author(name="Legend Family Rep Leaderboard",
                                 icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
                embed.set_footer(text="By Kingslayer | Legend Gaming",
                             icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
                embeds.append(embed)
                desc = ""
        if len(desc) == 0:
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            embed = discord.Embed(
                color=0xFAA61A, description=desc)
            embed.set_author(name="Legend Family Rep Leaderboard",
                             icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
            embed.set_footer(text="By Kingslayer | Legend Gaming",
                             icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
            embeds.append(embed)
            await menu(ctx, embeds, DEFAULT_CONTROLS)

    @commands.command()
    @checks.is_owner()
    @commands.guild_only()
    async def setrep(self, ctx, member:discord.Member, val:int):
        """Set a users rep points"""
        await self.config.member(member=member).rep.set(val)
        await ctx.send(f"Set {member.mention} rep to {val}")
    
