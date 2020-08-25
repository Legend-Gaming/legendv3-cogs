from redbot.core import checks, Config, commands, modlog
import discord

class Jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2345664456)
        default_member = {"roles":[],
                          "is_jailed": False,
                          "has_no_role": False}

        default_guild = {'jailed_role': 706167363027861544}
        self.config.register_member(**default_member)
        self.config.register_guild(**default_guild)

    async def initialize(self, bot):
        await self.register_casetypes()

    @staticmethod
    async def register_casetypes():
        jail_cases = [
        
            {
            "name": "jailed",
            "default_setting": True,
            "image": "<:pandacop:375143122474369046>",
            "case_str": "**Jailed**",
            },
            {
            "name": "bailed",
            "default_setting": True,
            "image": "<:pandacop:375143122474369046>",
            "case_str": "**Bailed**",
            }
        ]
        try:
            await modlog.register_casetypes(jail_cases)
        except RuntimeError:
            pass

    @commands.command()
    @checks.mod_or_permissions()
    async def jail(self, ctx, user: discord.Member, *,reason:str):

        if ctx.author != user:

            if ctx.author.top_role > user.top_role:

                jail_id = await self.config.guild(ctx.guild).jailed_role()

                lst = await self.config.member(user).roles()


                user_is_jailed = await self.config.member(user).is_jailed()

                jailed_role = ctx.guild.get_role(jail_id)

                user_roles = user.roles

                if user_is_jailed:
                    await ctx.send("The user is jailed")

                else:
                    
                    await modlog.create_case(
                    ctx.bot, ctx.guild, ctx.message.created_at, action_type="jailed",
                    user=user, moderator=ctx.author, reason=reason
                )
            
                    if len(user_roles) == 1:
                        await user.add_roles(jailed_role) 
                        await self.config.member(user).is_jailed.set(True)
                        await self.config.member(user).has_no_role.set(True)
                        await ctx.send("Done, the member has been jailed")

                    else:
                        for role in user_roles:
                            if role.name == "@everyone":
                                continue
                            lst.append(role.id)
                            await user.remove_roles(role)
                        await self.config.member(user).roles.set(lst)
                        await user.add_roles(jailed_role)
                        await self.config.member(user).is_jailed.set(True)
                        await self.config.member(user).has_no_role.set(False)
                        await ctx.send("Done, the member has been jailed")
                        
            else:
                await ctx.send("You can't jail a user who has a role greater than or equal to yours")
        else:
            await ctx.send("Please don't try these things for fun.")
                

    @commands.command()
    @checks.mod_or_permissions()
    async def bailout(self, ctx, user: discord.Member, *, reason:str):

        jail_id = await self.config.guild(ctx.guild).jailed_role()
        lst = await self.config.member(user).roles()
        jailed_role = ctx.guild.get_role(jail_id)
        user_has_no_roles = await self.config.member(user).has_no_role()
        user_is_jailed = await self.config.member(user).is_jailed()

        if user_is_jailed:
            await modlog.create_case(
            ctx.bot, ctx.guild, ctx.message.created_at, action_type="bailed",
            user=user, moderator=ctx.author, reason=reason
            )

            if user_has_no_roles:
                await self.config.member(user).is_jailed.set(False)
                await self.config.member(user).has_no_role.set(False)
                await user.remove_roles(jailed_role)
                await ctx.send("The user had no roles so Jailed role has been removed")

            else:
                for roleid in lst:
                    role =  ctx.guild.get_role(roleid)
                    await user.add_roles(role)
                await self.config.member(user).is_jailed.set(False)
                await self.config.member(user).roles.clear()
                await user.remove_roles(jailed_role)
                await ctx.send("The user has been released from jail, roles have been added")
        else:
            await ctx.send("The user isn't in jail.")

    @commands.command()
    @checks.admin_or_permissions()
    async def setjailrole(self, ctx, role: discord.Role):
        role_id = role.id
        await self.config.guild(ctx.guild).jailed_role.set(role_id)

    @commands.command()
    @checks.admin_or_permissions()
    async def forcebail(self, ctx, user: discord.Member):
        """This command is if any runtime error caused during bailing or jailing, this might not work"""
        lst = await self.config.member(user).roles()
        await self.config.member(user).is_jailed.set(False)
        for roleid in lst:
            role =  ctx.guild.get_role(roleid)
            await user.add_roles(role)
        await self.config.member(user).roles.clear()
        await ctx.send("Done... this might not have worked")

    
        

    


        
