from .rolesync import RoleSync

def setup(bot):
    bot.add_cog(RoleSync(bot))