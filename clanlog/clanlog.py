import logging
from typing import Optional

import discord
from redbot.core.bot import Red
from redbot.core import Config, checks, commands

log = logging.getLogger("red.cogs.clanlog")


class NoClansCog(Exception):
    pass


class ClanLog(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=6942053)
        default_global = {
            "global_log_channel": None,
        }
        self.config.register_global(**default_global)

        try:
            # for auto-completion :)
            from clashroyaleclansv2 import ClashRoyaleClans2
            self.crclans: ClashRoyaleClans2 = self.bot.get_cog("ClashRoyaleClans2")
            if self.crclans is None:
                log.error("Load clashroyaleclans cog for this cog to work.")
                raise NoClansCog
        except:
            pass

    @commands.Cog.listener(name="on_clandata_update")
    async def on_clandata_update(self, old_data, new_data):
        def get_role_hierarchy(role):
            hierarchy = {"member": 1, "elder": 2, "coleader": 3, "leader": 4}
            if role.lower() not in hierarchy.keys():
                log.error(f"Cannot find hierarchy for role {role.lower() or 'None'}")
                return 0
            return hierarchy[role.lower()]

        log_channel_id = await self.config.global_log_channel()
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel is None:
            log.error("Global log channel is not setup correctly.")
            return

        # old_data = kwargs.get("old_data")
        # new_data = kwargs.get("new_data")
        if len(old_data) == 0 or old_data is None:
                log.error("Old data is " + old_data)
                return
        if len(new_data) == 0 or new_data is None:
                log.error("New data is " + new_data)
                return
        for key, data in new_data.items():
            clan_log_channel = self.crclans.get_static_clandata(key).get("log_channel", None)
            if clan_log_channel:
                clan_log_channel = self.bot.get_channel(clan_log_channel)

            old_members_data = {}
            new_members_data = {}
            # When a clan is added
            if key not in old_data.keys():
                log.error(f"Clan {key} not found in old_data.")
                continue
            for member_data in old_data[key]["member_list"]:
                old_members_data[member_data["tag"]] = member_data
            for member_data in data["member_list"]:
                new_members_data[member_data["tag"]] = member_data

            # Process promotions and demotions
            common_members = set(old_members_data.keys()).intersection(new_members_data.keys())
            description = ""
            for member in common_members:
                old_role = old_members_data[member].get("role", "")
                old_role_index = get_role_hierarchy(old_role)
                new_role = new_members_data[member].get("role", "")
                new_role_index = get_role_hierarchy(new_role)
                if old_role_index == new_role_index:
                    continue
                if old_role_index > new_role_index:
                    description += f"Demotion: {old_role} ⇒ {new_role}\n"
                if old_role_index < new_role_index:
                    description += f"Promotion: {old_role} ⇒ {new_role}\n"
                description += f"{old_members_data[member]['name']} ({old_members_data[member]['tag']})\n"
            if description:
                embed = discord.Embed(
                    title="Member Edited {data['name']} ({data['tag']})",
                    description=description,
                    colour=discord.Colour.blue(),
                )
                await log_channel.send(embed=embed)
                if clan_log_channel:
                    await clan_log_channel.send(embed=embed)

            # Process members data
            total = set(list(new_members_data.keys())).union(
                set(list(old_members_data.keys()))
            )
            players_left_clan = set(total - set(new_members_data.keys()))
            players_joined_clan = set(total - set(old_members_data.keys()))

            description = ""
            for player_tag in players_left_clan:
                player_name = old_members_data.get(player_tag, {}).get("name", "Unnamed Player")
                sad_emote = self.bot.get_emoji(592001717311242241) or ""
                description += "{}({}) has left {} {}\n".format(
                    player_name, player_tag, data["name"], sad_emote
                )
            if description:
                embed = discord.Embed(
                    title="Member Left",
                    description=description,
                    colour=discord.Colour.blue(),
                )
                await log_channel.send(embed=embed)
                if clan_log_channel:
                    await clan_log_channel.send(embed=embed)
            description = ""
            for player_tag in players_joined_clan:
                player_name = new_members_data.get(player_tag, {}).get("name", "Unnamed Player")
                happy_emote = self.bot.get_emoji(375143193630605332) or ""
                description += "{}({}) has joined {} {}\n".format(
                    player_name, player_tag, key, happy_emote
                )
            if description:
                embed = discord.Embed(
                    title="Member Joined",
                    description=description,
                    colour=discord.Colour.blue(),
                )
                await log_channel.send(embed=embed)
                if clan_log_channel:
                    await clan_log_channel.send(embed=embed)

    @commands.group(name="clanlogset")
    async def clanlogset(self, ctx):
        pass

    @clanlogset.command(name="global_log")
    @checks.is_owner()
    async def clanlogset_global_log_channel(self, ctx, channel: Optional[discord.TextChannel] = None):
        if channel is None:
            await self.config.global_log_channel.set(channel)
            await ctx.send("Disabled global clanlog")
            await ctx.tick()
            return
        await self.config.global_log_channel.set(channel.id)
        await ctx.send("Global clanlog channel has been set to {}".format(channel.mention))
        await ctx.tick()
