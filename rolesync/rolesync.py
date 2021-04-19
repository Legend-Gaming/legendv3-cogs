from discord import member
from redbot.core import commands, Config, checks
import discord

default_global = {
    'logchannel': None,
    'enabledguilds': [],

}
default_user = {
    'roles' : []
}
"""
- Listener
- Logging
- Enable => sync_roles() (ask)

- Force sync (to this server)

- Join server?

"""


class RoleSync(commands.Cog):
    """Sync user roles between servers"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 8818154, force_registration=True)
        self.config.register_global(**default_global)
        self.config.register_user(**default_user)

    async def log(self, message: str):
        channelid = await self.config.logchannel()
        if channelid is None:
            print("Log channel for RoleSync is not set. Please do !rolesyncset logchannel #channel")
            print(message)
        channel = self.bot.get_channel(channelid)
        await channel.send(message)
        

    async def get_role(self, guild: discord.Guild, role_name: str):
        for role in guild.roles:
            if role.name == role_name:
                return role
        try:
            role = await guild.create_role(name=role_name)
            await self.log(f"The server {guild.name} did not have the role {role_name}. The role was created and assigned.")
        except discord.Forbidden:
            await self.log(f"The server {guild.name} did not have the role {role_name}. I could not create the role. ")
        return role

    async def syncuser(self, user: discord.Member, config=None, noremove=False):
        # print('sync', user)
        if user is None:
            return
        guilds = await self.config.enabledguilds()
        if user.guild.id not in guilds:
            return
        if config is None:
            config = await self.config.user(user).roles()
        guild: discord.guild = user.guild
        croles = user.roles
        extroles = [await self.get_role(guild, x) for x in config if await self.get_role(guild, x) not in croles]
        for role in extroles:
            if role is None:
                await self.log("The user {user.mention} needs the role above which could't be created.}")
            try:
                await user.add_roles(role, reason='Rolesync')
            except discord.Forbidden:
                await self.log(f"The role {role.name} from the server {user.guild.name} could not be added to the user {user.mention} because the role is above me or I don't have the manage roles permission. Please do this manually!")
        if noremove:
            return
        rmroles = [x for x in croles if x.name not in config]
        for role in rmroles:
            try:
                await user.remove_roles(role, reason='Rolesync')
            except discord.Forbidden:
                await self.log(f"The role {role.name} from the server {user.guild.name} could not be removed from the user {user.mention} because the role is above me or I don't have the manage roles permission. Please do this manually!")
        # print("added:", extroles)
        # print("removed:", rmroles)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guilds = await self.config.enabledguilds()
        if member.guild.id not in guilds:
            return
        await self.syncuser(member)
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        guilds = await self.config.enabledguilds()
        if before.guild.id not in guilds:
            return
        search = True
        async for entry in before.guild.audit_logs(limit=20, action=discord.AuditLogAction.member_role_update):
            if entry.after == after:
                break
            if entry.target.id == before.id and entry.reason == "Rolesync" and entry.after == after:
                search = False
                break

        if search == False:
            return

        nroles = [x.name for x in after.roles]
        await self.config.user(after).roles.set(nroles)
        for guildid in guilds:
            guild: discord.Guild = self.bot.get_guild(guildid)
            member = guild.get_member(after.id)
            # print(member)
            if member is not None:
                await self.syncuser(member)


    @commands.group(aliases=['rolesyncset', 'setrs', 'rsset'])
    @checks.mod()
    async def setrolesync(self, ctx):
        """Configure RoleSync"""
        pass

    @setrolesync.command()
    @checks.admin()
    async def toggle(self, ctx, option: str):
        """Enable / Disable Rolesync from / to this server. Option is either True or False"""
        option = option.lower()
        enabledguilds = await self.config.enabledguilds()
        guildid = ctx.guild.id
        if option == 'true':
            if guildid in enabledguilds:
                return await ctx.send("This server is already having roles synced.")
            enabledguilds.append(guildid)
            await self.config.enabledguilds.set(enabledguilds)
            return await ctx.send("This server is now having roles synced. Please use `!setrolesync forcesync` to sync this server's roles with other servers")
        elif option == 'false':
            if guildid in enabledguilds:
                enabledguilds.remove(guildid)
            await self.config.enabledguilds.set(enabledguilds)
            return await ctx.send("This server will not longer have roles synced.")
        else:
            return await ctx.send("Invalid option. Please enter true or false.")

    @setrolesync.command()
    @checks.admin()
    async def logchannel(self, ctx, channel: discord.TextChannel):
        """Set the log channel (will override currently set channel)"""
        await self.config.logchannel.set(channel.id)
        await ctx.send("Done!")
    
    
    @setrolesync.command()
    async def forcesync(self, ctx):
        """Force sync this server's roles"""
        await ctx.send("This will take awhile... (Please don't run multiple forcesync's at the same time. Wait for for me to say Done)")
        # await ctx.send("Note that other role ")
        async with ctx.typing():
            for member in ctx.guild.members:
                roles = await self.config.user(member).roles()
                croles = member.roles
                roles.extend(x.name for x in croles if x.name not in roles)
                await self.config.user(member).roles.set(roles)
                guilds = await self.config.enabledguilds()
                for guildid in guilds:
                    guild: discord.Guild = self.bot.get_guild(guildid)
                    membern = guild.get_member(member.id)
                    await self.syncuser(membern, config=roles, noremove=True)
        await ctx.send("Done!")
        
        # ext: perms
