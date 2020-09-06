import datetime
import discord
import asyncio
import logging

from discord.ext.commands.converter import Converter
from discord.ext.commands.errors import BadArgument

from redbot.core import commands, Config, modlog, VersionInfo, version_info
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import humanize_list, inline, escape

from typing import Union, cast, Sequence

_ = Translator("ExtendedModLog", __file__)
logger = logging.getLogger("red.trusty-cogs.ExtendedModLog")


class CommandPrivs(Converter):
    """
        Converter for command privliges
    """

    async def convert(self, ctx: commands.Context, argument: str) -> str:
        levels = ["MOD", "ADMIN", "BOT_OWNER", "GUILD_OWNER", "NONE"]
        result = None
        if argument.upper() in levels:
            result = argument.upper()
        if argument == "all":
            result = "NONE"
        if not result:
            raise BadArgument(
                _("`{arg}` is not an available command permission.").format(arg=argument)
            )
        return result


class EventChooser(Converter):
    """
        Converter for command privliges
    """

    async def convert(self, ctx: commands.Context, argument: str) -> str:
        options = [
            "message_edit",
            "message_delete",
            "user_change",
            "role_change",
            "role_create",
            "role_delete",
            "voice_change",
            "user_join",
            "user_left",
            "channel_change",
            "channel_create",
            "channel_delete",
            "guild_change",
            "emoji_change",
            "commands_used",
            "invite_created",
            "invite_deleted",
        ]
        result = None
        if argument.lower() in options:
            result = argument.lower()
        if not result:
            raise BadArgument(_("`{arg}` is not an available event option.").format(arg=argument))
        return result


@cog_i18n(_)
class EventMixin:
    """
        Handles all the on_event data
    """

    def __init__(self, *args):
        self.config: Config
        self.bot: Red
        self.settings: dict

    async def get_colour(self, channel: discord.TextChannel) -> discord.Colour:
        try:
            if await self.bot.db.guild(channel.guild).use_bot_color():
                return channel.guild.me.colour
            else:
                return await self.bot.db.color()
        except AttributeError:
            return await self.bot.get_embed_colour(channel)

    async def get_event_colour(
        self, guild: discord.Guild, event_type: str, changed_object: Union[discord.Role] = None
    ) -> discord.Colour:
        if guild.text_channels:
            cmd_colour = await self.get_colour(guild.text_channels[0])
        else:
            cmd_colour = discord.Colour.red()
        defaults = {
            "message_edit": discord.Colour.orange(),
            "message_delete": discord.Colour.dark_red(),
            "user_change": discord.Colour.greyple(),
            "role_change": changed_object.colour if changed_object else discord.Colour.blue(),
            "role_create": discord.Colour.blue(),
            "role_delete": discord.Colour.dark_blue(),
            "voice_change": discord.Colour.magenta(),
            "user_join": discord.Colour.green(),
            "user_left": discord.Colour.dark_green(),
            "channel_change": discord.Colour.teal(),
            "channel_create": discord.Colour.teal(),
            "channel_delete": discord.Colour.dark_teal(),
            "guild_change": discord.Colour.blurple(),
            "emoji_change": discord.Colour.gold(),
            "commands_used": cmd_colour,
            "invite_created": discord.Colour.blurple(),
            "invite_deleted": discord.Colour.blurple(),
        }
        colour = defaults[event_type]
        if self.settings[guild.id][event_type]["colour"] is not None:
            colour = discord.Colour(self.settings[guild.id][event_type]["colour"])
        return colour

    async def is_ignored_channel(self, guild: discord.Guild, channel: discord.abc.GuildChannel):
        ignored_channels = self.settings[guild.id]["ignored_channels"]
        if channel.id in ignored_channels:
            return True
        if channel.category and channel.category.id in ignored_channels:
            return True
        return False

    async def member_can_run(self, ctx: commands.Context) -> bool:
        """Check if a user can run a command.
        This will take the current context into account, such as the
        server and text channel.
        https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/release/3.0.0/redbot/cogs/permissions/permissions.py
        """
        command = ctx.message.content.replace(ctx.prefix, "")
        com = ctx.bot.get_command(command)
        if com is None:
            return False
        else:
            try:
                testcontext = await ctx.bot.get_context(ctx.message, cls=commands.Context)
                to_check = [*reversed(com.parents)] + [com]
                can = False
                for cmd in to_check:
                    can = await cmd.can_run(testcontext)
                    if can is False:
                        break
            except commands.CheckFailure:
                can = False
        return can

    async def modlog_channel(self, guild: discord.Guild, event: str) -> discord.TextChannel:
        channel = None
        settings = self.settings[guild.id].get(event)
        if "channel" in settings and settings["channel"]:
            channel = guild.get_channel(settings["channel"])
        if channel is None:
            try:
                channel = await modlog.get_modlog_channel(guild)
            except RuntimeError:
                raise RuntimeError("No Modlog set")
        if not channel.permissions_for(guild.me).send_messages:
            raise RuntimeError("No permission to send messages in channel")
        return channel

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        if guild is None:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, ctx.guild):
                return
        if guild.id not in self.settings:
            return
        if not self.settings[guild.id]["commands_used"]["enabled"]:
            return
        if await self.is_ignored_channel(ctx.guild, ctx.channel):
            return
        try:
            channel = await self.modlog_channel(guild, "commands_used")
        except RuntimeError:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["commands_used"]["embed"]
        )
        time = ctx.message.created_at
        message = ctx.message
        can_run = await self.member_can_run(ctx)
        command = ctx.message.content.replace(ctx.prefix, "")
        try:
            privs = self.bot.get_command(command).requires.privilege_level.name
        except Exception:
            return
        if privs not in self.settings[guild.id]["commands_used"]["privs"]:
            logger.debug(f"command not in list {privs}")
            return

        if privs == "MOD":
            try:
                mod_role_list = await ctx.bot.db.guild(guild).mod_role()
            except AttributeError:
                mod_role_list = await ctx.bot.get_mod_roles(guild)
            if mod_role_list != []:
                good_mod_roles = [guild.get_role(mr) for mr in mod_role_list]
                role = ", ".join(r.mention for r in good_mod_roles if r is not None) + f"\n{privs}"
            else:
                role = _("Not Set\nMOD")
        elif privs == "ADMIN":
            try:
                admin_role_list = await ctx.bot.db.guild(guild).admin_role()
            except AttributeError:
                admin_role_list = await ctx.bot.get_admin_roles(guild)
            if admin_role_list != []:
                good_admin_roles = [guild.get_role(ar) for ar in admin_role_list]
                role = (
                    ", ".join(r.mention for r in good_admin_roles if r is not None) + f"\n{privs}"
                )
            else:
                role = _("Not Set\nADMIN")
        elif privs == "BOT_OWNER":
            role = f"<@!{ctx.bot.owner_id}>\n{privs}"
        elif privs == "GUILD_OWNER":
            role = guild.owner.mention + f"\n{privs}"
        else:
            role = f"everyone\n{privs}"

        infomessage = _(
            "{emoji} `{time}` {author}(`{a_id}`) used the following command in {channel}\n> {com}"
        ).format(
            emoji=self.settings[guild.id]["commands_used"]["emoji"],
            time=message.created_at.strftime("%H:%M:%S"),
            author=message.author,
            a_id=message.author.id,
            channel=message.channel.mention,
            com=message.content,
        )
        if embed_links:
            embed = discord.Embed(
                description=message.content,
                colour=await self.get_event_colour(guild, "commands_used"),
                timestamp=time,
            )
            embed.add_field(name=_("Channel"), value=message.channel.mention)
            embed.add_field(name=_("Can Run"), value=str(can_run))
            embed.add_field(name=_("Required Role"), value=role)
            embed.set_footer(text=_("User ID: ") + str(message.author.id))
            author_title = _("{member} ({m_id})- Used a Command").format(
                member=message.author, m_id=message.author.id
            )
            embed.set_author(name=author_title, icon_url=message.author.avatar_url)
            await channel.send(embed=embed)
        else:
            await channel.send(infomessage[:2000])

    @commands.Cog.listener(name="on_raw_message_delete")
    async def on_raw_message_delete_listener(
        self, payload: discord.RawMessageDeleteEvent, *, check_audit_log: bool = True
    ) -> None:
        # custom name of method used, because this is only supported in Red 3.1+
        guild_id = payload.guild_id
        if guild_id is None:
            return
        guild = self.bot.get_guild(guild_id)
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        # settings = await self.config.guild(guild).message_delete()
        settings = self.settings[guild.id]["message_delete"]
        if not settings["enabled"]:
            return
        channel_id = payload.channel_id
        try:
            channel = await self.modlog_channel(guild, "message_delete")
        except RuntimeError:
            return
        if await self.is_ignored_channel(guild, guild.get_channel(channel_id)):
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["message_delete"]["embed"]
        )
        message = payload.cached_message
        if message is None:
            if settings["cached_only"]:
                return
            message_channel = guild.get_channel(channel_id)
            if embed_links:
                embed = discord.Embed(
                    description=_("*Message's content unknown.*"),
                    colour=await self.get_event_colour(guild, "message_delete"),
                )
                embed.add_field(name=_("Channel"), value=message_channel.mention)
                embed.set_author(name=_("Deleted Message"))
                await channel.send(embed=embed)
            else:
                infomessage = _("{emoji} `{time}` A message was deleted in {channel}").format(
                    emoji=settings["emoji"],
                    time=datetime.datetime.utcnow().strftime("%H:%M:%S"),
                    channel=message_channel.mention,
                )
                await channel.send(f"{infomessage}\n> *Message's content unknown.*")
            return
        await self._cached_message_delete(
            message, guild, settings, channel, check_audit_log=check_audit_log
        )

    async def _cached_message_delete(
        self,
        message: discord.Message,
        guild: discord.Guild,
        settings: dict,
        channel: discord.TextChannel,
        *,
        check_audit_log: bool = True,
    ) -> None:
        if message.author.bot and not settings["bots"]:
            # return to ignore bot accounts if enabled
            return
        if message.content == "" and message.attachments == []:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["message_delete"]["embed"]
        )
        time = message.created_at
        perp = None
        if channel.permissions_for(guild.me).view_audit_log and check_audit_log:
            action = discord.AuditLogAction.message_delete
            async for log in guild.audit_logs(limit=2, action=action):
                same_chan = log.extra.channel.id == message.channel.id
                if log.target.id == message.author.id and same_chan:
                    perp = f"{log.user}({log.user.id})"
                    break
        message_channel = cast(discord.TextChannel, message.channel)
        author = message.author
        if perp is None:
            infomessage = _(
                "{emoji} `{time}` A message from **{author}** (`{a_id}`) was deleted in {channel}"
            ).format(
                emoji=settings["emoji"],
                time=time.strftime("%H:%M:%S"),
                author=author,
                channel=message_channel.mention,
                a_id=author.id,
            )
        else:
            infomessage = _(
                "{emoji} `{time}` {perp} deleted a message from "
                "**{author}** (`{a_id}`) in {channel}"
            ).format(
                emoji=settings["emoji"],
                time=time.strftime("%H:%M:%S"),
                perp=perp,
                author=author,
                a_id=author.id,
                channel=message_channel.mention,
            )
        if embed_links:
            embed = discord.Embed(
                description=message.content,
                colour=await self.get_event_colour(guild, "message_delete"),
                timestamp=time,
            )

            embed.add_field(name=_("Channel"), value=message_channel.mention)
            if perp:
                embed.add_field(name=_("Deleted by"), value=perp)
            if message.attachments:
                files = ", ".join(a.filename for a in message.attachments)
                if len(message.attachments) > 1:
                    files = files[:-2]
                embed.add_field(name=_("Attachments"), value=files)
            embed.set_footer(text=_("User ID: ") + str(message.author.id))
            embed.set_author(
                name=_("{member} ({m_id})- Deleted Message").format(member=author, m_id=author.id),
                icon_url=str(message.author.avatar_url),
            )
            await channel.send(embed=embed)
        else:
            clean_msg = escape(message.clean_content, mass_mentions=True)[
                : (1990 - len(infomessage))
            ]
            await channel.send(f"{infomessage}\n>>> {clean_msg}")

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        guild_id = payload.guild_id
        if guild_id is None:
            return
        guild = self.bot.get_guild(guild_id)
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        settings = self.settings[guild.id]["message_delete"]
        if not settings["enabled"] or not settings["bulk_enabled"]:
            return
        channel_id = payload.channel_id
        message_channel = guild.get_channel(channel_id)
        try:
            channel = await self.modlog_channel(guild, "message_delete")
        except RuntimeError:
            return
        if await self.is_ignored_channel(guild, message_channel):
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["message_delete"]["embed"]
        )
        message_amount = len(payload.message_ids)
        if embed_links:
            embed = discord.Embed(
                description=message_channel.mention,
                colour=await self.get_event_colour(guild, "message_delete"),
            )
            embed.set_author(name=_("Bulk message delete"), icon_url=guild.icon_url)
            embed.add_field(name=_("Channel"), value=message_channel.mention)
            embed.add_field(name=_("Messages deleted"), value=str(message_amount))
            await channel.send(embed=embed)
        else:
            infomessage = _(
                "{emoji} `{time}` Bulk message delete in {channel}, {amount} messages deleted."
            ).format(
                emoji=settings["emoji"],
                time=datetime.datetime.utcnow().strftime("%H:%M:%S"),
                amount=message_amount,
                channel=message_channel.mention,
            )
            await channel.send(infomessage)
        if settings["bulk_individual"]:
            for message in payload.cached_messages:
                new_payload = discord.RawMessageDeleteEvent(
                    {"id": message.id, "channel_id": channel_id, "guild_id": guild_id}
                )
                new_payload.cached_message = message
                try:
                    await self.on_raw_message_delete_listener(new_payload, check_audit_log=False)
                except Exception:
                    pass

    async def invite_links_loop(self) -> None:
        """Check every 5 minutes for updates to the invite links"""
        if version_info >= VersionInfo.from_str("3.2.0"):
            await self.bot.wait_until_red_ready()
        else:
            await self.bot.wait_until_ready()
        while self is self.bot.get_cog("ExtendedModLog"):
            for guild_id in self.settings:
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    continue
                if self.settings[guild_id]["user_join"]["enabled"]:
                    await self.save_invite_links(guild)
            await asyncio.sleep(300)

    async def save_invite_links(self, guild: discord.Guild) -> bool:
        invites = {}
        if not guild.me.guild_permissions.manage_guild:
            return False
        for invite in await guild.invites():
            try:

                created_at = getattr(invite, "created_at", datetime.datetime.utcnow())
                channel = getattr(invite, "channel", discord.Object(id=0))
                inviter = getattr(invite, "inviter", discord.Object(id=0))
                invites[invite.code] = {
                    "uses": getattr(invite, "uses", 0),
                    "max_age": getattr(invite, "max_age", None),
                    "created_at": created_at.timestamp(),
                    "max_uses": getattr(invite, "max_uses", None),
                    "temporary": getattr(invite, "temporary", False),
                    "inviter": inviter.id,
                    "channel": channel.id,
                }
            except Exception:
                logger.exception("Error saving invites.")
                pass
        await self.config.guild(guild).invite_links.set(invites)
        return True

    async def get_invite_link(self, guild: discord.Guild) -> str:
        manage_guild = guild.me.guild_permissions.manage_guild
        # invites = await self.config.guild(guild).invite_links()
        invites = self.settings[guild.id]["invite_links"]
        possible_link = ""
        check_logs = manage_guild and guild.me.guild_permissions.view_audit_log
        if manage_guild and "VANITY_URL" in guild.features:
            possible_link = str(await guild.vanity_invite())
        if invites and manage_guild:
            guild_invites = await guild.invites()
            for invite in guild_invites:
                if invite.code in invites:
                    uses = invites[invite.code]["uses"]
                    # logger.info(f"{invite.code}: {invite.uses} - {uses}")
                    if invite.uses > uses:
                        possible_link = _(
                            "https://discord.gg/{code}\nInvited by: {inviter}"
                        ).format(code=invite.code, inviter=str(invite.inviter))

            if not possible_link:
                for code, data in invites.items():
                    try:
                        invite = await self.bot.fetch_invite(code)
                    except (
                        discord.errors.NotFound,
                        discord.errors.HTTPException,
                        Exception,
                    ):
                        logger.error("Error getting invite {code}".format(code=code))
                        invite = None
                        pass
                    if not invite:
                        if (data["max_uses"] - data["uses"]) == 1:
                            # The invite link was on its last uses and subsequently
                            # deleted so we're fairly sure this was the one used
                            try:
                                inviter = await self.bot.fetch_user(data["inviter"])
                            except (discord.errors.NotFound, discord.errors.Forbidden):
                                inviter = _("Unknown or deleted user ({inviter})").format(
                                    inviter=data["inviter"]
                                )
                            possible_link = _(
                                "https://discord.gg/{code}\nInvited by: {inviter}"
                            ).format(code=code, inviter=str(inviter))
            await self.save_invite_links(guild)  # Save all the invites again since they've changed
        if check_logs and not possible_link:
            action = discord.AuditLogAction.invite_create
            async for log in guild.audit_logs(action=action):
                if log.target.code not in invites:
                    possible_link = _("https://discord.gg/{code}\nInvited by: {inviter}").format(
                        code=log.target.code, inviter=str(log.target.inviter)
                    )
                    break
        return possible_link

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        if guild.id not in self.settings:
            return
        if not self.settings[guild.id]["user_join"]["enabled"]:
            return
        # if not await self.config.guild(guild).user_join.enabled():
        # return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        try:
            channel = await self.modlog_channel(guild, "user_join")
        except RuntimeError:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["user_join"]["embed"]
        )
        time = datetime.datetime.utcnow()
        users = len(guild.members)
        # https://github.com/Cog-Creators/Red-DiscordBot/blob/develop/cogs/general.py
        since_created = (time - member.created_at).days
        user_created = member.created_at.strftime("%d %b %Y %H:%M")

        created_on = "{}\n({} days ago)".format(user_created, since_created)

        possible_link = await self.get_invite_link(guild)
        if embed_links:
            embed = discord.Embed(
                description=member.mention,
                colour=await self.get_event_colour(guild, "user_join"),
                timestamp=member.joined_at if member.joined_at else datetime.datetime.utcnow(),
            )
            embed.add_field(name=_("Total Users:"), value=str(users))
            embed.add_field(name=_("Account created on:"), value=created_on)
            embed.set_footer(text=_("User ID: ") + str(member.id))
            embed.set_author(
                name=_("{member} ({m_id}) has joined the guild").format(
                    member=member, m_id=member.id
                ),
                url=member.avatar_url,
                icon_url=member.avatar_url,
            )
            if possible_link:
                embed.add_field(name=_("Invite Link"), value=possible_link)
            embed.set_thumbnail(url=member.avatar_url)
            await channel.send(embed=embed)
        else:
            time = datetime.datetime.utcnow()
            msg = _(
                "{emoji} `{time}` **{member}**(`{m_id}`) "
                "joined the guild. Total members: {users}"
            ).format(
                emoji=self.settings[guild.id]["user_join"]["emoji"],
                time=time.strftime("%H:%M:%S"),
                member=member,
                m_id=member.id,
                users=users,
            )
            await channel.send(msg)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        if guild.id not in self.settings:
            return
        if not self.settings[guild.id]["user_left"]["enabled"]:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        try:
            channel = await self.modlog_channel(guild, "user_left")
        except RuntimeError:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["user_left"]["embed"]
        )
        time = datetime.datetime.utcnow()
        check_after = time + datetime.timedelta(minutes=-30)
        perp = None
        reason = None
        if channel.permissions_for(guild.me).view_audit_log:
            action = discord.AuditLogAction.kick
            async for log in guild.audit_logs(limit=5, after=check_after, action=action):
                if log.target.id == member.id:
                    perp = log.user
                    reason = log.reason
                    break
        if embed_links:
            embed = discord.Embed(
                description=member.mention,
                colour=await self.get_event_colour(guild, "user_left"),
                timestamp=time,
            )
            embed.add_field(name=_("Total Users:"), value=str(len(guild.members)))
            if perp:
                embed.add_field(name=_("Kicked"), value=perp.mention)
            if reason:
                embed.add_field(name=_("Reason"), value=str(reason))
            embed.set_footer(text=_("User ID: ") + str(member.id))
            embed.set_author(
                name=_("{member} ({m_id}) has left the guild").format(
                    member=member, m_id=member.id
                ),
                url=member.avatar_url,
                icon_url=member.avatar_url,
            )
            embed.set_thumbnail(url=member.avatar_url)
            await channel.send(embed=embed)
        else:
            time = datetime.datetime.utcnow()
            msg = _(
                "{emoji} `{time}` **{member}**(`{m_id}`) left the guild. Total members: {users}"
            ).format(
                emoji=self.settings[guild.id]["user_left"]["emoji"],
                time=time.strftime("%H:%M:%S"),
                member=member,
                m_id=member.id,
                users=len(guild.members),
            )
            if perp:
                msg = _(
                    "{emoji} `{time}` **{member}**(`{m_id}`) "
                    "was kicked by {perp}. Total members: {users}"
                ).format(
                    emoji=self.settings[guild.id]["user_left"]["emoji"],
                    time=time.strftime("%H:%M:%S"),
                    member=member,
                    m_id=member.id,
                    perp=perp,
                    users=len(guild.members),
                )
            await channel.send(msg)

    async def get_permission_change(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel, embed_links: bool
    ) -> str:
        p_msg = ""
        before_perms = {}
        after_perms = {}
        for o, p in before.overwrites.items():
            before_perms[str(o.id)] = [i for i in p]
        for o, p in after.overwrites.items():
            after_perms[str(o.id)] = [i for i in p]
        for entity in before_perms:
            entity_obj = before.guild.get_role(int(entity))
            if not entity_obj:
                entity_obj = before.guild.get_member(int(entity))
            if entity not in after_perms:
                if not embed_links:
                    p_msg += f"{entity_obj.name} Overwrites removed.\n"
                else:
                    p_msg += f"{entity_obj.mention} Overwrites removed.\n"
                continue
            if after_perms[entity] != before_perms[entity]:
                a = set(after_perms[entity])
                b = set(before_perms[entity])
                a_perms = list(a - b)
                for diff in a_perms:
                    if not embed_links:
                        p_msg += f"{entity_obj.name} {diff[0]} Set to {diff[1]}\n"
                    else:
                        p_msg += f"{entity_obj.mention} {diff[0]} Set to {diff[1]}\n"
        for entity in after_perms:
            entity_obj = after.guild.get_role(int(entity))
            if not entity_obj:
                entity_obj = after.guild.get_member(int(entity))
            if entity not in before_perms:
                if not embed_links:
                    p_msg += f"{entity_obj.name} Overwrites added.\n"
                else:
                    p_msg += f"{entity_obj.mention} Overwrites added.\n"
                continue
        return p_msg

    @commands.Cog.listener()
    async def on_guild_channel_create(self, new_channel: discord.abc.GuildChannel) -> None:
        guild = new_channel.guild
        if guild.id not in self.settings:
            return
        if not self.settings[guild.id]["channel_create"]["enabled"]:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if await self.is_ignored_channel(guild, new_channel):
            return
        try:
            channel = await self.modlog_channel(guild, "channel_create")
        except RuntimeError:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["channel_create"]["embed"]
        )
        time = datetime.datetime.utcnow()
        channel_type = str(new_channel.type).title()
        embed = discord.Embed(
            description=f"{new_channel.mention} {new_channel.name}",
            timestamp=time,
            colour=await self.get_event_colour(guild, "channel_create"),
        )
        embed.set_author(
            name=_("{chan_type} Channel Created {chan_name} ({chan_id})").format(
                chan_type=channel_type, chan_name=new_channel.name, chan_id=new_channel.id
            )
        )
        # msg = _("Channel Created ") + str(new_channel.id) + "\n"
        perp = None
        reason = None
        if channel.permissions_for(guild.me).view_audit_log:
            action = discord.AuditLogAction.channel_create
            async for log in guild.audit_logs(limit=2, action=action):
                if log.target.id == new_channel.id:
                    perp = log.user
                    if log.reason:
                        reason = log.reason
                    break

        perp_msg = ""
        embed.add_field(name=_("Type"), value=channel_type)
        if perp:
            perp_msg = _("by {perp} (`{perp_id}`)").format(perp=perp, perp_id=perp.id)
            embed.add_field(name=_("Created by "), value=perp.mention)
        if reason:
            perp_msg += _(" Reason: {reason}").format(reason=reason)
            embed.add_field(name=_("Reason "), value=reason)
        msg = _("{emoji} `{time}` {chan_type} channel created {perp_msg} {channel}").format(
            emoji=self.settings[guild.id]["channel_create"]["emoji"],
            time=time.strftime("%H:%M:%S"),
            chan_type=channel_type,
            perp_msg=perp_msg,
            channel=new_channel.mention,
        )
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(msg)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, old_channel: discord.abc.GuildChannel):
        guild = old_channel.guild
        if guild.id not in self.settings:
            return
        if not self.settings[guild.id]["channel_delete"]["enabled"]:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if await self.is_ignored_channel(guild, old_channel):
            return
        try:
            channel = await self.modlog_channel(guild, "channel_delete")
        except RuntimeError:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["channel_delete"]["embed"]
        )
        channel_type = str(old_channel.type).title()
        time = datetime.datetime.utcnow()
        embed = discord.Embed(
            description=old_channel.name,
            timestamp=time,
            colour=await self.get_event_colour(guild, "channel_delete"),
        )
        embed.set_author(
            name=_("{chan_type} Channel Deleted {chan_name} ({chan_id})").format(
                chan_type=channel_type, chan_name=old_channel.name, chan_id=old_channel.id
            )
        )
        perp = None
        reason = None
        if channel.permissions_for(guild.me).view_audit_log:
            action = discord.AuditLogAction.channel_delete
            async for log in guild.audit_logs(limit=2, action=action):
                if log.target.id == old_channel.id:
                    perp = log.user
                    if log.reason:
                        reason = log.reason
                    break
        perp_msg = ""
        embed.add_field(name=_("Type"), value=channel_type)
        if perp:
            perp_msg = _("by {perp} (`{perp_id}`)").format(perp=perp, perp_id=perp.id)
            embed.add_field(name=_("Deleted by "), value=perp.mention)
        if reason:
            perp_msg += _(" Reason: {reason}").format(reason=reason)
            embed.add_field(name=_("Reason "), value=reason)
        msg = _("{emoji} `{time}` {chan_type} channel deleted {perp_msg} {channel}").format(
            emoji=self.settings[guild.id]["channel_delete"]["emoji"],
            time=time.strftime("%H:%M:%S"),
            chan_type=channel_type,
            perp_msg=perp_msg,
            channel=f"#{old_channel.name} ({old_channel.id})",
        )
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(msg)

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ) -> None:
        guild = before.guild
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if not self.settings[guild.id]["channel_change"]["enabled"]:
            return
        try:
            channel = await self.modlog_channel(guild, "channel_change")
        except RuntimeError:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["channel_change"]["embed"]
        )
        channel_type = str(after.type).title()
        time = datetime.datetime.utcnow()
        embed = discord.Embed(
            description=after.mention,
            timestamp=time,
            colour=await self.get_event_colour(guild, "channel_create"),
        )
        embed.set_author(
            name=_("{chan_type} Channel Updated {chan_name} ({chan_id})").format(
                chan_type=channel_type, chan_name=before.name, chan_id=before.id
            )
        )
        msg = _("{emoji} `{time}` Updated channel {channel}\n").format(
            emoji=self.settings[guild.id]["channel_change"]["emoji"],
            time=time.strftime("%H:%M:%S"),
            channel=before.name,
        )
        perp = None
        reason = None
        worth_updating = False
        if channel.permissions_for(guild.me).view_audit_log:
            action = discord.AuditLogAction.channel_update
            async for log in guild.audit_logs(limit=5, action=action):
                if log.target.id == before.id:
                    perp = log.user
                    if log.reason:
                        reason = log.reason
                    break
        if type(before) == discord.TextChannel:
            text_updates = {
                "name": _("Name:"),
                "topic": _("Topic:"),
                "category": _("Category:"),
                "slowmode_delay": _("Slowmode delay:"),
            }

            for attr, name in text_updates.items():
                before_attr = getattr(before, attr)
                after_attr = getattr(after, attr)
                if before_attr != after_attr:
                    worth_updating = True
                    if before_attr == "":
                        before_attr = "None"
                    if after_attr == "":
                        after_attr = "None"
                    msg += _("Before ") + f"{name} {before_attr}\n"
                    msg += _("After ") + f"{name} {after_attr}\n"
                    embed.add_field(name=_("Before ") + name, value=str(before_attr)[:1024])
                    embed.add_field(name=_("After ") + name, value=str(after_attr)[:1024])
            if before.is_nsfw() != after.is_nsfw():
                worth_updating = True
                msg += _("Before ") + f"NSFW {before.is_nsfw()}\n"
                msg += _("After ") + f"NSFW {after.is_nsfw()}\n"
                embed.add_field(name=_("Before ") + "NSFW", value=str(before.is_nsfw()))
                embed.add_field(name=_("After ") + "NSFW", value=str(after.is_nsfw()))
            p_msg = await self.get_permission_change(before, after, embed_links)
            if p_msg != "":
                worth_updating = True
                msg += _("Permissions Changed: ") + p_msg
                embed.add_field(name=_("Permissions"), value=p_msg[:1024])

        if type(before) == discord.VoiceChannel:
            voice_updates = {
                "name": _("Name:"),
                "position": _("Position:"),
                "category": _("Category:"),
                "bitrate": _("Bitrate:"),
                "user_limit": _("User limit:"),
            }
            for attr, name in voice_updates.items():
                before_attr = getattr(before, attr)
                after_attr = getattr(after, attr)
                if before_attr != after_attr:
                    worth_updating = True
                    msg += _("Before ") + f"{name} {before_attr}\n"
                    msg += _("After ") + f"{name} {after_attr}\n"
                    embed.add_field(name=_("Before ") + name, value=str(before_attr))
                    embed.add_field(name=_("After ") + name, value=str(after_attr))
            p_msg = await self.get_permission_change(before, after, embed_links)
            if p_msg != "":
                worth_updating = True
                msg += _("Permissions Changed: ") + p_msg
                embed.add_field(name=_("Permissions"), value=p_msg[:1024])

        if perp:
            msg += _("Updated by ") + str(perp) + "\n"
            embed.add_field(name=_("Updated by "), value=perp.mention)
        if reason:
            msg += _("Reason ") + reason + "\n"
            embed.add_field(name=_("Reason "), value=reason)
        if not worth_updating:
            return
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(escape(msg, mass_mentions=True))

    async def get_role_permission_change(self, before: discord.Role, after: discord.Role) -> str:
        permission_list = [
            "create_instant_invite",
            "kick_members",
            "ban_members",
            "administrator",
            "manage_channels",
            "manage_guild",
            "add_reactions",
            "view_audit_log",
            "priority_speaker",
            "read_messages",
            "send_messages",
            "send_tts_messages",
            "manage_messages",
            "embed_links",
            "attach_files",
            "read_message_history",
            "mention_everyone",
            "external_emojis",
            "connect",
            "speak",
            "mute_members",
            "deafen_members",
            "move_members",
            "use_voice_activation",
            "change_nickname",
            "manage_nicknames",
            "manage_roles",
            "manage_webhooks",
            "manage_emojis",
        ]
        p_msg = ""
        for p in permission_list:
            if getattr(before.permissions, p) != getattr(after.permissions, p):
                change = getattr(after.permissions, p)
                p_msg += f"{p} Set to {change}\n"
        return p_msg

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        guild = before.guild
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if not self.settings[guild.id]["role_change"]["enabled"]:
            return
        try:
            channel = await self.modlog_channel(guild, "role_change")
        except RuntimeError:
            return
        perp = None
        reason = None
        if channel.permissions_for(guild.me).view_audit_log:
            action = discord.AuditLogAction.role_update
            async for log in guild.audit_logs(limit=5, action=action):
                if log.target.id == before.id:
                    perp = log.user
                    if log.reason:
                        reason = log.reason
                    break
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["role_change"]["embed"]
        )
        time = datetime.datetime.utcnow()
        embed = discord.Embed(description=after.mention, colour=after.colour, timestamp=time)
        msg = _("{emoji} `{time}` Updated role **{role}**\n").format(
            emoji=self.settings[guild.id]["role_change"]["emoji"],
            time=time.strftime("%H:%M:%S"),
            role=before.name,
        )
        if after is guild.default_role:
            embed.set_author(name=_("Updated @everyone role "))
        else:
            embed.set_author(
                name=_("Updated {role} ({r_id}) role ").format(role=before.name, r_id=before.id)
            )
        if perp:
            msg += _("Updated by ") + str(perp) + "\n"
            embed.add_field(name=_("Updated by "), value=perp.mention)
        if reason:
            msg += _("Reason ") + reason + "\n"
            embed.add_field(name=_("Reason "), value=reason)
        role_updates = {
            "name": _("Name:"),
            "color": _("Colour:"),
            "mentionable": _("Mentionable:"),
            "hoist": _("Is Hoisted:"),
        }
        worth_updating = False
        for attr, name in role_updates.items():
            before_attr = getattr(before, attr)
            after_attr = getattr(after, attr)
            if before_attr != after_attr:
                worth_updating = True
                if before_attr == "":
                    before_attr = "None"
                if after_attr == "":
                    after_attr = "None"
                msg += _("Before ") + f"{name} {before_attr}\n"
                msg += _("After ") + f"{name} {after_attr}\n"
                embed.add_field(name=_("Before ") + name, value=str(before_attr))
                embed.add_field(name=_("After ") + name, value=str(after_attr))
        p_msg = await self.get_role_permission_change(before, after)
        if p_msg != "":
            worth_updating = True
            msg += _("Permissions Changed: ") + p_msg
            embed.add_field(name=_("Permissions"), value=p_msg[:1024])
        if not worth_updating:
            return
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(msg)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        guild = role.guild
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if not self.settings[guild.id]["role_create"]["enabled"]:
            return
        try:
            channel = await self.modlog_channel(guild, "role_change")
        except RuntimeError:
            return
        perp = None
        reason = None
        if channel.permissions_for(guild.me).view_audit_log:
            action = discord.AuditLogAction.role_create
            async for log in guild.audit_logs(limit=5, action=action):
                if log.target.id == role.id:
                    perp = log.user
                    if log.reason:
                        reason = log.reason
                    break
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["role_create"]["embed"]
        )
        time = datetime.datetime.utcnow()
        embed = discord.Embed(
            description=role.mention,
            colour=await self.get_event_colour(guild, "role_create"),
            timestamp=time,
        )
        embed.set_author(
            name=_("Role created {role} ({r_id})").format(role=role.name, r_id=role.id)
        )
        msg = _("{emoji} `{time}` Role created {role}\n").format(
            emoji=self.settings[guild.id]["role_create"]["emoji"],
            time=time.strftime("%H:%M:%S"),
            role=role.name,
        )
        if perp:
            embed.add_field(name=_("Created by"), value=perp.mention)
            msg += _("By ") + str(perp) + "\n"
        if reason:
            msg += _("Reason ") + reason + "\n"
            embed.add_field(name=_("Reason "), value=reason)
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(escape(msg, mass_mentions=True))

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        guild = role.guild
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if not self.settings[guild.id]["role_delete"]["enabled"]:
            return
        try:
            channel = await self.modlog_channel(guild, "role_change")
        except RuntimeError:
            return
        perp = None
        reason = None
        if channel.permissions_for(guild.me).view_audit_log:
            action = discord.AuditLogAction.role_delete
            async for log in guild.audit_logs(limit=5, action=action):
                if log.target.id == role.id:
                    perp = log.user
                    if log.reason:
                        reason = log.reason
                    break
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["role_delete"]["embed"]
        )
        time = datetime.datetime.utcnow()
        embed = discord.Embed(
            description=role.name,
            timestamp=time,
            colour=await self.get_event_colour(guild, "role_delete"),
        )
        embed.set_author(
            name=_("Role deleted {role} ({r_id})").format(role=role.name, r_id=role.id)
        )
        msg = _("{emoji} `{time}` Role deleted **{role}**\n").format(
            emoji=self.settings[guild.id]["role_create"]["emoji"],
            time=time.strftime("%H:%M:%S"),
            role=role.name,
        )
        if perp:
            embed.add_field(name=_("Deleted by"), value=perp.mention)
            msg += _("By ") + str(perp) + "\n"
        if reason:
            msg += _("Reason ") + reason + "\n"
            embed.add_field(name=_("Reason "), value=reason)
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(escape(msg, mass_mentions=True))

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        guild = before.guild
        if guild is None:
            return
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        settings = self.settings[guild.id]["message_edit"]
        if not settings["enabled"]:
            return
        if before.author.bot and not settings["bots"]:
            return
        if before.content == after.content:
            return
        try:
            channel = await self.modlog_channel(guild, "message_edit")
        except RuntimeError:
            return
        if await self.is_ignored_channel(guild, after.channel):
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["message_edit"]["embed"]
        )
        time = datetime.datetime.utcnow()
        fmt = "%H:%M:%S"
        if embed_links:
            embed = discord.Embed(
                description=before.content,
                colour=await self.get_event_colour(guild, "message_edit"),
                timestamp=before.created_at,
            )
            jump_url = f"[Click to see new message]({after.jump_url})"
            embed.add_field(name=_("After Message:"), value=jump_url)
            embed.add_field(name=_("Channel:"), value=before.channel.mention)
            embed.set_footer(text=_("User ID: ") + str(before.author.id))
            embed.set_author(
                name=_("{member} ({m_id}) - Edited Message").format(
                    member=before.author, m_id=before.author.id
                ),
                icon_url=str(before.author.avatar_url),
            )
            await channel.send(embed=embed)
        else:
            msg = _(
                "{emoji} `{time}` **{author}** (`{a_id}`) edited a message "
                "in {channel}.\nBefore:\n> {before}\nAfter:\n> {after}"
            ).format(
                emoji=self.settings[guild.id]["message_edit"]["emoji"],
                time=time.strftime(fmt),
                author=before.author,
                a_id=before.author.id,
                channel=before.channel.mention,
                before=escape(before.content, mass_mentions=True),
                after=escape(after.content, mass_mentions=True),
            )
            await channel.send(msg[:2000])

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        guild = after
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if not self.settings[guild.id]["guild_change"]["enabled"]:
            return
        try:
            channel = await self.modlog_channel(guild, "guild_change")
        except RuntimeError:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["guild_change"]["embed"]
        )
        time = datetime.datetime.utcnow()
        embed = discord.Embed(
            timestamp=time, colour=await self.get_event_colour(guild, "guild_change")
        )
        embed.set_author(name=_("Updated Guild"), icon_url=str(guild.icon_url))
        embed.set_thumbnail(url=str(guild.icon_url))
        msg = _("{emoji} `{time}` Guild updated\n").format(
            emoji=self.settings[guild.id]["guild_change"]["emoji"], time=time.strftime("%H:%M:%S"),
        )
        guild_updates = {
            "name": _("Name:"),
            "region": _("Region:"),
            "afk_timeout": _("AFK Timeout:"),
            "afk_channel": _("AFK Channel:"),
            "icon_url": _("Server Icon:"),
            "owner": _("Server Owner:"),
            "splash": _("Splash Image:"),
            "system_channel": _("Welcome message channel:"),
            "verification_level": _("Verification Level:"),
        }
        worth_updating = False
        for attr, name in guild_updates.items():
            before_attr = getattr(before, attr)
            after_attr = getattr(after, attr)
            if before_attr != after_attr:
                worth_updating = True
                msg += _("Before ") + f"{name} {before_attr}\n"
                msg += _("After ") + f"{name} {after_attr}\n"
                embed.add_field(name=_("Before ") + name, value=str(before_attr))
                embed.add_field(name=_("After ") + name, value=str(after_attr))
        if not worth_updating:
            return
        perps = []
        reasons = []
        if channel.permissions_for(guild.me).view_audit_log:
            action = discord.AuditLogAction.guild_update
            async for log in guild.audit_logs(limit=int(len(embed.fields) / 2), action=action):
                perps.append(log.user)
                if log.reason:
                    reasons.append(log.reason)
        if perps:
            perp_s = ", ".join(str(p) for p in perps)
            msg += _("Update by ") + f"{perp_s}\n"
            perp_m = ", ".join(p.mention for p in perps)
            embed.add_field(name=_("Updated by"), value=perp_m)
        if reasons:
            s_reasons = ", ".join(str(r) for r in reasons)
            msg += _("Reasons ") + f"{reasons}\n"
            embed.add_field(name=_("Reasons "), value=s_reasons)
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(msg)

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self, guild: discord.Guild, before: Sequence[discord.Emoji], after: Sequence[discord.Emoji]
    ) -> None:
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if not self.settings[guild.id]["emoji_change"]["enabled"]:
            return
        try:
            channel = await self.modlog_channel(guild, "emoji_change")
        except RuntimeError:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["emoji_change"]["embed"]
        )
        perp = None

        time = datetime.datetime.utcnow()
        embed = discord.Embed(
            description="",
            timestamp=time,
            colour=await self.get_event_colour(guild, "emoji_change"),
        )
        embed.set_author(name=_("Updated Server Emojis"))
        msg = _("{emoji} `{time}` Updated Server Emojis").format(
            emoji=self.settings[guild.id]["emoji_change"]["emoji"], time=time.strftime("%H:%M:%S")
        )
        worth_updating = False
        b = set(before)
        a = set(after)
        # discord.Emoji uses id for hashing so we use set difference to get added/removed emoji
        try:
            added_emoji = (a - b).pop()
        except KeyError:
            added_emoji = None
        try:
            removed_emoji = (b - a).pop()
        except KeyError:
            removed_emoji = None
        # changed emojis have their name and/or allowed roles changed while keeping id unchanged
        if added_emoji is not None:
            to_iter = before + (added_emoji,)
        else:
            to_iter = before
        changed_emoji = set((e, e.name, tuple(e.roles)) for e in after)
        changed_emoji.difference_update((e, e.name, tuple(e.roles)) for e in to_iter)
        try:
            changed_emoji = changed_emoji.pop()[0]
        except KeyError:
            changed_emoji = None
        else:
            for old_emoji in before:
                if old_emoji.id == changed_emoji.id:
                    break
            else:
                # this shouldn't happen but it's here just in case
                changed_emoji = None
        action = None
        if removed_emoji is not None:
            worth_updating = True
            new_msg = f"`{removed_emoji}` (ID: {removed_emoji.id})" + _(
                " Removed from the guild\n"
            )
            msg += new_msg
            embed.description += new_msg
            action = discord.AuditLogAction.emoji_delete
        elif added_emoji is not None:
            worth_updating = True
            new_msg = f"{added_emoji} `{added_emoji}`" + _(" Added to the guild\n")
            msg += new_msg
            embed.description += new_msg
            action = discord.AuditLogAction.emoji_create
        elif changed_emoji is not None:
            worth_updating = True
            new_msg = f"{changed_emoji} `{changed_emoji}`"
            if old_emoji.name != changed_emoji.name:
                new_msg += (
                    _(" Renamed from ") + old_emoji.name + _(" to ") + f"{changed_emoji.name}\n"
                )
                # emoji_update shows only for renames and not for role restriction updates
                action = discord.AuditLogAction.emoji_update
            msg += new_msg
            embed.description += new_msg
            if old_emoji.roles != changed_emoji.roles:
                worth_updating = True
                if not changed_emoji.roles:
                    new_msg = _(" Changed to unrestricted.\n")
                    msg += new_msg
                    embed.description += new_msg
                elif not old_emoji.roles:
                    msg += (
                        _(" Restricted to roles: ")
                        + humanize_list(
                            [f"{role.name} ({role.id})" for role in changed_emoji.roles]
                        )
                        + "\n"
                    )
                    embed.description += _(" Restricted to roles: ") + humanize_list(
                        [role.mention for role in changed_emoji.roles]
                    )
                else:
                    msg += (
                        _(" Role restriction changed from ")
                        + humanize_list([f"{role.name} ({role.id})" for role in old_emoji.roles])
                        + _(" to ")
                        + humanize_list(
                            [f"{role.name} ({role.id})" for role in changed_emoji.roles]
                        )
                        + "\n"
                    )
                    embed.description += (
                        _(" Role restriction changed from ")
                        + humanize_list([role.mention for role in old_emoji.roles])
                        + _(" to ")
                        + humanize_list([role.mention for role in changed_emoji.roles])
                    )
        perp = None
        reason = None
        if not worth_updating:
            return
        if channel.permissions_for(guild.me).view_audit_log:
            if action:
                async for log in guild.audit_logs(limit=1, action=action):
                    perp = log.user
                    if log.reason:
                        reason = log.reason
                    break
        if perp:
            embed.add_field(name=_("Updated by "), value=perp.mention)
            msg += _("Updated by ") + str(perp) + "\n"
        if reason:
            msg += _("Reason ") + reason + "\n"
            embed.add_field(name=_("Reason "), value=reason)
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(msg)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        guild = member.guild
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if not self.settings[guild.id]["voice_change"]["enabled"]:
            return
        if member.bot:
            return
        try:
            channel = await self.modlog_channel(guild, "voice_change")
        except RuntimeError:
            return
        if after.channel is not None:
            if await self.is_ignored_channel(guild, after.channel):
                return
        if before.channel is not None:
            if await self.is_ignored_channel(guild, before.channel):
                return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["voice_change"]["embed"]
        )
        time = datetime.datetime.utcnow()
        embed = discord.Embed(
            timestamp=time, colour=await self.get_event_colour(guild, "voice_change"),
        )
        msg = _("{emoji} `{time}` Updated Voice State for **{member}** (`{m_id}`)").format(
            emoji=self.settings[guild.id]["voice_change"]["emoji"],
            time=time.strftime("%H:%M:%S"),
            member=member,
            m_id=member.id,
        )
        embed.set_author(
            name=_("{member} ({m_id}) Voice State Update").format(member=member, m_id=member.id)
        )
        change_type = None
        worth_updating = False
        if before.deaf != after.deaf:
            worth_updating = True
            change_type = "deaf"
            if after.deaf:
                chan_msg = member.mention + _(" was deafened. ")
                msg += chan_msg + "\n"
                embed.description = chan_msg
            else:
                chan_msg = member.mention + _(" was undeafened. ")
                msg += chan_msg + "\n"
                embed.description = chan_msg
        if before.mute != after.mute:
            worth_updating = True
            change_type = "mute"
            if after.mute:
                chan_msg = member.mention + _(" was muted. ")
                msg += chan_msg + "\n"
                embed.description = chan_msg
            else:
                chan_msg = member.mention + _(" was unmuted. ")
                msg += chan_msg + "\n"
                embed.description = chan_msg
        if before.channel != after.channel:
            worth_updating = True
            change_type = "channel"
            if before.channel is None:
                chan_msg = member.mention + _(" has joined ") + inline(after.channel.name)
                msg += chan_msg + "\n"
                embed.description = chan_msg
            elif after.channel is None:
                chan_msg = member.mention + _(" has left ") + inline(before.channel.name)
                msg += chan_msg + "\n"
                embed.description = chan_msg
            else:
                chan_msg = (
                    member.mention
                    + _(" has moved from ")
                    + inline(before.channel.name)
                    + _(" to ")
                    + inline(after.channel.name)
                )
                msg += chan_msg
                embed.description = chan_msg
        if not worth_updating:
            return
        perp = None
        reason = None
        if channel.permissions_for(guild.me).view_audit_log and change_type:
            action = discord.AuditLogAction.member_update
            async for log in guild.audit_logs(limit=5, action=action):
                is_change = getattr(log.after, change_type, None)
                if log.target.id == member.id and is_change:
                    perp = log.user
                    if log.reason:
                        reason = log.reason
                    break
        if perp:
            embed.add_field(name=_("Updated by"), value=perp.mention)
        if reason:
            msg += _("Reason ") + reason + "\n"
            embed.add_field(name=_("Reason "), value=reason)
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(escape(msg, mass_mentions=True))

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        guild = before.guild
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if not self.settings[guild.id]["user_change"]["enabled"]:
            return
        if not self.settings[guild.id]["user_change"]["bots"] and after.bot:
            return
        try:
            channel = await self.modlog_channel(guild, "user_change")
        except RuntimeError:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["user_change"]["embed"]
        )
        time = datetime.datetime.utcnow()
        embed = discord.Embed(
            timestamp=time, colour=await self.get_event_colour(guild, "user_change")
        )
        msg = _("{emoji} `{time}` Member updated **{member}** (`{m_id}`)\n").format(
            emoji=self.settings[guild.id]["user_change"]["emoji"],
            time=time.strftime("%H:%M:%S"),
            member=before,
            m_id=before.id,
        )
        emb_msg = _("{member} ({m_id}) updated").format(member=before, m_id=before.id)
        embed.set_author(name=emb_msg, icon_url=before.avatar_url)
        member_updates = {"nick": _("Nickname:"), "roles": _("Roles:")}
        perp = None
        reason = None
        worth_sending = False
        for attr, name in member_updates.items():
            if attr == "nick" and not self.settings[guild.id]["user_change"]["nicknames"]:
                continue
            before_attr = getattr(before, attr)
            after_attr = getattr(after, attr)
            if before_attr != after_attr:
                if attr == "roles":
                    b = set(before.roles)
                    a = set(after.roles)
                    before_roles = list(b - a)
                    after_roles = list(a - b)
                    if before_roles:
                        for role in before_roles:
                            msg += role.name + _(" Role Removed.")
                            embed.description = role.mention + _(" Role removed.")
                            worth_sending = True
                    if after_roles:
                        for role in after_roles:
                            msg += role.name + _(" Role Applied.")
                            embed.description = role.mention + _(" Role applied.")
                            worth_sending = True
                    if channel.permissions_for(guild.me).view_audit_log:
                        action = discord.AuditLogAction.member_role_update
                        async for log in guild.audit_logs(limit=5, action=action):
                            if log.target.id == before.id:
                                perp = log.user
                                if log.reason:
                                    reason = log.reason
                                break
                else:
                    if channel.permissions_for(guild.me).view_audit_log:
                        action = discord.AuditLogAction.member_update
                        async for log in guild.audit_logs(limit=5, action=action):
                            if log.target.id == before.id:
                                perp = log.user
                                if log.reason:
                                    reason = log.reason
                                break
                    worth_sending = True
                    msg += _("Before ") + f"{name} {before_attr}\n"
                    msg += _("After ") + f"{name} {after_attr}\n"
                    embed.add_field(name=_("Before ") + name, value=str(before_attr)[:1024])
                    embed.add_field(name=_("After ") + name, value=str(after_attr)[:1024])
        if not worth_sending:
            return
        if perp:
            msg += _("Updated by ") + f"{perp}\n"
            embed.add_field(name=_("Updated by "), value=perp.mention)
        if reason:
            msg += _("Reason: ") + f"{reason}\n"
            embed.add_field(name=_("Reason"), value=reason)
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(msg)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        """
            New in discord.py 1.3
        """
        guild = invite.guild
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if invite.code not in self.settings[guild.id]["invite_links"]:
            created_at = getattr(invite, "created_at", datetime.datetime.utcnow())
            inviter = getattr(invite, "inviter", discord.Object(id=0))
            channel = getattr(invite, "channel", discord.Object(id=0))
            self.settings[guild.id]["invite_links"][invite.code] = {
                "uses": getattr(invite, "uses", 0),
                "max_age": getattr(invite, "max_age", None),
                "created_at": created_at.timestamp(),
                "max_uses": getattr(invite, "max_uses", None),
                "temporary": getattr(invite, "temporary", False),
                "inviter": inviter.id,
                "channel": channel.id,
            }
            await self.config.guild(guild).invite_links.set(
                self.settings[guild.id]["invite_links"]
            )
        if not self.settings[guild.id]["invite_created"]["enabled"]:
            return
        try:
            channel = await self.modlog_channel(guild, "invite_created")
        except RuntimeError:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["invite_created"]["embed"]
        )
        invite_attrs = {
            "code": _("Code:"),
            "inviter": _("Inviter:"),
            "channel": _("Channel:"),
            "max_uses": _("Max Uses:"),
        }
        try:
            invite_time = invite.created_at.strftime("%H:%M:%S")
        except AttributeError:
            invite_time = datetime.datetime.utcnow().strftime("%H:%M:%S")
        msg = _("{emoji} `{time}` Invite created ").format(
            emoji=self.settings[guild.id]["invite_created"]["emoji"], time=invite_time,
        )
        embed = discord.Embed(
            title=_("Invite Created"), colour=await self.get_event_colour(guild, "invite_created")
        )
        worth_updating = False
        for attr, name in invite_attrs.items():
            before_attr = getattr(invite, attr)
            if before_attr:
                worth_updating = True
                msg += f"{name} {before_attr}\n"
                embed.add_field(name=name, value=str(before_attr))
        if not worth_updating:
            return
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(escape(msg, mass_mentions=True))

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite) -> None:
        """
            New in discord.py 1.3
        """
        guild = invite.guild
        if guild.id not in self.settings:
            return
        if version_info >= VersionInfo.from_str("3.4.0"):
            if await self.bot.cog_disabled_in_guild(self, guild):
                return
        if not self.settings[guild.id]["invite_deleted"]["enabled"]:
            return
        try:
            channel = await self.modlog_channel(guild, "invite_deleted")
        except RuntimeError:
            return
        embed_links = (
            channel.permissions_for(guild.me).embed_links
            and self.settings[guild.id]["invite_deleted"]["embed"]
        )
        invite_attrs = {
            "code": _("Code: "),
            "inviter": _("Inviter: "),
            "channel": _("Channel: "),
            "max_uses": _("Max Uses: "),
            "uses": _("Used: "),
        }
        try:
            invite_time = invite.created_at.strftime("%H:%M:%S")
        except AttributeError:
            invite_time = datetime.datetime.utcnow().strftime("%H:%M:%S")
        msg = _("{emoji} `{time}` Invite deleted ").format(
            emoji=self.settings[guild.id]["invite_deleted"]["emoji"], time=invite_time,
        )
        embed = discord.Embed(
            title=_("Invite Deleted"), colour=await self.get_event_colour(guild, "invite_deleted")
        )
        worth_updating = False
        for attr, name in invite_attrs.items():
            before_attr = getattr(invite, attr)
            if before_attr:
                worth_updating = True
                msg += f"{name} {before_attr}\n"
                embed.add_field(name=name, value=str(before_attr))
        if not worth_updating:
            return
        if embed_links:
            await channel.send(embed=embed)
        else:
            await channel.send(escape(msg, mass_mentions=True))-s>&quot;channel&quot;</span>: <span class=pl-s1>channel</span>.<span class=pl-s1>id</span>,</td>
      </tr>
      <tr>
        <td id="L481" class="blob-num js-line-number" data-line-number="481"></td>
        <td id="LC481" class="blob-code blob-code-inner js-file-line">                }</td>
      </tr>
      <tr>
        <td id="L482" class="blob-num js-line-number" data-line-number="482"></td>
        <td id="LC482" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>except</span> <span class=pl-v>Exception</span>:</td>
      </tr>
      <tr>
        <td id="L483" class="blob-num js-line-number" data-line-number="483"></td>
        <td id="LC483" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>logger</span>.<span class=pl-en>exception</span>(<span class=pl-s>&quot;Error saving invites.&quot;</span>)</td>
      </tr>
      <tr>
        <td id="L484" class="blob-num js-line-number" data-line-number="484"></td>
        <td id="LC484" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>pass</span></td>
      </tr>
      <tr>
        <td id="L485" class="blob-num js-line-number" data-line-number="485"></td>
        <td id="LC485" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>config</span>.<span class=pl-en>guild</span>(<span class=pl-s1>guild</span>).<span class=pl-s1>invite_links</span>.<span class=pl-en>set</span>(<span class=pl-s1>invites</span>)</td>
      </tr>
      <tr>
        <td id="L486" class="blob-num js-line-number" data-line-number="486"></td>
        <td id="LC486" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>return</span> <span class=pl-c1>True</span></td>
      </tr>
      <tr>
        <td id="L487" class="blob-num js-line-number" data-line-number="487"></td>
        <td id="LC487" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L488" class="blob-num js-line-number" data-line-number="488"></td>
        <td id="LC488" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>async</span> <span class=pl-k>def</span> <span class=pl-en>get_invite_link</span>(<span class=pl-s1>self</span>, <span class=pl-s1>guild</span>: <span class=pl-s1>discord</span>.<span class=pl-v>Guild</span>) <span class=pl-c1>-&gt;</span> <span class=pl-s1>str</span>:</td>
      </tr>
      <tr>
        <td id="L489" class="blob-num js-line-number" data-line-number="489"></td>
        <td id="LC489" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>manage_guild</span> <span class=pl-c1>=</span> <span class=pl-s1>guild</span>.<span class=pl-s1>me</span>.<span class=pl-s1>guild_permissions</span>.<span class=pl-s1>manage_guild</span></td>
      </tr>
      <tr>
        <td id="L490" class="blob-num js-line-number" data-line-number="490"></td>
        <td id="LC490" class="blob-code blob-code-inner js-file-line">        <span class=pl-c># invites = await self.config.guild(guild).invite_links()</span></td>
      </tr>
      <tr>
        <td id="L491" class="blob-num js-line-number" data-line-number="491"></td>
        <td id="LC491" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>invites</span> <span class=pl-c1>=</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;invite_links&quot;</span>]</td>
      </tr>
      <tr>
        <td id="L492" class="blob-num js-line-number" data-line-number="492"></td>
        <td id="LC492" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>possible_link</span> <span class=pl-c1>=</span> <span class=pl-s>&quot;&quot;</span></td>
      </tr>
      <tr>
        <td id="L493" class="blob-num js-line-number" data-line-number="493"></td>
        <td id="LC493" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>check_logs</span> <span class=pl-c1>=</span> <span class=pl-s1>manage_guild</span> <span class=pl-c1>and</span> <span class=pl-s1>guild</span>.<span class=pl-s1>me</span>.<span class=pl-s1>guild_permissions</span>.<span class=pl-s1>view_audit_log</span></td>
      </tr>
      <tr>
        <td id="L494" class="blob-num js-line-number" data-line-number="494"></td>
        <td id="LC494" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>manage_guild</span> <span class=pl-c1>and</span> <span class=pl-s>&quot;VANITY_URL&quot;</span> <span class=pl-c1>in</span> <span class=pl-s1>guild</span>.<span class=pl-s1>features</span>:</td>
      </tr>
      <tr>
        <td id="L495" class="blob-num js-line-number" data-line-number="495"></td>
        <td id="LC495" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>possible_link</span> <span class=pl-c1>=</span> <span class=pl-en>str</span>(<span class=pl-k>await</span> <span class=pl-s1>guild</span>.<span class=pl-en>vanity_invite</span>())</td>
      </tr>
      <tr>
        <td id="L496" class="blob-num js-line-number" data-line-number="496"></td>
        <td id="LC496" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>invites</span> <span class=pl-c1>and</span> <span class=pl-s1>manage_guild</span>:</td>
      </tr>
      <tr>
        <td id="L497" class="blob-num js-line-number" data-line-number="497"></td>
        <td id="LC497" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>guild_invites</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>guild</span>.<span class=pl-en>invites</span>()</td>
      </tr>
      <tr>
        <td id="L498" class="blob-num js-line-number" data-line-number="498"></td>
        <td id="LC498" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>for</span> <span class=pl-s1>invite</span> <span class=pl-c1>in</span> <span class=pl-s1>guild_invites</span>:</td>
      </tr>
      <tr>
        <td id="L499" class="blob-num js-line-number" data-line-number="499"></td>
        <td id="LC499" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>invite</span>.<span class=pl-s1>code</span> <span class=pl-c1>in</span> <span class=pl-s1>invites</span>:</td>
      </tr>
      <tr>
        <td id="L500" class="blob-num js-line-number" data-line-number="500"></td>
        <td id="LC500" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>uses</span> <span class=pl-c1>=</span> <span class=pl-s1>invites</span>[<span class=pl-s1>invite</span>.<span class=pl-s1>code</span>][<span class=pl-s>&quot;uses&quot;</span>]</td>
      </tr>
      <tr>
        <td id="L501" class="blob-num js-line-number" data-line-number="501"></td>
        <td id="LC501" class="blob-code blob-code-inner js-file-line">                    <span class=pl-c># logger.info(f&quot;{invite.code}: {invite.uses} - {uses}&quot;)</span></td>
      </tr>
      <tr>
        <td id="L502" class="blob-num js-line-number" data-line-number="502"></td>
        <td id="LC502" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>if</span> <span class=pl-s1>invite</span>.<span class=pl-s1>uses</span> <span class=pl-c1>&gt;</span> <span class=pl-s1>uses</span>:</td>
      </tr>
      <tr>
        <td id="L503" class="blob-num js-line-number" data-line-number="503"></td>
        <td id="LC503" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>possible_link</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(</td>
      </tr>
      <tr>
        <td id="L504" class="blob-num js-line-number" data-line-number="504"></td>
        <td id="LC504" class="blob-code blob-code-inner js-file-line">                            <span class=pl-s>&quot;https://discord.gg/{code}<span class=pl-cce>\n</span>Invited by: {inviter}&quot;</span></td>
      </tr>
      <tr>
        <td id="L505" class="blob-num js-line-number" data-line-number="505"></td>
        <td id="LC505" class="blob-code blob-code-inner js-file-line">                        ).<span class=pl-en>format</span>(<span class=pl-s1>code</span><span class=pl-c1>=</span><span class=pl-s1>invite</span>.<span class=pl-s1>code</span>, <span class=pl-s1>inviter</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>invite</span>.<span class=pl-s1>inviter</span>))</td>
      </tr>
      <tr>
        <td id="L506" class="blob-num js-line-number" data-line-number="506"></td>
        <td id="LC506" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L507" class="blob-num js-line-number" data-line-number="507"></td>
        <td id="LC507" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>possible_link</span>:</td>
      </tr>
      <tr>
        <td id="L508" class="blob-num js-line-number" data-line-number="508"></td>
        <td id="LC508" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>for</span> <span class=pl-s1>code</span>, <span class=pl-s1>data</span> <span class=pl-c1>in</span> <span class=pl-s1>invites</span>.<span class=pl-en>items</span>():</td>
      </tr>
      <tr>
        <td id="L509" class="blob-num js-line-number" data-line-number="509"></td>
        <td id="LC509" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>try</span>:</td>
      </tr>
      <tr>
        <td id="L510" class="blob-num js-line-number" data-line-number="510"></td>
        <td id="LC510" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>invite</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>bot</span>.<span class=pl-en>fetch_invite</span>(<span class=pl-s1>code</span>)</td>
      </tr>
      <tr>
        <td id="L511" class="blob-num js-line-number" data-line-number="511"></td>
        <td id="LC511" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>except</span> (</td>
      </tr>
      <tr>
        <td id="L512" class="blob-num js-line-number" data-line-number="512"></td>
        <td id="LC512" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>discord</span>.<span class=pl-s1>errors</span>.<span class=pl-v>NotFound</span>,</td>
      </tr>
      <tr>
        <td id="L513" class="blob-num js-line-number" data-line-number="513"></td>
        <td id="LC513" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>discord</span>.<span class=pl-s1>errors</span>.<span class=pl-v>HTTPException</span>,</td>
      </tr>
      <tr>
        <td id="L514" class="blob-num js-line-number" data-line-number="514"></td>
        <td id="LC514" class="blob-code blob-code-inner js-file-line">                        <span class=pl-v>Exception</span>,</td>
      </tr>
      <tr>
        <td id="L515" class="blob-num js-line-number" data-line-number="515"></td>
        <td id="LC515" class="blob-code blob-code-inner js-file-line">                    ):</td>
      </tr>
      <tr>
        <td id="L516" class="blob-num js-line-number" data-line-number="516"></td>
        <td id="LC516" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>logger</span>.<span class=pl-en>error</span>(<span class=pl-s>&quot;Error getting invite {code}&quot;</span>.<span class=pl-en>format</span>(<span class=pl-s1>code</span><span class=pl-c1>=</span><span class=pl-s1>code</span>))</td>
      </tr>
      <tr>
        <td id="L517" class="blob-num js-line-number" data-line-number="517"></td>
        <td id="LC517" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>invite</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L518" class="blob-num js-line-number" data-line-number="518"></td>
        <td id="LC518" class="blob-code blob-code-inner js-file-line">                        <span class=pl-k>pass</span></td>
      </tr>
      <tr>
        <td id="L519" class="blob-num js-line-number" data-line-number="519"></td>
        <td id="LC519" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>invite</span>:</td>
      </tr>
      <tr>
        <td id="L520" class="blob-num js-line-number" data-line-number="520"></td>
        <td id="LC520" class="blob-code blob-code-inner js-file-line">                        <span class=pl-k>if</span> (<span class=pl-s1>data</span>[<span class=pl-s>&quot;max_uses&quot;</span>] <span class=pl-c1>-</span> <span class=pl-s1>data</span>[<span class=pl-s>&quot;uses&quot;</span>]) <span class=pl-c1>==</span> <span class=pl-c1>1</span>:</td>
      </tr>
      <tr>
        <td id="L521" class="blob-num js-line-number" data-line-number="521"></td>
        <td id="LC521" class="blob-code blob-code-inner js-file-line">                            <span class=pl-c># The invite link was on its last uses and subsequently</span></td>
      </tr>
      <tr>
        <td id="L522" class="blob-num js-line-number" data-line-number="522"></td>
        <td id="LC522" class="blob-code blob-code-inner js-file-line">                            <span class=pl-c># deleted so we&#39;re fairly sure this was the one used</span></td>
      </tr>
      <tr>
        <td id="L523" class="blob-num js-line-number" data-line-number="523"></td>
        <td id="LC523" class="blob-code blob-code-inner js-file-line">                            <span class=pl-k>try</span>:</td>
      </tr>
      <tr>
        <td id="L524" class="blob-num js-line-number" data-line-number="524"></td>
        <td id="LC524" class="blob-code blob-code-inner js-file-line">                                <span class=pl-s1>inviter</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>bot</span>.<span class=pl-en>fetch_user</span>(<span class=pl-s1>data</span>[<span class=pl-s>&quot;inviter&quot;</span>])</td>
      </tr>
      <tr>
        <td id="L525" class="blob-num js-line-number" data-line-number="525"></td>
        <td id="LC525" class="blob-code blob-code-inner js-file-line">                            <span class=pl-k>except</span> (<span class=pl-s1>discord</span>.<span class=pl-s1>errors</span>.<span class=pl-v>NotFound</span>, <span class=pl-s1>discord</span>.<span class=pl-s1>errors</span>.<span class=pl-v>Forbidden</span>):</td>
      </tr>
      <tr>
        <td id="L526" class="blob-num js-line-number" data-line-number="526"></td>
        <td id="LC526" class="blob-code blob-code-inner js-file-line">                                <span class=pl-s1>inviter</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Unknown or deleted user ({inviter})&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L527" class="blob-num js-line-number" data-line-number="527"></td>
        <td id="LC527" class="blob-code blob-code-inner js-file-line">                                    <span class=pl-s1>inviter</span><span class=pl-c1>=</span><span class=pl-s1>data</span>[<span class=pl-s>&quot;inviter&quot;</span>]</td>
      </tr>
      <tr>
        <td id="L528" class="blob-num js-line-number" data-line-number="528"></td>
        <td id="LC528" class="blob-code blob-code-inner js-file-line">                                )</td>
      </tr>
      <tr>
        <td id="L529" class="blob-num js-line-number" data-line-number="529"></td>
        <td id="LC529" class="blob-code blob-code-inner js-file-line">                            <span class=pl-s1>possible_link</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(</td>
      </tr>
      <tr>
        <td id="L530" class="blob-num js-line-number" data-line-number="530"></td>
        <td id="LC530" class="blob-code blob-code-inner js-file-line">                                <span class=pl-s>&quot;https://discord.gg/{code}<span class=pl-cce>\n</span>Invited by: {inviter}&quot;</span></td>
      </tr>
      <tr>
        <td id="L531" class="blob-num js-line-number" data-line-number="531"></td>
        <td id="LC531" class="blob-code blob-code-inner js-file-line">                            ).<span class=pl-en>format</span>(<span class=pl-s1>code</span><span class=pl-c1>=</span><span class=pl-s1>code</span>, <span class=pl-s1>inviter</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>inviter</span>))</td>
      </tr>
      <tr>
        <td id="L532" class="blob-num js-line-number" data-line-number="532"></td>
        <td id="LC532" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>save_invite_links</span>(<span class=pl-s1>guild</span>)  <span class=pl-c># Save all the invites again since they&#39;ve changed</span></td>
      </tr>
      <tr>
        <td id="L533" class="blob-num js-line-number" data-line-number="533"></td>
        <td id="LC533" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>check_logs</span> <span class=pl-c1>and</span> <span class=pl-c1>not</span> <span class=pl-s1>possible_link</span>:</td>
      </tr>
      <tr>
        <td id="L534" class="blob-num js-line-number" data-line-number="534"></td>
        <td id="LC534" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>action</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>AuditLogAction</span>.<span class=pl-s1>invite_create</span></td>
      </tr>
      <tr>
        <td id="L535" class="blob-num js-line-number" data-line-number="535"></td>
        <td id="LC535" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>async</span> <span class=pl-k>for</span> <span class=pl-s1>log</span> <span class=pl-c1>in</span> <span class=pl-s1>guild</span>.<span class=pl-en>audit_logs</span>(<span class=pl-s1>action</span><span class=pl-c1>=</span><span class=pl-s1>action</span>):</td>
      </tr>
      <tr>
        <td id="L536" class="blob-num js-line-number" data-line-number="536"></td>
        <td id="LC536" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>target</span>.<span class=pl-s1>code</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>invites</span>:</td>
      </tr>
      <tr>
        <td id="L537" class="blob-num js-line-number" data-line-number="537"></td>
        <td id="LC537" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>possible_link</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;https://discord.gg/{code}<span class=pl-cce>\n</span>Invited by: {inviter}&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L538" class="blob-num js-line-number" data-line-number="538"></td>
        <td id="LC538" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>code</span><span class=pl-c1>=</span><span class=pl-s1>log</span>.<span class=pl-s1>target</span>.<span class=pl-s1>code</span>, <span class=pl-s1>inviter</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>log</span>.<span class=pl-s1>target</span>.<span class=pl-s1>inviter</span>)</td>
      </tr>
      <tr>
        <td id="L539" class="blob-num js-line-number" data-line-number="539"></td>
        <td id="LC539" class="blob-code blob-code-inner js-file-line">                    )</td>
      </tr>
      <tr>
        <td id="L540" class="blob-num js-line-number" data-line-number="540"></td>
        <td id="LC540" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>break</span></td>
      </tr>
      <tr>
        <td id="L541" class="blob-num js-line-number" data-line-number="541"></td>
        <td id="LC541" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>return</span> <span class=pl-s1>possible_link</span></td>
      </tr>
      <tr>
        <td id="L542" class="blob-num js-line-number" data-line-number="542"></td>
        <td id="LC542" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L543" class="blob-num js-line-number" data-line-number="543"></td>
        <td id="LC543" class="blob-code blob-code-inner js-file-line">    <span class=pl-en>@<span class=pl-s1>commands</span>.<span class=pl-v>Cog</span>.<span class=pl-s1>listener</span>()</span></td>
      </tr>
      <tr>
        <td id="L544" class="blob-num js-line-number" data-line-number="544"></td>
        <td id="LC544" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>async</span> <span class=pl-k>def</span> <span class=pl-en>on_member_join</span>(<span class=pl-s1>self</span>, <span class=pl-s1>member</span>: <span class=pl-s1>discord</span>.<span class=pl-v>Member</span>):</td>
      </tr>
      <tr>
        <td id="L545" class="blob-num js-line-number" data-line-number="545"></td>
        <td id="LC545" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>guild</span> <span class=pl-c1>=</span> <span class=pl-s1>member</span>.<span class=pl-s1>guild</span></td>
      </tr>
      <tr>
        <td id="L546" class="blob-num js-line-number" data-line-number="546"></td>
        <td id="LC546" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>guild</span>.<span class=pl-s1>id</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>:</td>
      </tr>
      <tr>
        <td id="L547" class="blob-num js-line-number" data-line-number="547"></td>
        <td id="LC547" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L548" class="blob-num js-line-number" data-line-number="548"></td>
        <td id="LC548" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;user_join&quot;</span>][<span class=pl-s>&quot;enabled&quot;</span>]:</td>
      </tr>
      <tr>
        <td id="L549" class="blob-num js-line-number" data-line-number="549"></td>
        <td id="LC549" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L550" class="blob-num js-line-number" data-line-number="550"></td>
        <td id="LC550" class="blob-code blob-code-inner js-file-line">        <span class=pl-c># if not await self.config.guild(guild).user_join.enabled():</span></td>
      </tr>
      <tr>
        <td id="L551" class="blob-num js-line-number" data-line-number="551"></td>
        <td id="LC551" class="blob-code blob-code-inner js-file-line">        <span class=pl-c># return</span></td>
      </tr>
      <tr>
        <td id="L552" class="blob-num js-line-number" data-line-number="552"></td>
        <td id="LC552" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>version_info</span> <span class=pl-c1>&gt;=</span> <span class=pl-v>VersionInfo</span>.<span class=pl-en>from_str</span>(<span class=pl-s>&quot;3.4.0&quot;</span>):</td>
      </tr>
      <tr>
        <td id="L553" class="blob-num js-line-number" data-line-number="553"></td>
        <td id="LC553" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>bot</span>.<span class=pl-en>cog_disabled_in_guild</span>(<span class=pl-s1>self</span>, <span class=pl-s1>guild</span>):</td>
      </tr>
      <tr>
        <td id="L554" class="blob-num js-line-number" data-line-number="554"></td>
        <td id="LC554" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L555" class="blob-num js-line-number" data-line-number="555"></td>
        <td id="LC555" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>try</span>:</td>
      </tr>
      <tr>
        <td id="L556" class="blob-num js-line-number" data-line-number="556"></td>
        <td id="LC556" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>modlog_channel</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;user_join&quot;</span>)</td>
      </tr>
      <tr>
        <td id="L557" class="blob-num js-line-number" data-line-number="557"></td>
        <td id="LC557" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>except</span> <span class=pl-v>RuntimeError</span>:</td>
      </tr>
      <tr>
        <td id="L558" class="blob-num js-line-number" data-line-number="558"></td>
        <td id="LC558" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L559" class="blob-num js-line-number" data-line-number="559"></td>
        <td id="LC559" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed_links</span> <span class=pl-c1>=</span> (</td>
      </tr>
      <tr>
        <td id="L560" class="blob-num js-line-number" data-line-number="560"></td>
        <td id="LC560" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>embed_links</span></td>
      </tr>
      <tr>
        <td id="L561" class="blob-num js-line-number" data-line-number="561"></td>
        <td id="LC561" class="blob-code blob-code-inner js-file-line">            <span class=pl-c1>and</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;user_join&quot;</span>][<span class=pl-s>&quot;embed&quot;</span>]</td>
      </tr>
      <tr>
        <td id="L562" class="blob-num js-line-number" data-line-number="562"></td>
        <td id="LC562" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L563" class="blob-num js-line-number" data-line-number="563"></td>
        <td id="LC563" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>time</span> <span class=pl-c1>=</span> <span class=pl-s1>datetime</span>.<span class=pl-s1>datetime</span>.<span class=pl-en>utcnow</span>()</td>
      </tr>
      <tr>
        <td id="L564" class="blob-num js-line-number" data-line-number="564"></td>
        <td id="LC564" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>users</span> <span class=pl-c1>=</span> <span class=pl-en>len</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>members</span>)</td>
      </tr>
      <tr>
        <td id="L565" class="blob-num js-line-number" data-line-number="565"></td>
        <td id="LC565" class="blob-code blob-code-inner js-file-line">        <span class=pl-c># https://github.com/Cog-Creators/Red-DiscordBot/blob/develop/cogs/general.py</span></td>
      </tr>
      <tr>
        <td id="L566" class="blob-num js-line-number" data-line-number="566"></td>
        <td id="LC566" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>since_created</span> <span class=pl-c1>=</span> (<span class=pl-s1>time</span> <span class=pl-c1>-</span> <span class=pl-s1>member</span>.<span class=pl-s1>created_at</span>).<span class=pl-s1>days</span></td>
      </tr>
      <tr>
        <td id="L567" class="blob-num js-line-number" data-line-number="567"></td>
        <td id="LC567" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>user_created</span> <span class=pl-c1>=</span> <span class=pl-s1>member</span>.<span class=pl-s1>created_at</span>.<span class=pl-en>strftime</span>(<span class=pl-s>&quot;%d %b %Y %H:%M&quot;</span>)</td>
      </tr>
      <tr>
        <td id="L568" class="blob-num js-line-number" data-line-number="568"></td>
        <td id="LC568" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L569" class="blob-num js-line-number" data-line-number="569"></td>
        <td id="LC569" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>created_on</span> <span class=pl-c1>=</span> <span class=pl-s>&quot;{}<span class=pl-cce>\n</span>({} days ago)&quot;</span>.<span class=pl-en>format</span>(<span class=pl-s1>user_created</span>, <span class=pl-s1>since_created</span>)</td>
      </tr>
      <tr>
        <td id="L570" class="blob-num js-line-number" data-line-number="570"></td>
        <td id="LC570" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L571" class="blob-num js-line-number" data-line-number="571"></td>
        <td id="LC571" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>possible_link</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>get_invite_link</span>(<span class=pl-s1>guild</span>)</td>
      </tr>
      <tr>
        <td id="L572" class="blob-num js-line-number" data-line-number="572"></td>
        <td id="LC572" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>embed_links</span>:</td>
      </tr>
      <tr>
        <td id="L573" class="blob-num js-line-number" data-line-number="573"></td>
        <td id="LC573" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>Embed</span>(</td>
      </tr>
      <tr>
        <td id="L574" class="blob-num js-line-number" data-line-number="574"></td>
        <td id="LC574" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>description</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>mention</span>,</td>
      </tr>
      <tr>
        <td id="L575" class="blob-num js-line-number" data-line-number="575"></td>
        <td id="LC575" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>colour</span><span class=pl-c1>=</span><span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>get_event_colour</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;user_join&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L576" class="blob-num js-line-number" data-line-number="576"></td>
        <td id="LC576" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>timestamp</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>joined_at</span> <span class=pl-k>if</span> <span class=pl-s1>member</span>.<span class=pl-s1>joined_at</span> <span class=pl-k>else</span> <span class=pl-s1>datetime</span>.<span class=pl-s1>datetime</span>.<span class=pl-en>utcnow</span>(),</td>
      </tr>
      <tr>
        <td id="L577" class="blob-num js-line-number" data-line-number="577"></td>
        <td id="LC577" class="blob-code blob-code-inner js-file-line">            )</td>
      </tr>
      <tr>
        <td id="L578" class="blob-num js-line-number" data-line-number="578"></td>
        <td id="LC578" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Total Users:&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>users</span>))</td>
      </tr>
      <tr>
        <td id="L579" class="blob-num js-line-number" data-line-number="579"></td>
        <td id="LC579" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Account created on:&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>created_on</span>)</td>
      </tr>
      <tr>
        <td id="L580" class="blob-num js-line-number" data-line-number="580"></td>
        <td id="LC580" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>set_footer</span>(<span class=pl-s1>text</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;User ID: &quot;</span>) <span class=pl-c1>+</span> <span class=pl-en>str</span>(<span class=pl-s1>member</span>.<span class=pl-s1>id</span>))</td>
      </tr>
      <tr>
        <td id="L581" class="blob-num js-line-number" data-line-number="581"></td>
        <td id="LC581" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>set_author</span>(</td>
      </tr>
      <tr>
        <td id="L582" class="blob-num js-line-number" data-line-number="582"></td>
        <td id="LC582" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;{member} ({m_id}) has joined the guild&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L583" class="blob-num js-line-number" data-line-number="583"></td>
        <td id="LC583" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>member</span><span class=pl-c1>=</span><span class=pl-s1>member</span>, <span class=pl-s1>m_id</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>id</span></td>
      </tr>
      <tr>
        <td id="L584" class="blob-num js-line-number" data-line-number="584"></td>
        <td id="LC584" class="blob-code blob-code-inner js-file-line">                ),</td>
      </tr>
      <tr>
        <td id="L585" class="blob-num js-line-number" data-line-number="585"></td>
        <td id="LC585" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>url</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>avatar_url</span>,</td>
      </tr>
      <tr>
        <td id="L586" class="blob-num js-line-number" data-line-number="586"></td>
        <td id="LC586" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>icon_url</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>avatar_url</span>,</td>
      </tr>
      <tr>
        <td id="L587" class="blob-num js-line-number" data-line-number="587"></td>
        <td id="LC587" class="blob-code blob-code-inner js-file-line">            )</td>
      </tr>
      <tr>
        <td id="L588" class="blob-num js-line-number" data-line-number="588"></td>
        <td id="LC588" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-s1>possible_link</span>:</td>
      </tr>
      <tr>
        <td id="L589" class="blob-num js-line-number" data-line-number="589"></td>
        <td id="LC589" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Invite Link&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>possible_link</span>)</td>
      </tr>
      <tr>
        <td id="L590" class="blob-num js-line-number" data-line-number="590"></td>
        <td id="LC590" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>set_thumbnail</span>(<span class=pl-s1>url</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>avatar_url</span>)</td>
      </tr>
      <tr>
        <td id="L591" class="blob-num js-line-number" data-line-number="591"></td>
        <td id="LC591" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>embed</span><span class=pl-c1>=</span><span class=pl-s1>embed</span>)</td>
      </tr>
      <tr>
        <td id="L592" class="blob-num js-line-number" data-line-number="592"></td>
        <td id="LC592" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L593" class="blob-num js-line-number" data-line-number="593"></td>
        <td id="LC593" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>time</span> <span class=pl-c1>=</span> <span class=pl-s1>datetime</span>.<span class=pl-s1>datetime</span>.<span class=pl-en>utcnow</span>()</td>
      </tr>
      <tr>
        <td id="L594" class="blob-num js-line-number" data-line-number="594"></td>
        <td id="LC594" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>msg</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(</td>
      </tr>
      <tr>
        <td id="L595" class="blob-num js-line-number" data-line-number="595"></td>
        <td id="LC595" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;{emoji} `{time}` **{member}**(`{m_id}`) &quot;</span></td>
      </tr>
      <tr>
        <td id="L596" class="blob-num js-line-number" data-line-number="596"></td>
        <td id="LC596" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;joined the guild. Total members: {users}&quot;</span></td>
      </tr>
      <tr>
        <td id="L597" class="blob-num js-line-number" data-line-number="597"></td>
        <td id="LC597" class="blob-code blob-code-inner js-file-line">            ).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L598" class="blob-num js-line-number" data-line-number="598"></td>
        <td id="LC598" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>emoji</span><span class=pl-c1>=</span><span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;user_join&quot;</span>][<span class=pl-s>&quot;emoji&quot;</span>],</td>
      </tr>
      <tr>
        <td id="L599" class="blob-num js-line-number" data-line-number="599"></td>
        <td id="LC599" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>time</span><span class=pl-c1>=</span><span class=pl-s1>time</span>.<span class=pl-en>strftime</span>(<span class=pl-s>&quot;%H:%M:%S&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L600" class="blob-num js-line-number" data-line-number="600"></td>
        <td id="LC600" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>member</span><span class=pl-c1>=</span><span class=pl-s1>member</span>,</td>
      </tr>
      <tr>
        <td id="L601" class="blob-num js-line-number" data-line-number="601"></td>
        <td id="LC601" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>m_id</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>id</span>,</td>
      </tr>
      <tr>
        <td id="L602" class="blob-num js-line-number" data-line-number="602"></td>
        <td id="LC602" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>users</span><span class=pl-c1>=</span><span class=pl-s1>users</span>,</td>
      </tr>
      <tr>
        <td id="L603" class="blob-num js-line-number" data-line-number="603"></td>
        <td id="LC603" class="blob-code blob-code-inner js-file-line">            )</td>
      </tr>
      <tr>
        <td id="L604" class="blob-num js-line-number" data-line-number="604"></td>
        <td id="LC604" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>msg</span>)</td>
      </tr>
      <tr>
        <td id="L605" class="blob-num js-line-number" data-line-number="605"></td>
        <td id="LC605" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L606" class="blob-num js-line-number" data-line-number="606"></td>
        <td id="LC606" class="blob-code blob-code-inner js-file-line">    <span class=pl-en>@<span class=pl-s1>commands</span>.<span class=pl-v>Cog</span>.<span class=pl-s1>listener</span>()</span></td>
      </tr>
      <tr>
        <td id="L607" class="blob-num js-line-number" data-line-number="607"></td>
        <td id="LC607" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>async</span> <span class=pl-k>def</span> <span class=pl-en>on_member_remove</span>(<span class=pl-s1>self</span>, <span class=pl-s1>member</span>: <span class=pl-s1>discord</span>.<span class=pl-v>Member</span>):</td>
      </tr>
      <tr>
        <td id="L608" class="blob-num js-line-number" data-line-number="608"></td>
        <td id="LC608" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>guild</span> <span class=pl-c1>=</span> <span class=pl-s1>member</span>.<span class=pl-s1>guild</span></td>
      </tr>
      <tr>
        <td id="L609" class="blob-num js-line-number" data-line-number="609"></td>
        <td id="LC609" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>guild</span>.<span class=pl-s1>id</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>:</td>
      </tr>
      <tr>
        <td id="L610" class="blob-num js-line-number" data-line-number="610"></td>
        <td id="LC610" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L611" class="blob-num js-line-number" data-line-number="611"></td>
        <td id="LC611" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;user_left&quot;</span>][<span class=pl-s>&quot;enabled&quot;</span>]:</td>
      </tr>
      <tr>
        <td id="L612" class="blob-num js-line-number" data-line-number="612"></td>
        <td id="LC612" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L613" class="blob-num js-line-number" data-line-number="613"></td>
        <td id="LC613" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>version_info</span> <span class=pl-c1>&gt;=</span> <span class=pl-v>VersionInfo</span>.<span class=pl-en>from_str</span>(<span class=pl-s>&quot;3.4.0&quot;</span>):</td>
      </tr>
      <tr>
        <td id="L614" class="blob-num js-line-number" data-line-number="614"></td>
        <td id="LC614" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>bot</span>.<span class=pl-en>cog_disabled_in_guild</span>(<span class=pl-s1>self</span>, <span class=pl-s1>guild</span>):</td>
      </tr>
      <tr>
        <td id="L615" class="blob-num js-line-number" data-line-number="615"></td>
        <td id="LC615" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L616" class="blob-num js-line-number" data-line-number="616"></td>
        <td id="LC616" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>try</span>:</td>
      </tr>
      <tr>
        <td id="L617" class="blob-num js-line-number" data-line-number="617"></td>
        <td id="LC617" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>modlog_channel</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;user_left&quot;</span>)</td>
      </tr>
      <tr>
        <td id="L618" class="blob-num js-line-number" data-line-number="618"></td>
        <td id="LC618" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>except</span> <span class=pl-v>RuntimeError</span>:</td>
      </tr>
      <tr>
        <td id="L619" class="blob-num js-line-number" data-line-number="619"></td>
        <td id="LC619" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L620" class="blob-num js-line-number" data-line-number="620"></td>
        <td id="LC620" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed_links</span> <span class=pl-c1>=</span> (</td>
      </tr>
      <tr>
        <td id="L621" class="blob-num js-line-number" data-line-number="621"></td>
        <td id="LC621" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>embed_links</span></td>
      </tr>
      <tr>
        <td id="L622" class="blob-num js-line-number" data-line-number="622"></td>
        <td id="LC622" class="blob-code blob-code-inner js-file-line">            <span class=pl-c1>and</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;user_left&quot;</span>][<span class=pl-s>&quot;embed&quot;</span>]</td>
      </tr>
      <tr>
        <td id="L623" class="blob-num js-line-number" data-line-number="623"></td>
        <td id="LC623" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L624" class="blob-num js-line-number" data-line-number="624"></td>
        <td id="LC624" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>time</span> <span class=pl-c1>=</span> <span class=pl-s1>datetime</span>.<span class=pl-s1>datetime</span>.<span class=pl-en>utcnow</span>()</td>
      </tr>
      <tr>
        <td id="L625" class="blob-num js-line-number" data-line-number="625"></td>
        <td id="LC625" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>check_after</span> <span class=pl-c1>=</span> <span class=pl-s1>time</span> <span class=pl-c1>+</span> <span class=pl-s1>datetime</span>.<span class=pl-en>timedelta</span>(<span class=pl-s1>minutes</span><span class=pl-c1>=</span><span class=pl-c1>-</span><span class=pl-c1>30</span>)</td>
      </tr>
      <tr>
        <td id="L626" class="blob-num js-line-number" data-line-number="626"></td>
        <td id="LC626" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L627" class="blob-num js-line-number" data-line-number="627"></td>
        <td id="LC627" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L628" class="blob-num js-line-number" data-line-number="628"></td>
        <td id="LC628" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>view_audit_log</span>:</td>
      </tr>
      <tr>
        <td id="L629" class="blob-num js-line-number" data-line-number="629"></td>
        <td id="LC629" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>action</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>AuditLogAction</span>.<span class=pl-s1>kick</span></td>
      </tr>
      <tr>
        <td id="L630" class="blob-num js-line-number" data-line-number="630"></td>
        <td id="LC630" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>async</span> <span class=pl-k>for</span> <span class=pl-s1>log</span> <span class=pl-c1>in</span> <span class=pl-s1>guild</span>.<span class=pl-en>audit_logs</span>(<span class=pl-s1>limit</span><span class=pl-c1>=</span><span class=pl-c1>5</span>, <span class=pl-s1>after</span><span class=pl-c1>=</span><span class=pl-s1>check_after</span>, <span class=pl-s1>action</span><span class=pl-c1>=</span><span class=pl-s1>action</span>):</td>
      </tr>
      <tr>
        <td id="L631" class="blob-num js-line-number" data-line-number="631"></td>
        <td id="LC631" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>target</span>.<span class=pl-s1>id</span> <span class=pl-c1>==</span> <span class=pl-s1>member</span>.<span class=pl-s1>id</span>:</td>
      </tr>
      <tr>
        <td id="L632" class="blob-num js-line-number" data-line-number="632"></td>
        <td id="LC632" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>user</span></td>
      </tr>
      <tr>
        <td id="L633" class="blob-num js-line-number" data-line-number="633"></td>
        <td id="LC633" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span></td>
      </tr>
      <tr>
        <td id="L634" class="blob-num js-line-number" data-line-number="634"></td>
        <td id="LC634" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>break</span></td>
      </tr>
      <tr>
        <td id="L635" class="blob-num js-line-number" data-line-number="635"></td>
        <td id="LC635" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>embed_links</span>:</td>
      </tr>
      <tr>
        <td id="L636" class="blob-num js-line-number" data-line-number="636"></td>
        <td id="LC636" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>Embed</span>(</td>
      </tr>
      <tr>
        <td id="L637" class="blob-num js-line-number" data-line-number="637"></td>
        <td id="LC637" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>description</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>mention</span>,</td>
      </tr>
      <tr>
        <td id="L638" class="blob-num js-line-number" data-line-number="638"></td>
        <td id="LC638" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>colour</span><span class=pl-c1>=</span><span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>get_event_colour</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;user_left&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L639" class="blob-num js-line-number" data-line-number="639"></td>
        <td id="LC639" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>timestamp</span><span class=pl-c1>=</span><span class=pl-s1>time</span>,</td>
      </tr>
      <tr>
        <td id="L640" class="blob-num js-line-number" data-line-number="640"></td>
        <td id="LC640" class="blob-code blob-code-inner js-file-line">            )</td>
      </tr>
      <tr>
        <td id="L641" class="blob-num js-line-number" data-line-number="641"></td>
        <td id="LC641" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Total Users:&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-en>len</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>members</span>)))</td>
      </tr>
      <tr>
        <td id="L642" class="blob-num js-line-number" data-line-number="642"></td>
        <td id="LC642" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-s1>perp</span>:</td>
      </tr>
      <tr>
        <td id="L643" class="blob-num js-line-number" data-line-number="643"></td>
        <td id="LC643" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Kicked&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>perp</span>.<span class=pl-s1>mention</span>)</td>
      </tr>
      <tr>
        <td id="L644" class="blob-num js-line-number" data-line-number="644"></td>
        <td id="LC644" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L645" class="blob-num js-line-number" data-line-number="645"></td>
        <td id="LC645" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Reason&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>reason</span>))</td>
      </tr>
      <tr>
        <td id="L646" class="blob-num js-line-number" data-line-number="646"></td>
        <td id="LC646" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>set_footer</span>(<span class=pl-s1>text</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;User ID: &quot;</span>) <span class=pl-c1>+</span> <span class=pl-en>str</span>(<span class=pl-s1>member</span>.<span class=pl-s1>id</span>))</td>
      </tr>
      <tr>
        <td id="L647" class="blob-num js-line-number" data-line-number="647"></td>
        <td id="LC647" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>set_author</span>(</td>
      </tr>
      <tr>
        <td id="L648" class="blob-num js-line-number" data-line-number="648"></td>
        <td id="LC648" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;{member} ({m_id}) has left the guild&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L649" class="blob-num js-line-number" data-line-number="649"></td>
        <td id="LC649" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>member</span><span class=pl-c1>=</span><span class=pl-s1>member</span>, <span class=pl-s1>m_id</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>id</span></td>
      </tr>
      <tr>
        <td id="L650" class="blob-num js-line-number" data-line-number="650"></td>
        <td id="LC650" class="blob-code blob-code-inner js-file-line">                ),</td>
      </tr>
      <tr>
        <td id="L651" class="blob-num js-line-number" data-line-number="651"></td>
        <td id="LC651" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>url</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>avatar_url</span>,</td>
      </tr>
      <tr>
        <td id="L652" class="blob-num js-line-number" data-line-number="652"></td>
        <td id="LC652" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>icon_url</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>avatar_url</span>,</td>
      </tr>
      <tr>
        <td id="L653" class="blob-num js-line-number" data-line-number="653"></td>
        <td id="LC653" class="blob-code blob-code-inner js-file-line">            )</td>
      </tr>
      <tr>
        <td id="L654" class="blob-num js-line-number" data-line-number="654"></td>
        <td id="LC654" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>set_thumbnail</span>(<span class=pl-s1>url</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>avatar_url</span>)</td>
      </tr>
      <tr>
        <td id="L655" class="blob-num js-line-number" data-line-number="655"></td>
        <td id="LC655" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>embed</span><span class=pl-c1>=</span><span class=pl-s1>embed</span>)</td>
      </tr>
      <tr>
        <td id="L656" class="blob-num js-line-number" data-line-number="656"></td>
        <td id="LC656" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L657" class="blob-num js-line-number" data-line-number="657"></td>
        <td id="LC657" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>time</span> <span class=pl-c1>=</span> <span class=pl-s1>datetime</span>.<span class=pl-s1>datetime</span>.<span class=pl-en>utcnow</span>()</td>
      </tr>
      <tr>
        <td id="L658" class="blob-num js-line-number" data-line-number="658"></td>
        <td id="LC658" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>msg</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(</td>
      </tr>
      <tr>
        <td id="L659" class="blob-num js-line-number" data-line-number="659"></td>
        <td id="LC659" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;{emoji} `{time}` **{member}**(`{m_id}`) left the guild. Total members: {users}&quot;</span></td>
      </tr>
      <tr>
        <td id="L660" class="blob-num js-line-number" data-line-number="660"></td>
        <td id="LC660" class="blob-code blob-code-inner js-file-line">            ).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L661" class="blob-num js-line-number" data-line-number="661"></td>
        <td id="LC661" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>emoji</span><span class=pl-c1>=</span><span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;user_left&quot;</span>][<span class=pl-s>&quot;emoji&quot;</span>],</td>
      </tr>
      <tr>
        <td id="L662" class="blob-num js-line-number" data-line-number="662"></td>
        <td id="LC662" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>time</span><span class=pl-c1>=</span><span class=pl-s1>time</span>.<span class=pl-en>strftime</span>(<span class=pl-s>&quot;%H:%M:%S&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L663" class="blob-num js-line-number" data-line-number="663"></td>
        <td id="LC663" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>member</span><span class=pl-c1>=</span><span class=pl-s1>member</span>,</td>
      </tr>
      <tr>
        <td id="L664" class="blob-num js-line-number" data-line-number="664"></td>
        <td id="LC664" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>m_id</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>id</span>,</td>
      </tr>
      <tr>
        <td id="L665" class="blob-num js-line-number" data-line-number="665"></td>
        <td id="LC665" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>users</span><span class=pl-c1>=</span><span class=pl-en>len</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>members</span>),</td>
      </tr>
      <tr>
        <td id="L666" class="blob-num js-line-number" data-line-number="666"></td>
        <td id="LC666" class="blob-code blob-code-inner js-file-line">            )</td>
      </tr>
      <tr>
        <td id="L667" class="blob-num js-line-number" data-line-number="667"></td>
        <td id="LC667" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-s1>perp</span>:</td>
      </tr>
      <tr>
        <td id="L668" class="blob-num js-line-number" data-line-number="668"></td>
        <td id="LC668" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>msg</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(</td>
      </tr>
      <tr>
        <td id="L669" class="blob-num js-line-number" data-line-number="669"></td>
        <td id="LC669" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s>&quot;{emoji} `{time}` **{member}**(`{m_id}`) &quot;</span></td>
      </tr>
      <tr>
        <td id="L670" class="blob-num js-line-number" data-line-number="670"></td>
        <td id="LC670" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s>&quot;was kicked by {perp}. Total members: {users}&quot;</span></td>
      </tr>
      <tr>
        <td id="L671" class="blob-num js-line-number" data-line-number="671"></td>
        <td id="LC671" class="blob-code blob-code-inner js-file-line">                ).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L672" class="blob-num js-line-number" data-line-number="672"></td>
        <td id="LC672" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>emoji</span><span class=pl-c1>=</span><span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;user_left&quot;</span>][<span class=pl-s>&quot;emoji&quot;</span>],</td>
      </tr>
      <tr>
        <td id="L673" class="blob-num js-line-number" data-line-number="673"></td>
        <td id="LC673" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>time</span><span class=pl-c1>=</span><span class=pl-s1>time</span>.<span class=pl-en>strftime</span>(<span class=pl-s>&quot;%H:%M:%S&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L674" class="blob-num js-line-number" data-line-number="674"></td>
        <td id="LC674" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>member</span><span class=pl-c1>=</span><span class=pl-s1>member</span>,</td>
      </tr>
      <tr>
        <td id="L675" class="blob-num js-line-number" data-line-number="675"></td>
        <td id="LC675" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>m_id</span><span class=pl-c1>=</span><span class=pl-s1>member</span>.<span class=pl-s1>id</span>,</td>
      </tr>
      <tr>
        <td id="L676" class="blob-num js-line-number" data-line-number="676"></td>
        <td id="LC676" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>perp</span><span class=pl-c1>=</span><span class=pl-s1>perp</span>,</td>
      </tr>
      <tr>
        <td id="L677" class="blob-num js-line-number" data-line-number="677"></td>
        <td id="LC677" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>users</span><span class=pl-c1>=</span><span class=pl-en>len</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>members</span>),</td>
      </tr>
      <tr>
        <td id="L678" class="blob-num js-line-number" data-line-number="678"></td>
        <td id="LC678" class="blob-code blob-code-inner js-file-line">                )</td>
      </tr>
      <tr>
        <td id="L679" class="blob-num js-line-number" data-line-number="679"></td>
        <td id="LC679" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>msg</span>)</td>
      </tr>
      <tr>
        <td id="L680" class="blob-num js-line-number" data-line-number="680"></td>
        <td id="LC680" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L681" class="blob-num js-line-number" data-line-number="681"></td>
        <td id="LC681" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>async</span> <span class=pl-k>def</span> <span class=pl-en>get_permission_change</span>(</td>
      </tr>
      <tr>
        <td id="L682" class="blob-num js-line-number" data-line-number="682"></td>
        <td id="LC682" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>self</span>, <span class=pl-s1>before</span>: <span class=pl-s1>discord</span>.<span class=pl-s1>abc</span>.<span class=pl-v>GuildChannel</span>, <span class=pl-s1>after</span>: <span class=pl-s1>discord</span>.<span class=pl-s1>abc</span>.<span class=pl-v>GuildChannel</span>, <span class=pl-s1>embed_links</span>: <span class=pl-s1>bool</span></td>
      </tr>
      <tr>
        <td id="L683" class="blob-num js-line-number" data-line-number="683"></td>
        <td id="LC683" class="blob-code blob-code-inner js-file-line">    ) <span class=pl-c1>-&gt;</span> <span class=pl-s1>str</span>:</td>
      </tr>
      <tr>
        <td id="L684" class="blob-num js-line-number" data-line-number="684"></td>
        <td id="LC684" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>p_msg</span> <span class=pl-c1>=</span> <span class=pl-s>&quot;&quot;</span></td>
      </tr>
      <tr>
        <td id="L685" class="blob-num js-line-number" data-line-number="685"></td>
        <td id="LC685" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>before_perms</span> <span class=pl-c1>=</span> {}</td>
      </tr>
      <tr>
        <td id="L686" class="blob-num js-line-number" data-line-number="686"></td>
        <td id="LC686" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>after_perms</span> <span class=pl-c1>=</span> {}</td>
      </tr>
      <tr>
        <td id="L687" class="blob-num js-line-number" data-line-number="687"></td>
        <td id="LC687" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>for</span> <span class=pl-s1>o</span>, <span class=pl-s1>p</span> <span class=pl-c1>in</span> <span class=pl-s1>before</span>.<span class=pl-s1>overwrites</span>.<span class=pl-en>items</span>():</td>
      </tr>
      <tr>
        <td id="L688" class="blob-num js-line-number" data-line-number="688"></td>
        <td id="LC688" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>before_perms</span>[<span class=pl-en>str</span>(<span class=pl-s1>o</span>.<span class=pl-s1>id</span>)] <span class=pl-c1>=</span> [<span class=pl-s1>i</span> <span class=pl-k>for</span> <span class=pl-s1>i</span> <span class=pl-c1>in</span> <span class=pl-s1>p</span>]</td>
      </tr>
      <tr>
        <td id="L689" class="blob-num js-line-number" data-line-number="689"></td>
        <td id="LC689" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>for</span> <span class=pl-s1>o</span>, <span class=pl-s1>p</span> <span class=pl-c1>in</span> <span class=pl-s1>after</span>.<span class=pl-s1>overwrites</span>.<span class=pl-en>items</span>():</td>
      </tr>
      <tr>
        <td id="L690" class="blob-num js-line-number" data-line-number="690"></td>
        <td id="LC690" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>after_perms</span>[<span class=pl-en>str</span>(<span class=pl-s1>o</span>.<span class=pl-s1>id</span>)] <span class=pl-c1>=</span> [<span class=pl-s1>i</span> <span class=pl-k>for</span> <span class=pl-s1>i</span> <span class=pl-c1>in</span> <span class=pl-s1>p</span>]</td>
      </tr>
      <tr>
        <td id="L691" class="blob-num js-line-number" data-line-number="691"></td>
        <td id="LC691" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>for</span> <span class=pl-s1>entity</span> <span class=pl-c1>in</span> <span class=pl-s1>before_perms</span>:</td>
      </tr>
      <tr>
        <td id="L692" class="blob-num js-line-number" data-line-number="692"></td>
        <td id="LC692" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>entity_obj</span> <span class=pl-c1>=</span> <span class=pl-s1>before</span>.<span class=pl-s1>guild</span>.<span class=pl-en>get_role</span>(<span class=pl-en>int</span>(<span class=pl-s1>entity</span>))</td>
      </tr>
      <tr>
        <td id="L693" class="blob-num js-line-number" data-line-number="693"></td>
        <td id="LC693" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>entity_obj</span>:</td>
      </tr>
      <tr>
        <td id="L694" class="blob-num js-line-number" data-line-number="694"></td>
        <td id="LC694" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>entity_obj</span> <span class=pl-c1>=</span> <span class=pl-s1>before</span>.<span class=pl-s1>guild</span>.<span class=pl-en>get_member</span>(<span class=pl-en>int</span>(<span class=pl-s1>entity</span>))</td>
      </tr>
      <tr>
        <td id="L695" class="blob-num js-line-number" data-line-number="695"></td>
        <td id="LC695" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-s1>entity</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>after_perms</span>:</td>
      </tr>
      <tr>
        <td id="L696" class="blob-num js-line-number" data-line-number="696"></td>
        <td id="LC696" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>embed_links</span>:</td>
      </tr>
      <tr>
        <td id="L697" class="blob-num js-line-number" data-line-number="697"></td>
        <td id="LC697" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>p_msg</span> <span class=pl-c1>+=</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>entity_obj</span>.<span class=pl-s1>name</span><span class=pl-kos>}</span></span> Overwrites removed.<span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L698" class="blob-num js-line-number" data-line-number="698"></td>
        <td id="LC698" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L699" class="blob-num js-line-number" data-line-number="699"></td>
        <td id="LC699" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>p_msg</span> <span class=pl-c1>+=</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>entity_obj</span>.<span class=pl-s1>mention</span><span class=pl-kos>}</span></span> Overwrites removed.<span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L700" class="blob-num js-line-number" data-line-number="700"></td>
        <td id="LC700" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>continue</span></td>
      </tr>
      <tr>
        <td id="L701" class="blob-num js-line-number" data-line-number="701"></td>
        <td id="LC701" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-s1>after_perms</span>[<span class=pl-s1>entity</span>] <span class=pl-c1>!=</span> <span class=pl-s1>before_perms</span>[<span class=pl-s1>entity</span>]:</td>
      </tr>
      <tr>
        <td id="L702" class="blob-num js-line-number" data-line-number="702"></td>
        <td id="LC702" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>a</span> <span class=pl-c1>=</span> <span class=pl-en>set</span>(<span class=pl-s1>after_perms</span>[<span class=pl-s1>entity</span>])</td>
      </tr>
      <tr>
        <td id="L703" class="blob-num js-line-number" data-line-number="703"></td>
        <td id="LC703" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>b</span> <span class=pl-c1>=</span> <span class=pl-en>set</span>(<span class=pl-s1>before_perms</span>[<span class=pl-s1>entity</span>])</td>
      </tr>
      <tr>
        <td id="L704" class="blob-num js-line-number" data-line-number="704"></td>
        <td id="LC704" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>a_perms</span> <span class=pl-c1>=</span> <span class=pl-en>list</span>(<span class=pl-s1>a</span> <span class=pl-c1>-</span> <span class=pl-s1>b</span>)</td>
      </tr>
      <tr>
        <td id="L705" class="blob-num js-line-number" data-line-number="705"></td>
        <td id="LC705" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>for</span> <span class=pl-s1>diff</span> <span class=pl-c1>in</span> <span class=pl-s1>a_perms</span>:</td>
      </tr>
      <tr>
        <td id="L706" class="blob-num js-line-number" data-line-number="706"></td>
        <td id="LC706" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>embed_links</span>:</td>
      </tr>
      <tr>
        <td id="L707" class="blob-num js-line-number" data-line-number="707"></td>
        <td id="LC707" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>p_msg</span> <span class=pl-c1>+=</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>entity_obj</span>.<span class=pl-s1>name</span><span class=pl-kos>}</span></span> <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>diff</span>[<span class=pl-c1>0</span>]<span class=pl-kos>}</span></span> Set to <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>diff</span>[<span class=pl-c1>1</span>]<span class=pl-kos>}</span></span><span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L708" class="blob-num js-line-number" data-line-number="708"></td>
        <td id="LC708" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L709" class="blob-num js-line-number" data-line-number="709"></td>
        <td id="LC709" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>p_msg</span> <span class=pl-c1>+=</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>entity_obj</span>.<span class=pl-s1>mention</span><span class=pl-kos>}</span></span> <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>diff</span>[<span class=pl-c1>0</span>]<span class=pl-kos>}</span></span> Set to <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>diff</span>[<span class=pl-c1>1</span>]<span class=pl-kos>}</span></span><span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L710" class="blob-num js-line-number" data-line-number="710"></td>
        <td id="LC710" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>for</span> <span class=pl-s1>entity</span> <span class=pl-c1>in</span> <span class=pl-s1>after_perms</span>:</td>
      </tr>
      <tr>
        <td id="L711" class="blob-num js-line-number" data-line-number="711"></td>
        <td id="LC711" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>entity_obj</span> <span class=pl-c1>=</span> <span class=pl-s1>after</span>.<span class=pl-s1>guild</span>.<span class=pl-en>get_role</span>(<span class=pl-en>int</span>(<span class=pl-s1>entity</span>))</td>
      </tr>
      <tr>
        <td id="L712" class="blob-num js-line-number" data-line-number="712"></td>
        <td id="LC712" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>entity_obj</span>:</td>
      </tr>
      <tr>
        <td id="L713" class="blob-num js-line-number" data-line-number="713"></td>
        <td id="LC713" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>entity_obj</span> <span class=pl-c1>=</span> <span class=pl-s1>after</span>.<span class=pl-s1>guild</span>.<span class=pl-en>get_member</span>(<span class=pl-en>int</span>(<span class=pl-s1>entity</span>))</td>
      </tr>
      <tr>
        <td id="L714" class="blob-num js-line-number" data-line-number="714"></td>
        <td id="LC714" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-s1>entity</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>before_perms</span>:</td>
      </tr>
      <tr>
        <td id="L715" class="blob-num js-line-number" data-line-number="715"></td>
        <td id="LC715" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>embed_links</span>:</td>
      </tr>
      <tr>
        <td id="L716" class="blob-num js-line-number" data-line-number="716"></td>
        <td id="LC716" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>p_msg</span> <span class=pl-c1>+=</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>entity_obj</span>.<span class=pl-s1>name</span><span class=pl-kos>}</span></span> Overwrites added.<span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L717" class="blob-num js-line-number" data-line-number="717"></td>
        <td id="LC717" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L718" class="blob-num js-line-number" data-line-number="718"></td>
        <td id="LC718" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>p_msg</span> <span class=pl-c1>+=</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>entity_obj</span>.<span class=pl-s1>mention</span><span class=pl-kos>}</span></span> Overwrites added.<span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L719" class="blob-num js-line-number" data-line-number="719"></td>
        <td id="LC719" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>continue</span></td>
      </tr>
      <tr>
        <td id="L720" class="blob-num js-line-number" data-line-number="720"></td>
        <td id="LC720" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>return</span> <span class=pl-s1>p_msg</span></td>
      </tr>
      <tr>
        <td id="L721" class="blob-num js-line-number" data-line-number="721"></td>
        <td id="LC721" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L722" class="blob-num js-line-number" data-line-number="722"></td>
        <td id="LC722" class="blob-code blob-code-inner js-file-line">    <span class=pl-en>@<span class=pl-s1>commands</span>.<span class=pl-v>Cog</span>.<span class=pl-s1>listener</span>()</span></td>
      </tr>
      <tr>
        <td id="L723" class="blob-num js-line-number" data-line-number="723"></td>
        <td id="LC723" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>async</span> <span class=pl-k>def</span> <span class=pl-en>on_guild_channel_create</span>(<span class=pl-s1>self</span>, <span class=pl-s1>new_channel</span>: <span class=pl-s1>discord</span>.<span class=pl-s1>abc</span>.<span class=pl-v>GuildChannel</span>) <span class=pl-c1>-&gt;</span> <span class=pl-c1>None</span>:</td>
      </tr>
      <tr>
        <td id="L724" class="blob-num js-line-number" data-line-number="724"></td>
        <td id="LC724" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>guild</span> <span class=pl-c1>=</span> <span class=pl-s1>new_channel</span>.<span class=pl-s1>guild</span></td>
      </tr>
      <tr>
        <td id="L725" class="blob-num js-line-number" data-line-number="725"></td>
        <td id="LC725" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>guild</span>.<span class=pl-s1>id</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>:</td>
      </tr>
      <tr>
        <td id="L726" class="blob-num js-line-number" data-line-number="726"></td>
        <td id="LC726" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L727" class="blob-num js-line-number" data-line-number="727"></td>
        <td id="LC727" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;channel_create&quot;</span>][<span class=pl-s>&quot;enabled&quot;</span>]:</td>
      </tr>
      <tr>
        <td id="L728" class="blob-num js-line-number" data-line-number="728"></td>
        <td id="LC728" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L729" class="blob-num js-line-number" data-line-number="729"></td>
        <td id="LC729" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>version_info</span> <span class=pl-c1>&gt;=</span> <span class=pl-v>VersionInfo</span>.<span class=pl-en>from_str</span>(<span class=pl-s>&quot;3.4.0&quot;</span>):</td>
      </tr>
      <tr>
        <td id="L730" class="blob-num js-line-number" data-line-number="730"></td>
        <td id="LC730" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>bot</span>.<span class=pl-en>cog_disabled_in_guild</span>(<span class=pl-s1>self</span>, <span class=pl-s1>guild</span>):</td>
      </tr>
      <tr>
        <td id="L731" class="blob-num js-line-number" data-line-number="731"></td>
        <td id="LC731" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L732" class="blob-num js-line-number" data-line-number="732"></td>
        <td id="LC732" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>is_ignored_channel</span>(<span class=pl-s1>guild</span>, <span class=pl-s1>new_channel</span>):</td>
      </tr>
      <tr>
        <td id="L733" class="blob-num js-line-number" data-line-number="733"></td>
        <td id="LC733" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L734" class="blob-num js-line-number" data-line-number="734"></td>
        <td id="LC734" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>try</span>:</td>
      </tr>
      <tr>
        <td id="L735" class="blob-num js-line-number" data-line-number="735"></td>
        <td id="LC735" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>modlog_channel</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;channel_create&quot;</span>)</td>
      </tr>
      <tr>
        <td id="L736" class="blob-num js-line-number" data-line-number="736"></td>
        <td id="LC736" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>except</span> <span class=pl-v>RuntimeError</span>:</td>
      </tr>
      <tr>
        <td id="L737" class="blob-num js-line-number" data-line-number="737"></td>
        <td id="LC737" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L738" class="blob-num js-line-number" data-line-number="738"></td>
        <td id="LC738" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed_links</span> <span class=pl-c1>=</span> (</td>
      </tr>
      <tr>
        <td id="L739" class="blob-num js-line-number" data-line-number="739"></td>
        <td id="LC739" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>embed_links</span></td>
      </tr>
      <tr>
        <td id="L740" class="blob-num js-line-number" data-line-number="740"></td>
        <td id="LC740" class="blob-code blob-code-inner js-file-line">            <span class=pl-c1>and</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;channel_create&quot;</span>][<span class=pl-s>&quot;embed&quot;</span>]</td>
      </tr>
      <tr>
        <td id="L741" class="blob-num js-line-number" data-line-number="741"></td>
        <td id="LC741" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L742" class="blob-num js-line-number" data-line-number="742"></td>
        <td id="LC742" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>time</span> <span class=pl-c1>=</span> <span class=pl-s1>datetime</span>.<span class=pl-s1>datetime</span>.<span class=pl-en>utcnow</span>()</td>
      </tr>
      <tr>
        <td id="L743" class="blob-num js-line-number" data-line-number="743"></td>
        <td id="LC743" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>channel_type</span> <span class=pl-c1>=</span> <span class=pl-en>str</span>(<span class=pl-s1>new_channel</span>.<span class=pl-s1>type</span>).<span class=pl-en>title</span>()</td>
      </tr>
      <tr>
        <td id="L744" class="blob-num js-line-number" data-line-number="744"></td>
        <td id="LC744" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>Embed</span>(</td>
      </tr>
      <tr>
        <td id="L745" class="blob-num js-line-number" data-line-number="745"></td>
        <td id="LC745" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>description</span><span class=pl-c1>=</span><span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>new_channel</span>.<span class=pl-s1>mention</span><span class=pl-kos>}</span></span> <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>new_channel</span>.<span class=pl-s1>name</span><span class=pl-kos>}</span></span>&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L746" class="blob-num js-line-number" data-line-number="746"></td>
        <td id="LC746" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>timestamp</span><span class=pl-c1>=</span><span class=pl-s1>time</span>,</td>
      </tr>
      <tr>
        <td id="L747" class="blob-num js-line-number" data-line-number="747"></td>
        <td id="LC747" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>colour</span><span class=pl-c1>=</span><span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>get_event_colour</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;channel_create&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L748" class="blob-num js-line-number" data-line-number="748"></td>
        <td id="LC748" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L749" class="blob-num js-line-number" data-line-number="749"></td>
        <td id="LC749" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed</span>.<span class=pl-en>set_author</span>(</td>
      </tr>
      <tr>
        <td id="L750" class="blob-num js-line-number" data-line-number="750"></td>
        <td id="LC750" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;{chan_type} Channel Created {chan_name} ({chan_id})&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L751" class="blob-num js-line-number" data-line-number="751"></td>
        <td id="LC751" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>chan_type</span><span class=pl-c1>=</span><span class=pl-s1>channel_type</span>, <span class=pl-s1>chan_name</span><span class=pl-c1>=</span><span class=pl-s1>new_channel</span>.<span class=pl-s1>name</span>, <span class=pl-s1>chan_id</span><span class=pl-c1>=</span><span class=pl-s1>new_channel</span>.<span class=pl-s1>id</span></td>
      </tr>
      <tr>
        <td id="L752" class="blob-num js-line-number" data-line-number="752"></td>
        <td id="LC752" class="blob-code blob-code-inner js-file-line">            )</td>
      </tr>
      <tr>
        <td id="L753" class="blob-num js-line-number" data-line-number="753"></td>
        <td id="LC753" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L754" class="blob-num js-line-number" data-line-number="754"></td>
        <td id="LC754" class="blob-code blob-code-inner js-file-line">        <span class=pl-c># msg = _(&quot;Channel Created &quot;) + str(new_channel.id) + &quot;\n&quot;</span></td>
      </tr>
      <tr>
        <td id="L755" class="blob-num js-line-number" data-line-number="755"></td>
        <td id="LC755" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L756" class="blob-num js-line-number" data-line-number="756"></td>
        <td id="LC756" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L757" class="blob-num js-line-number" data-line-number="757"></td>
        <td id="LC757" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>view_audit_log</span>:</td>
      </tr>
      <tr>
        <td id="L758" class="blob-num js-line-number" data-line-number="758"></td>
        <td id="LC758" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>action</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>AuditLogAction</span>.<span class=pl-s1>channel_create</span></td>
      </tr>
      <tr>
        <td id="L759" class="blob-num js-line-number" data-line-number="759"></td>
        <td id="LC759" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>async</span> <span class=pl-k>for</span> <span class=pl-s1>log</span> <span class=pl-c1>in</span> <span class=pl-s1>guild</span>.<span class=pl-en>audit_logs</span>(<span class=pl-s1>limit</span><span class=pl-c1>=</span><span class=pl-c1>2</span>, <span class=pl-s1>action</span><span class=pl-c1>=</span><span class=pl-s1>action</span>):</td>
      </tr>
      <tr>
        <td id="L760" class="blob-num js-line-number" data-line-number="760"></td>
        <td id="LC760" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>target</span>.<span class=pl-s1>id</span> <span class=pl-c1>==</span> <span class=pl-s1>new_channel</span>.<span class=pl-s1>id</span>:</td>
      </tr>
      <tr>
        <td id="L761" class="blob-num js-line-number" data-line-number="761"></td>
        <td id="LC761" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>user</span></td>
      </tr>
      <tr>
        <td id="L762" class="blob-num js-line-number" data-line-number="762"></td>
        <td id="LC762" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L763" class="blob-num js-line-number" data-line-number="763"></td>
        <td id="LC763" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span></td>
      </tr>
      <tr>
        <td id="L764" class="blob-num js-line-number" data-line-number="764"></td>
        <td id="LC764" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>break</span></td>
      </tr>
      <tr>
        <td id="L765" class="blob-num js-line-number" data-line-number="765"></td>
        <td id="LC765" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L766" class="blob-num js-line-number" data-line-number="766"></td>
        <td id="LC766" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>perp_msg</span> <span class=pl-c1>=</span> <span class=pl-s>&quot;&quot;</span></td>
      </tr>
      <tr>
        <td id="L767" class="blob-num js-line-number" data-line-number="767"></td>
        <td id="LC767" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Type&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>channel_type</span>)</td>
      </tr>
      <tr>
        <td id="L768" class="blob-num js-line-number" data-line-number="768"></td>
        <td id="LC768" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>perp</span>:</td>
      </tr>
      <tr>
        <td id="L769" class="blob-num js-line-number" data-line-number="769"></td>
        <td id="LC769" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>perp_msg</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;by {perp} (`{perp_id}`)&quot;</span>).<span class=pl-en>format</span>(<span class=pl-s1>perp</span><span class=pl-c1>=</span><span class=pl-s1>perp</span>, <span class=pl-s1>perp_id</span><span class=pl-c1>=</span><span class=pl-s1>perp</span>.<span class=pl-s1>id</span>)</td>
      </tr>
      <tr>
        <td id="L770" class="blob-num js-line-number" data-line-number="770"></td>
        <td id="LC770" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Created by &quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>perp</span>.<span class=pl-s1>mention</span>)</td>
      </tr>
      <tr>
        <td id="L771" class="blob-num js-line-number" data-line-number="771"></td>
        <td id="LC771" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L772" class="blob-num js-line-number" data-line-number="772"></td>
        <td id="LC772" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>perp_msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot; Reason: {reason}&quot;</span>).<span class=pl-en>format</span>(<span class=pl-s1>reason</span><span class=pl-c1>=</span><span class=pl-s1>reason</span>)</td>
      </tr>
      <tr>
        <td id="L773" class="blob-num js-line-number" data-line-number="773"></td>
        <td id="LC773" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Reason &quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>reason</span>)</td>
      </tr>
      <tr>
        <td id="L774" class="blob-num js-line-number" data-line-number="774"></td>
        <td id="LC774" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>msg</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;{emoji} `{time}` {chan_type} channel created {perp_msg} {channel}&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L775" class="blob-num js-line-number" data-line-number="775"></td>
        <td id="LC775" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>emoji</span><span class=pl-c1>=</span><span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;channel_create&quot;</span>][<span class=pl-s>&quot;emoji&quot;</span>],</td>
      </tr>
      <tr>
        <td id="L776" class="blob-num js-line-number" data-line-number="776"></td>
        <td id="LC776" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>time</span><span class=pl-c1>=</span><span class=pl-s1>time</span>.<span class=pl-en>strftime</span>(<span class=pl-s>&quot;%H:%M:%S&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L777" class="blob-num js-line-number" data-line-number="777"></td>
        <td id="LC777" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>chan_type</span><span class=pl-c1>=</span><span class=pl-s1>channel_type</span>,</td>
      </tr>
      <tr>
        <td id="L778" class="blob-num js-line-number" data-line-number="778"></td>
        <td id="LC778" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>perp_msg</span><span class=pl-c1>=</span><span class=pl-s1>perp_msg</span>,</td>
      </tr>
      <tr>
        <td id="L779" class="blob-num js-line-number" data-line-number="779"></td>
        <td id="LC779" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span><span class=pl-c1>=</span><span class=pl-s1>new_channel</span>.<span class=pl-s1>mention</span>,</td>
      </tr>
      <tr>
        <td id="L780" class="blob-num js-line-number" data-line-number="780"></td>
        <td id="LC780" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L781" class="blob-num js-line-number" data-line-number="781"></td>
        <td id="LC781" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>embed_links</span>:</td>
      </tr>
      <tr>
        <td id="L782" class="blob-num js-line-number" data-line-number="782"></td>
        <td id="LC782" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>embed</span><span class=pl-c1>=</span><span class=pl-s1>embed</span>)</td>
      </tr>
      <tr>
        <td id="L783" class="blob-num js-line-number" data-line-number="783"></td>
        <td id="LC783" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L784" class="blob-num js-line-number" data-line-number="784"></td>
        <td id="LC784" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>msg</span>)</td>
      </tr>
      <tr>
        <td id="L785" class="blob-num js-line-number" data-line-number="785"></td>
        <td id="LC785" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L786" class="blob-num js-line-number" data-line-number="786"></td>
        <td id="LC786" class="blob-code blob-code-inner js-file-line">    <span class=pl-en>@<span class=pl-s1>commands</span>.<span class=pl-v>Cog</span>.<span class=pl-s1>listener</span>()</span></td>
      </tr>
      <tr>
        <td id="L787" class="blob-num js-line-number" data-line-number="787"></td>
        <td id="LC787" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>async</span> <span class=pl-k>def</span> <span class=pl-en>on_guild_channel_delete</span>(<span class=pl-s1>self</span>, <span class=pl-s1>old_channel</span>: <span class=pl-s1>discord</span>.<span class=pl-s1>abc</span>.<span class=pl-v>GuildChannel</span>):</td>
      </tr>
      <tr>
        <td id="L788" class="blob-num js-line-number" data-line-number="788"></td>
        <td id="LC788" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>guild</span> <span class=pl-c1>=</span> <span class=pl-s1>old_channel</span>.<span class=pl-s1>guild</span></td>
      </tr>
      <tr>
        <td id="L789" class="blob-num js-line-number" data-line-number="789"></td>
        <td id="LC789" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>guild</span>.<span class=pl-s1>id</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>:</td>
      </tr>
      <tr>
        <td id="L790" class="blob-num js-line-number" data-line-number="790"></td>
        <td id="LC790" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L791" class="blob-num js-line-number" data-line-number="791"></td>
        <td id="LC791" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;channel_delete&quot;</span>][<span class=pl-s>&quot;enabled&quot;</span>]:</td>
      </tr>
      <tr>
        <td id="L792" class="blob-num js-line-number" data-line-number="792"></td>
        <td id="LC792" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L793" class="blob-num js-line-number" data-line-number="793"></td>
        <td id="LC793" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>version_info</span> <span class=pl-c1>&gt;=</span> <span class=pl-v>VersionInfo</span>.<span class=pl-en>from_str</span>(<span class=pl-s>&quot;3.4.0&quot;</span>):</td>
      </tr>
      <tr>
        <td id="L794" class="blob-num js-line-number" data-line-number="794"></td>
        <td id="LC794" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>bot</span>.<span class=pl-en>cog_disabled_in_guild</span>(<span class=pl-s1>self</span>, <span class=pl-s1>guild</span>):</td>
      </tr>
      <tr>
        <td id="L795" class="blob-num js-line-number" data-line-number="795"></td>
        <td id="LC795" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L796" class="blob-num js-line-number" data-line-number="796"></td>
        <td id="LC796" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>is_ignored_channel</span>(<span class=pl-s1>guild</span>, <span class=pl-s1>old_channel</span>):</td>
      </tr>
      <tr>
        <td id="L797" class="blob-num js-line-number" data-line-number="797"></td>
        <td id="LC797" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L798" class="blob-num js-line-number" data-line-number="798"></td>
        <td id="LC798" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>try</span>:</td>
      </tr>
      <tr>
        <td id="L799" class="blob-num js-line-number" data-line-number="799"></td>
        <td id="LC799" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>modlog_channel</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;channel_delete&quot;</span>)</td>
      </tr>
      <tr>
        <td id="L800" class="blob-num js-line-number" data-line-number="800"></td>
        <td id="LC800" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>except</span> <span class=pl-v>RuntimeError</span>:</td>
      </tr>
      <tr>
        <td id="L801" class="blob-num js-line-number" data-line-number="801"></td>
        <td id="LC801" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L802" class="blob-num js-line-number" data-line-number="802"></td>
        <td id="LC802" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed_links</span> <span class=pl-c1>=</span> (</td>
      </tr>
      <tr>
        <td id="L803" class="blob-num js-line-number" data-line-number="803"></td>
        <td id="LC803" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>embed_links</span></td>
      </tr>
      <tr>
        <td id="L804" class="blob-num js-line-number" data-line-number="804"></td>
        <td id="LC804" class="blob-code blob-code-inner js-file-line">            <span class=pl-c1>and</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;channel_delete&quot;</span>][<span class=pl-s>&quot;embed&quot;</span>]</td>
      </tr>
      <tr>
        <td id="L805" class="blob-num js-line-number" data-line-number="805"></td>
        <td id="LC805" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L806" class="blob-num js-line-number" data-line-number="806"></td>
        <td id="LC806" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>channel_type</span> <span class=pl-c1>=</span> <span class=pl-en>str</span>(<span class=pl-s1>old_channel</span>.<span class=pl-s1>type</span>).<span class=pl-en>title</span>()</td>
      </tr>
      <tr>
        <td id="L807" class="blob-num js-line-number" data-line-number="807"></td>
        <td id="LC807" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>time</span> <span class=pl-c1>=</span> <span class=pl-s1>datetime</span>.<span class=pl-s1>datetime</span>.<span class=pl-en>utcnow</span>()</td>
      </tr>
      <tr>
        <td id="L808" class="blob-num js-line-number" data-line-number="808"></td>
        <td id="LC808" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>Embed</span>(</td>
      </tr>
      <tr>
        <td id="L809" class="blob-num js-line-number" data-line-number="809"></td>
        <td id="LC809" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>description</span><span class=pl-c1>=</span><span class=pl-s1>old_channel</span>.<span class=pl-s1>name</span>,</td>
      </tr>
      <tr>
        <td id="L810" class="blob-num js-line-number" data-line-number="810"></td>
        <td id="LC810" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>timestamp</span><span class=pl-c1>=</span><span class=pl-s1>time</span>,</td>
      </tr>
      <tr>
        <td id="L811" class="blob-num js-line-number" data-line-number="811"></td>
        <td id="LC811" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>colour</span><span class=pl-c1>=</span><span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>get_event_colour</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;channel_delete&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L812" class="blob-num js-line-number" data-line-number="812"></td>
        <td id="LC812" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L813" class="blob-num js-line-number" data-line-number="813"></td>
        <td id="LC813" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed</span>.<span class=pl-en>set_author</span>(</td>
      </tr>
      <tr>
        <td id="L814" class="blob-num js-line-number" data-line-number="814"></td>
        <td id="LC814" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;{chan_type} Channel Deleted {chan_name} ({chan_id})&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L815" class="blob-num js-line-number" data-line-number="815"></td>
        <td id="LC815" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>chan_type</span><span class=pl-c1>=</span><span class=pl-s1>channel_type</span>, <span class=pl-s1>chan_name</span><span class=pl-c1>=</span><span class=pl-s1>old_channel</span>.<span class=pl-s1>name</span>, <span class=pl-s1>chan_id</span><span class=pl-c1>=</span><span class=pl-s1>old_channel</span>.<span class=pl-s1>id</span></td>
      </tr>
      <tr>
        <td id="L816" class="blob-num js-line-number" data-line-number="816"></td>
        <td id="LC816" class="blob-code blob-code-inner js-file-line">            )</td>
      </tr>
      <tr>
        <td id="L817" class="blob-num js-line-number" data-line-number="817"></td>
        <td id="LC817" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L818" class="blob-num js-line-number" data-line-number="818"></td>
        <td id="LC818" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L819" class="blob-num js-line-number" data-line-number="819"></td>
        <td id="LC819" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L820" class="blob-num js-line-number" data-line-number="820"></td>
        <td id="LC820" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>view_audit_log</span>:</td>
      </tr>
      <tr>
        <td id="L821" class="blob-num js-line-number" data-line-number="821"></td>
        <td id="LC821" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>action</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>AuditLogAction</span>.<span class=pl-s1>channel_delete</span></td>
      </tr>
      <tr>
        <td id="L822" class="blob-num js-line-number" data-line-number="822"></td>
        <td id="LC822" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>async</span> <span class=pl-k>for</span> <span class=pl-s1>log</span> <span class=pl-c1>in</span> <span class=pl-s1>guild</span>.<span class=pl-en>audit_logs</span>(<span class=pl-s1>limit</span><span class=pl-c1>=</span><span class=pl-c1>2</span>, <span class=pl-s1>action</span><span class=pl-c1>=</span><span class=pl-s1>action</span>):</td>
      </tr>
      <tr>
        <td id="L823" class="blob-num js-line-number" data-line-number="823"></td>
        <td id="LC823" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>target</span>.<span class=pl-s1>id</span> <span class=pl-c1>==</span> <span class=pl-s1>old_channel</span>.<span class=pl-s1>id</span>:</td>
      </tr>
      <tr>
        <td id="L824" class="blob-num js-line-number" data-line-number="824"></td>
        <td id="LC824" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>user</span></td>
      </tr>
      <tr>
        <td id="L825" class="blob-num js-line-number" data-line-number="825"></td>
        <td id="LC825" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L826" class="blob-num js-line-number" data-line-number="826"></td>
        <td id="LC826" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span></td>
      </tr>
      <tr>
        <td id="L827" class="blob-num js-line-number" data-line-number="827"></td>
        <td id="LC827" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>break</span></td>
      </tr>
      <tr>
        <td id="L828" class="blob-num js-line-number" data-line-number="828"></td>
        <td id="LC828" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>perp_msg</span> <span class=pl-c1>=</span> <span class=pl-s>&quot;&quot;</span></td>
      </tr>
      <tr>
        <td id="L829" class="blob-num js-line-number" data-line-number="829"></td>
        <td id="LC829" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Type&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>channel_type</span>)</td>
      </tr>
      <tr>
        <td id="L830" class="blob-num js-line-number" data-line-number="830"></td>
        <td id="LC830" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>perp</span>:</td>
      </tr>
      <tr>
        <td id="L831" class="blob-num js-line-number" data-line-number="831"></td>
        <td id="LC831" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>perp_msg</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;by {perp} (`{perp_id}`)&quot;</span>).<span class=pl-en>format</span>(<span class=pl-s1>perp</span><span class=pl-c1>=</span><span class=pl-s1>perp</span>, <span class=pl-s1>perp_id</span><span class=pl-c1>=</span><span class=pl-s1>perp</span>.<span class=pl-s1>id</span>)</td>
      </tr>
      <tr>
        <td id="L832" class="blob-num js-line-number" data-line-number="832"></td>
        <td id="LC832" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Deleted by &quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>perp</span>.<span class=pl-s1>mention</span>)</td>
      </tr>
      <tr>
        <td id="L833" class="blob-num js-line-number" data-line-number="833"></td>
        <td id="LC833" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L834" class="blob-num js-line-number" data-line-number="834"></td>
        <td id="LC834" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>perp_msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot; Reason: {reason}&quot;</span>).<span class=pl-en>format</span>(<span class=pl-s1>reason</span><span class=pl-c1>=</span><span class=pl-s1>reason</span>)</td>
      </tr>
      <tr>
        <td id="L835" class="blob-num js-line-number" data-line-number="835"></td>
        <td id="LC835" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Reason &quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>reason</span>)</td>
      </tr>
      <tr>
        <td id="L836" class="blob-num js-line-number" data-line-number="836"></td>
        <td id="LC836" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>msg</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;{emoji} `{time}` {chan_type} channel deleted {perp_msg} {channel}&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L837" class="blob-num js-line-number" data-line-number="837"></td>
        <td id="LC837" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>emoji</span><span class=pl-c1>=</span><span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;channel_delete&quot;</span>][<span class=pl-s>&quot;emoji&quot;</span>],</td>
      </tr>
      <tr>
        <td id="L838" class="blob-num js-line-number" data-line-number="838"></td>
        <td id="LC838" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>time</span><span class=pl-c1>=</span><span class=pl-s1>time</span>.<span class=pl-en>strftime</span>(<span class=pl-s>&quot;%H:%M:%S&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L839" class="blob-num js-line-number" data-line-number="839"></td>
        <td id="LC839" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>chan_type</span><span class=pl-c1>=</span><span class=pl-s1>channel_type</span>,</td>
      </tr>
      <tr>
        <td id="L840" class="blob-num js-line-number" data-line-number="840"></td>
        <td id="LC840" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>perp_msg</span><span class=pl-c1>=</span><span class=pl-s1>perp_msg</span>,</td>
      </tr>
      <tr>
        <td id="L841" class="blob-num js-line-number" data-line-number="841"></td>
        <td id="LC841" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span><span class=pl-c1>=</span><span class=pl-s>f&quot;#<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>old_channel</span>.<span class=pl-s1>name</span><span class=pl-kos>}</span></span> (<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>old_channel</span>.<span class=pl-s1>id</span><span class=pl-kos>}</span></span>)&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L842" class="blob-num js-line-number" data-line-number="842"></td>
        <td id="LC842" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L843" class="blob-num js-line-number" data-line-number="843"></td>
        <td id="LC843" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>embed_links</span>:</td>
      </tr>
      <tr>
        <td id="L844" class="blob-num js-line-number" data-line-number="844"></td>
        <td id="LC844" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>embed</span><span class=pl-c1>=</span><span class=pl-s1>embed</span>)</td>
      </tr>
      <tr>
        <td id="L845" class="blob-num js-line-number" data-line-number="845"></td>
        <td id="LC845" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L846" class="blob-num js-line-number" data-line-number="846"></td>
        <td id="LC846" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>msg</span>)</td>
      </tr>
      <tr>
        <td id="L847" class="blob-num js-line-number" data-line-number="847"></td>
        <td id="LC847" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L848" class="blob-num js-line-number" data-line-number="848"></td>
        <td id="LC848" class="blob-code blob-code-inner js-file-line">    <span class=pl-en>@<span class=pl-s1>commands</span>.<span class=pl-v>Cog</span>.<span class=pl-s1>listener</span>()</span></td>
      </tr>
      <tr>
        <td id="L849" class="blob-num js-line-number" data-line-number="849"></td>
        <td id="LC849" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>async</span> <span class=pl-k>def</span> <span class=pl-en>on_guild_channel_update</span>(</td>
      </tr>
      <tr>
        <td id="L850" class="blob-num js-line-number" data-line-number="850"></td>
        <td id="LC850" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>self</span>, <span class=pl-s1>before</span>: <span class=pl-s1>discord</span>.<span class=pl-s1>abc</span>.<span class=pl-v>GuildChannel</span>, <span class=pl-s1>after</span>: <span class=pl-s1>discord</span>.<span class=pl-s1>abc</span>.<span class=pl-v>GuildChannel</span></td>
      </tr>
      <tr>
        <td id="L851" class="blob-num js-line-number" data-line-number="851"></td>
        <td id="LC851" class="blob-code blob-code-inner js-file-line">    ) <span class=pl-c1>-&gt;</span> <span class=pl-c1>None</span>:</td>
      </tr>
      <tr>
        <td id="L852" class="blob-num js-line-number" data-line-number="852"></td>
        <td id="LC852" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>guild</span> <span class=pl-c1>=</span> <span class=pl-s1>before</span>.<span class=pl-s1>guild</span></td>
      </tr>
      <tr>
        <td id="L853" class="blob-num js-line-number" data-line-number="853"></td>
        <td id="LC853" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>guild</span>.<span class=pl-s1>id</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>:</td>
      </tr>
      <tr>
        <td id="L854" class="blob-num js-line-number" data-line-number="854"></td>
        <td id="LC854" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L855" class="blob-num js-line-number" data-line-number="855"></td>
        <td id="LC855" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>version_info</span> <span class=pl-c1>&gt;=</span> <span class=pl-v>VersionInfo</span>.<span class=pl-en>from_str</span>(<span class=pl-s>&quot;3.4.0&quot;</span>):</td>
      </tr>
      <tr>
        <td id="L856" class="blob-num js-line-number" data-line-number="856"></td>
        <td id="LC856" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>bot</span>.<span class=pl-en>cog_disabled_in_guild</span>(<span class=pl-s1>self</span>, <span class=pl-s1>guild</span>):</td>
      </tr>
      <tr>
        <td id="L857" class="blob-num js-line-number" data-line-number="857"></td>
        <td id="LC857" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L858" class="blob-num js-line-number" data-line-number="858"></td>
        <td id="LC858" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;channel_change&quot;</span>][<span class=pl-s>&quot;enabled&quot;</span>]:</td>
      </tr>
      <tr>
        <td id="L859" class="blob-num js-line-number" data-line-number="859"></td>
        <td id="LC859" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L860" class="blob-num js-line-number" data-line-number="860"></td>
        <td id="LC860" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>try</span>:</td>
      </tr>
      <tr>
        <td id="L861" class="blob-num js-line-number" data-line-number="861"></td>
        <td id="LC861" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>modlog_channel</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;channel_change&quot;</span>)</td>
      </tr>
      <tr>
        <td id="L862" class="blob-num js-line-number" data-line-number="862"></td>
        <td id="LC862" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>except</span> <span class=pl-v>RuntimeError</span>:</td>
      </tr>
      <tr>
        <td id="L863" class="blob-num js-line-number" data-line-number="863"></td>
        <td id="LC863" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L864" class="blob-num js-line-number" data-line-number="864"></td>
        <td id="LC864" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed_links</span> <span class=pl-c1>=</span> (</td>
      </tr>
      <tr>
        <td id="L865" class="blob-num js-line-number" data-line-number="865"></td>
        <td id="LC865" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>embed_links</span></td>
      </tr>
      <tr>
        <td id="L866" class="blob-num js-line-number" data-line-number="866"></td>
        <td id="LC866" class="blob-code blob-code-inner js-file-line">            <span class=pl-c1>and</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;channel_change&quot;</span>][<span class=pl-s>&quot;embed&quot;</span>]</td>
      </tr>
      <tr>
        <td id="L867" class="blob-num js-line-number" data-line-number="867"></td>
        <td id="LC867" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L868" class="blob-num js-line-number" data-line-number="868"></td>
        <td id="LC868" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>channel_type</span> <span class=pl-c1>=</span> <span class=pl-en>str</span>(<span class=pl-s1>after</span>.<span class=pl-s1>type</span>).<span class=pl-en>title</span>()</td>
      </tr>
      <tr>
        <td id="L869" class="blob-num js-line-number" data-line-number="869"></td>
        <td id="LC869" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>time</span> <span class=pl-c1>=</span> <span class=pl-s1>datetime</span>.<span class=pl-s1>datetime</span>.<span class=pl-en>utcnow</span>()</td>
      </tr>
      <tr>
        <td id="L870" class="blob-num js-line-number" data-line-number="870"></td>
        <td id="LC870" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>Embed</span>(</td>
      </tr>
      <tr>
        <td id="L871" class="blob-num js-line-number" data-line-number="871"></td>
        <td id="LC871" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>description</span><span class=pl-c1>=</span><span class=pl-s1>after</span>.<span class=pl-s1>mention</span>,</td>
      </tr>
      <tr>
        <td id="L872" class="blob-num js-line-number" data-line-number="872"></td>
        <td id="LC872" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>timestamp</span><span class=pl-c1>=</span><span class=pl-s1>time</span>,</td>
      </tr>
      <tr>
        <td id="L873" class="blob-num js-line-number" data-line-number="873"></td>
        <td id="LC873" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>colour</span><span class=pl-c1>=</span><span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>get_event_colour</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;channel_create&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L874" class="blob-num js-line-number" data-line-number="874"></td>
        <td id="LC874" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L875" class="blob-num js-line-number" data-line-number="875"></td>
        <td id="LC875" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed</span>.<span class=pl-en>set_author</span>(</td>
      </tr>
      <tr>
        <td id="L876" class="blob-num js-line-number" data-line-number="876"></td>
        <td id="LC876" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;{chan_type} Channel Updated {chan_name} ({chan_id})&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L877" class="blob-num js-line-number" data-line-number="877"></td>
        <td id="LC877" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>chan_type</span><span class=pl-c1>=</span><span class=pl-s1>channel_type</span>, <span class=pl-s1>chan_name</span><span class=pl-c1>=</span><span class=pl-s1>before</span>.<span class=pl-s1>name</span>, <span class=pl-s1>chan_id</span><span class=pl-c1>=</span><span class=pl-s1>before</span>.<span class=pl-s1>id</span></td>
      </tr>
      <tr>
        <td id="L878" class="blob-num js-line-number" data-line-number="878"></td>
        <td id="LC878" class="blob-code blob-code-inner js-file-line">            )</td>
      </tr>
      <tr>
        <td id="L879" class="blob-num js-line-number" data-line-number="879"></td>
        <td id="LC879" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L880" class="blob-num js-line-number" data-line-number="880"></td>
        <td id="LC880" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>msg</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;{emoji} `{time}` Updated channel {channel}<span class=pl-cce>\n</span>&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L881" class="blob-num js-line-number" data-line-number="881"></td>
        <td id="LC881" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>emoji</span><span class=pl-c1>=</span><span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;channel_change&quot;</span>][<span class=pl-s>&quot;emoji&quot;</span>],</td>
      </tr>
      <tr>
        <td id="L882" class="blob-num js-line-number" data-line-number="882"></td>
        <td id="LC882" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>time</span><span class=pl-c1>=</span><span class=pl-s1>time</span>.<span class=pl-en>strftime</span>(<span class=pl-s>&quot;%H:%M:%S&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L883" class="blob-num js-line-number" data-line-number="883"></td>
        <td id="LC883" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span><span class=pl-c1>=</span><span class=pl-s1>before</span>.<span class=pl-s1>name</span>,</td>
      </tr>
      <tr>
        <td id="L884" class="blob-num js-line-number" data-line-number="884"></td>
        <td id="LC884" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L885" class="blob-num js-line-number" data-line-number="885"></td>
        <td id="LC885" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L886" class="blob-num js-line-number" data-line-number="886"></td>
        <td id="LC886" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L887" class="blob-num js-line-number" data-line-number="887"></td>
        <td id="LC887" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>worth_updating</span> <span class=pl-c1>=</span> <span class=pl-c1>False</span></td>
      </tr>
      <tr>
        <td id="L888" class="blob-num js-line-number" data-line-number="888"></td>
        <td id="LC888" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>view_audit_log</span>:</td>
      </tr>
      <tr>
        <td id="L889" class="blob-num js-line-number" data-line-number="889"></td>
        <td id="LC889" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>action</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>AuditLogAction</span>.<span class=pl-s1>channel_update</span></td>
      </tr>
      <tr>
        <td id="L890" class="blob-num js-line-number" data-line-number="890"></td>
        <td id="LC890" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>async</span> <span class=pl-k>for</span> <span class=pl-s1>log</span> <span class=pl-c1>in</span> <span class=pl-s1>guild</span>.<span class=pl-en>audit_logs</span>(<span class=pl-s1>limit</span><span class=pl-c1>=</span><span class=pl-c1>5</span>, <span class=pl-s1>action</span><span class=pl-c1>=</span><span class=pl-s1>action</span>):</td>
      </tr>
      <tr>
        <td id="L891" class="blob-num js-line-number" data-line-number="891"></td>
        <td id="LC891" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>target</span>.<span class=pl-s1>id</span> <span class=pl-c1>==</span> <span class=pl-s1>before</span>.<span class=pl-s1>id</span>:</td>
      </tr>
      <tr>
        <td id="L892" class="blob-num js-line-number" data-line-number="892"></td>
        <td id="LC892" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>user</span></td>
      </tr>
      <tr>
        <td id="L893" class="blob-num js-line-number" data-line-number="893"></td>
        <td id="LC893" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L894" class="blob-num js-line-number" data-line-number="894"></td>
        <td id="LC894" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span></td>
      </tr>
      <tr>
        <td id="L895" class="blob-num js-line-number" data-line-number="895"></td>
        <td id="LC895" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>break</span></td>
      </tr>
      <tr>
        <td id="L896" class="blob-num js-line-number" data-line-number="896"></td>
        <td id="LC896" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-en>type</span>(<span class=pl-s1>before</span>) <span class=pl-c1>==</span> <span class=pl-s1>discord</span>.<span class=pl-v>TextChannel</span>:</td>
      </tr>
      <tr>
        <td id="L897" class="blob-num js-line-number" data-line-number="897"></td>
        <td id="LC897" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>text_updates</span> <span class=pl-c1>=</span> {</td>
      </tr>
      <tr>
        <td id="L898" class="blob-num js-line-number" data-line-number="898"></td>
        <td id="LC898" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;name&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Name:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L899" class="blob-num js-line-number" data-line-number="899"></td>
        <td id="LC899" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;topic&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Topic:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L900" class="blob-num js-line-number" data-line-number="900"></td>
        <td id="LC900" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;category&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Category:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L901" class="blob-num js-line-number" data-line-number="901"></td>
        <td id="LC901" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;slowmode_delay&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Slowmode delay:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L902" class="blob-num js-line-number" data-line-number="902"></td>
        <td id="LC902" class="blob-code blob-code-inner js-file-line">            }</td>
      </tr>
      <tr>
        <td id="L903" class="blob-num js-line-number" data-line-number="903"></td>
        <td id="LC903" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L904" class="blob-num js-line-number" data-line-number="904"></td>
        <td id="LC904" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>for</span> <span class=pl-s1>attr</span>, <span class=pl-s1>name</span> <span class=pl-c1>in</span> <span class=pl-s1>text_updates</span>.<span class=pl-en>items</span>():</td>
      </tr>
      <tr>
        <td id="L905" class="blob-num js-line-number" data-line-number="905"></td>
        <td id="LC905" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>before_attr</span> <span class=pl-c1>=</span> <span class=pl-en>getattr</span>(<span class=pl-s1>before</span>, <span class=pl-s1>attr</span>)</td>
      </tr>
      <tr>
        <td id="L906" class="blob-num js-line-number" data-line-number="906"></td>
        <td id="LC906" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>after_attr</span> <span class=pl-c1>=</span> <span class=pl-en>getattr</span>(<span class=pl-s1>after</span>, <span class=pl-s1>attr</span>)</td>
      </tr>
      <tr>
        <td id="L907" class="blob-num js-line-number" data-line-number="907"></td>
        <td id="LC907" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>before_attr</span> <span class=pl-c1>!=</span> <span class=pl-s1>after_attr</span>:</td>
      </tr>
      <tr>
        <td id="L908" class="blob-num js-line-number" data-line-number="908"></td>
        <td id="LC908" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>worth_updating</span> <span class=pl-c1>=</span> <span class=pl-c1>True</span></td>
      </tr>
      <tr>
        <td id="L909" class="blob-num js-line-number" data-line-number="909"></td>
        <td id="LC909" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>if</span> <span class=pl-s1>before_attr</span> <span class=pl-c1>==</span> <span class=pl-s>&quot;&quot;</span>:</td>
      </tr>
      <tr>
        <td id="L910" class="blob-num js-line-number" data-line-number="910"></td>
        <td id="LC910" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>before_attr</span> <span class=pl-c1>=</span> <span class=pl-s>&quot;None&quot;</span></td>
      </tr>
      <tr>
        <td id="L911" class="blob-num js-line-number" data-line-number="911"></td>
        <td id="LC911" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>if</span> <span class=pl-s1>after_attr</span> <span class=pl-c1>==</span> <span class=pl-s>&quot;&quot;</span>:</td>
      </tr>
      <tr>
        <td id="L912" class="blob-num js-line-number" data-line-number="912"></td>
        <td id="LC912" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>after_attr</span> <span class=pl-c1>=</span> <span class=pl-s>&quot;None&quot;</span></td>
      </tr>
      <tr>
        <td id="L913" class="blob-num js-line-number" data-line-number="913"></td>
        <td id="LC913" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Before &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>name</span><span class=pl-kos>}</span></span> <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>before_attr</span><span class=pl-kos>}</span></span><span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L914" class="blob-num js-line-number" data-line-number="914"></td>
        <td id="LC914" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;After &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>name</span><span class=pl-kos>}</span></span> <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>after_attr</span><span class=pl-kos>}</span></span><span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L915" class="blob-num js-line-number" data-line-number="915"></td>
        <td id="LC915" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Before &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>name</span>, <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>before_attr</span>)[:<span class=pl-c1>1024</span>])</td>
      </tr>
      <tr>
        <td id="L916" class="blob-num js-line-number" data-line-number="916"></td>
        <td id="LC916" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;After &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>name</span>, <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>after_attr</span>)[:<span class=pl-c1>1024</span>])</td>
      </tr>
      <tr>
        <td id="L917" class="blob-num js-line-number" data-line-number="917"></td>
        <td id="LC917" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-s1>before</span>.<span class=pl-en>is_nsfw</span>() <span class=pl-c1>!=</span> <span class=pl-s1>after</span>.<span class=pl-en>is_nsfw</span>():</td>
      </tr>
      <tr>
        <td id="L918" class="blob-num js-line-number" data-line-number="918"></td>
        <td id="LC918" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>worth_updating</span> <span class=pl-c1>=</span> <span class=pl-c1>True</span></td>
      </tr>
      <tr>
        <td id="L919" class="blob-num js-line-number" data-line-number="919"></td>
        <td id="LC919" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Before &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s>f&quot;NSFW <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>before</span>.<span class=pl-en>is_nsfw</span>()<span class=pl-kos>}</span></span><span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L920" class="blob-num js-line-number" data-line-number="920"></td>
        <td id="LC920" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;After &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s>f&quot;NSFW <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>after</span>.<span class=pl-en>is_nsfw</span>()<span class=pl-kos>}</span></span><span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L921" class="blob-num js-line-number" data-line-number="921"></td>
        <td id="LC921" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Before &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s>&quot;NSFW&quot;</span>, <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>before</span>.<span class=pl-en>is_nsfw</span>()))</td>
      </tr>
      <tr>
        <td id="L922" class="blob-num js-line-number" data-line-number="922"></td>
        <td id="LC922" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;After &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s>&quot;NSFW&quot;</span>, <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>after</span>.<span class=pl-en>is_nsfw</span>()))</td>
      </tr>
      <tr>
        <td id="L923" class="blob-num js-line-number" data-line-number="923"></td>
        <td id="LC923" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>p_msg</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>get_permission_change</span>(<span class=pl-s1>before</span>, <span class=pl-s1>after</span>, <span class=pl-s1>embed_links</span>)</td>
      </tr>
      <tr>
        <td id="L924" class="blob-num js-line-number" data-line-number="924"></td>
        <td id="LC924" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-s1>p_msg</span> <span class=pl-c1>!=</span> <span class=pl-s>&quot;&quot;</span>:</td>
      </tr>
      <tr>
        <td id="L925" class="blob-num js-line-number" data-line-number="925"></td>
        <td id="LC925" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>worth_updating</span> <span class=pl-c1>=</span> <span class=pl-c1>True</span></td>
      </tr>
      <tr>
        <td id="L926" class="blob-num js-line-number" data-line-number="926"></td>
        <td id="LC926" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Permissions Changed: &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>p_msg</span></td>
      </tr>
      <tr>
        <td id="L927" class="blob-num js-line-number" data-line-number="927"></td>
        <td id="LC927" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Permissions&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>p_msg</span>[:<span class=pl-c1>1024</span>])</td>
      </tr>
      <tr>
        <td id="L928" class="blob-num js-line-number" data-line-number="928"></td>
        <td id="LC928" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L929" class="blob-num js-line-number" data-line-number="929"></td>
        <td id="LC929" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-en>type</span>(<span class=pl-s1>before</span>) <span class=pl-c1>==</span> <span class=pl-s1>discord</span>.<span class=pl-v>VoiceChannel</span>:</td>
      </tr>
      <tr>
        <td id="L930" class="blob-num js-line-number" data-line-number="930"></td>
        <td id="LC930" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>voice_updates</span> <span class=pl-c1>=</span> {</td>
      </tr>
      <tr>
        <td id="L931" class="blob-num js-line-number" data-line-number="931"></td>
        <td id="LC931" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;name&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Name:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L932" class="blob-num js-line-number" data-line-number="932"></td>
        <td id="LC932" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;position&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Position:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L933" class="blob-num js-line-number" data-line-number="933"></td>
        <td id="LC933" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;category&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Category:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L934" class="blob-num js-line-number" data-line-number="934"></td>
        <td id="LC934" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;bitrate&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Bitrate:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L935" class="blob-num js-line-number" data-line-number="935"></td>
        <td id="LC935" class="blob-code blob-code-inner js-file-line">                <span class=pl-s>&quot;user_limit&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;User limit:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L936" class="blob-num js-line-number" data-line-number="936"></td>
        <td id="LC936" class="blob-code blob-code-inner js-file-line">            }</td>
      </tr>
      <tr>
        <td id="L937" class="blob-num js-line-number" data-line-number="937"></td>
        <td id="LC937" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>for</span> <span class=pl-s1>attr</span>, <span class=pl-s1>name</span> <span class=pl-c1>in</span> <span class=pl-s1>voice_updates</span>.<span class=pl-en>items</span>():</td>
      </tr>
      <tr>
        <td id="L938" class="blob-num js-line-number" data-line-number="938"></td>
        <td id="LC938" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>before_attr</span> <span class=pl-c1>=</span> <span class=pl-en>getattr</span>(<span class=pl-s1>before</span>, <span class=pl-s1>attr</span>)</td>
      </tr>
      <tr>
        <td id="L939" class="blob-num js-line-number" data-line-number="939"></td>
        <td id="LC939" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>after_attr</span> <span class=pl-c1>=</span> <span class=pl-en>getattr</span>(<span class=pl-s1>after</span>, <span class=pl-s1>attr</span>)</td>
      </tr>
      <tr>
        <td id="L940" class="blob-num js-line-number" data-line-number="940"></td>
        <td id="LC940" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>before_attr</span> <span class=pl-c1>!=</span> <span class=pl-s1>after_attr</span>:</td>
      </tr>
      <tr>
        <td id="L941" class="blob-num js-line-number" data-line-number="941"></td>
        <td id="LC941" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>worth_updating</span> <span class=pl-c1>=</span> <span class=pl-c1>True</span></td>
      </tr>
      <tr>
        <td id="L942" class="blob-num js-line-number" data-line-number="942"></td>
        <td id="LC942" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Before &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>name</span><span class=pl-kos>}</span></span> <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>before_attr</span><span class=pl-kos>}</span></span><span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L943" class="blob-num js-line-number" data-line-number="943"></td>
        <td id="LC943" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;After &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>name</span><span class=pl-kos>}</span></span> <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>after_attr</span><span class=pl-kos>}</span></span><span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L944" class="blob-num js-line-number" data-line-number="944"></td>
        <td id="LC944" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Before &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>name</span>, <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>before_attr</span>))</td>
      </tr>
      <tr>
        <td id="L945" class="blob-num js-line-number" data-line-number="945"></td>
        <td id="LC945" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;After &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>name</span>, <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>after_attr</span>))</td>
      </tr>
      <tr>
        <td id="L946" class="blob-num js-line-number" data-line-number="946"></td>
        <td id="LC946" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>p_msg</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>get_permission_change</span>(<span class=pl-s1>before</span>, <span class=pl-s1>after</span>, <span class=pl-s1>embed_links</span>)</td>
      </tr>
      <tr>
        <td id="L947" class="blob-num js-line-number" data-line-number="947"></td>
        <td id="LC947" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-s1>p_msg</span> <span class=pl-c1>!=</span> <span class=pl-s>&quot;&quot;</span>:</td>
      </tr>
      <tr>
        <td id="L948" class="blob-num js-line-number" data-line-number="948"></td>
        <td id="LC948" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>worth_updating</span> <span class=pl-c1>=</span> <span class=pl-c1>True</span></td>
      </tr>
      <tr>
        <td id="L949" class="blob-num js-line-number" data-line-number="949"></td>
        <td id="LC949" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Permissions Changed: &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>p_msg</span></td>
      </tr>
      <tr>
        <td id="L950" class="blob-num js-line-number" data-line-number="950"></td>
        <td id="LC950" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Permissions&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>p_msg</span>[:<span class=pl-c1>1024</span>])</td>
      </tr>
      <tr>
        <td id="L951" class="blob-num js-line-number" data-line-number="951"></td>
        <td id="LC951" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L952" class="blob-num js-line-number" data-line-number="952"></td>
        <td id="LC952" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>perp</span>:</td>
      </tr>
      <tr>
        <td id="L953" class="blob-num js-line-number" data-line-number="953"></td>
        <td id="LC953" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Updated by &quot;</span>) <span class=pl-c1>+</span> <span class=pl-en>str</span>(<span class=pl-s1>perp</span>) <span class=pl-c1>+</span> <span class=pl-s>&quot;<span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L954" class="blob-num js-line-number" data-line-number="954"></td>
        <td id="LC954" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Updated by &quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>perp</span>.<span class=pl-s1>mention</span>)</td>
      </tr>
      <tr>
        <td id="L955" class="blob-num js-line-number" data-line-number="955"></td>
        <td id="LC955" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L956" class="blob-num js-line-number" data-line-number="956"></td>
        <td id="LC956" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Reason &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>reason</span> <span class=pl-c1>+</span> <span class=pl-s>&quot;<span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L957" class="blob-num js-line-number" data-line-number="957"></td>
        <td id="LC957" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Reason &quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>reason</span>)</td>
      </tr>
      <tr>
        <td id="L958" class="blob-num js-line-number" data-line-number="958"></td>
        <td id="LC958" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>worth_updating</span>:</td>
      </tr>
      <tr>
        <td id="L959" class="blob-num js-line-number" data-line-number="959"></td>
        <td id="LC959" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L960" class="blob-num js-line-number" data-line-number="960"></td>
        <td id="LC960" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>embed_links</span>:</td>
      </tr>
      <tr>
        <td id="L961" class="blob-num js-line-number" data-line-number="961"></td>
        <td id="LC961" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>embed</span><span class=pl-c1>=</span><span class=pl-s1>embed</span>)</td>
      </tr>
      <tr>
        <td id="L962" class="blob-num js-line-number" data-line-number="962"></td>
        <td id="LC962" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L963" class="blob-num js-line-number" data-line-number="963"></td>
        <td id="LC963" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-en>escape</span>(<span class=pl-s1>msg</span>, <span class=pl-s1>mass_mentions</span><span class=pl-c1>=</span><span class=pl-c1>True</span>))</td>
      </tr>
      <tr>
        <td id="L964" class="blob-num js-line-number" data-line-number="964"></td>
        <td id="LC964" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L965" class="blob-num js-line-number" data-line-number="965"></td>
        <td id="LC965" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>async</span> <span class=pl-k>def</span> <span class=pl-en>get_role_permission_change</span>(<span class=pl-s1>self</span>, <span class=pl-s1>before</span>: <span class=pl-s1>discord</span>.<span class=pl-v>Role</span>, <span class=pl-s1>after</span>: <span class=pl-s1>discord</span>.<span class=pl-v>Role</span>) <span class=pl-c1>-&gt;</span> <span class=pl-s1>str</span>:</td>
      </tr>
      <tr>
        <td id="L966" class="blob-num js-line-number" data-line-number="966"></td>
        <td id="LC966" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>permission_list</span> <span class=pl-c1>=</span> [</td>
      </tr>
      <tr>
        <td id="L967" class="blob-num js-line-number" data-line-number="967"></td>
        <td id="LC967" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;create_instant_invite&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L968" class="blob-num js-line-number" data-line-number="968"></td>
        <td id="LC968" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;kick_members&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L969" class="blob-num js-line-number" data-line-number="969"></td>
        <td id="LC969" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;ban_members&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L970" class="blob-num js-line-number" data-line-number="970"></td>
        <td id="LC970" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;administrator&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L971" class="blob-num js-line-number" data-line-number="971"></td>
        <td id="LC971" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;manage_channels&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L972" class="blob-num js-line-number" data-line-number="972"></td>
        <td id="LC972" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;manage_guild&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L973" class="blob-num js-line-number" data-line-number="973"></td>
        <td id="LC973" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;add_reactions&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L974" class="blob-num js-line-number" data-line-number="974"></td>
        <td id="LC974" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;view_audit_log&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L975" class="blob-num js-line-number" data-line-number="975"></td>
        <td id="LC975" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;priority_speaker&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L976" class="blob-num js-line-number" data-line-number="976"></td>
        <td id="LC976" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;read_messages&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L977" class="blob-num js-line-number" data-line-number="977"></td>
        <td id="LC977" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;send_messages&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L978" class="blob-num js-line-number" data-line-number="978"></td>
        <td id="LC978" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;send_tts_messages&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L979" class="blob-num js-line-number" data-line-number="979"></td>
        <td id="LC979" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;manage_messages&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L980" class="blob-num js-line-number" data-line-number="980"></td>
        <td id="LC980" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;embed_links&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L981" class="blob-num js-line-number" data-line-number="981"></td>
        <td id="LC981" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;attach_files&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L982" class="blob-num js-line-number" data-line-number="982"></td>
        <td id="LC982" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;read_message_history&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L983" class="blob-num js-line-number" data-line-number="983"></td>
        <td id="LC983" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;mention_everyone&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L984" class="blob-num js-line-number" data-line-number="984"></td>
        <td id="LC984" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;external_emojis&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L985" class="blob-num js-line-number" data-line-number="985"></td>
        <td id="LC985" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;connect&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L986" class="blob-num js-line-number" data-line-number="986"></td>
        <td id="LC986" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;speak&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L987" class="blob-num js-line-number" data-line-number="987"></td>
        <td id="LC987" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;mute_members&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L988" class="blob-num js-line-number" data-line-number="988"></td>
        <td id="LC988" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;deafen_members&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L989" class="blob-num js-line-number" data-line-number="989"></td>
        <td id="LC989" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;move_members&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L990" class="blob-num js-line-number" data-line-number="990"></td>
        <td id="LC990" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;use_voice_activation&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L991" class="blob-num js-line-number" data-line-number="991"></td>
        <td id="LC991" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;change_nickname&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L992" class="blob-num js-line-number" data-line-number="992"></td>
        <td id="LC992" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;manage_nicknames&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L993" class="blob-num js-line-number" data-line-number="993"></td>
        <td id="LC993" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;manage_roles&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L994" class="blob-num js-line-number" data-line-number="994"></td>
        <td id="LC994" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;manage_webhooks&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L995" class="blob-num js-line-number" data-line-number="995"></td>
        <td id="LC995" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;manage_emojis&quot;</span>,</td>
      </tr>
      <tr>
        <td id="L996" class="blob-num js-line-number" data-line-number="996"></td>
        <td id="LC996" class="blob-code blob-code-inner js-file-line">        ]</td>
      </tr>
      <tr>
        <td id="L997" class="blob-num js-line-number" data-line-number="997"></td>
        <td id="LC997" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>p_msg</span> <span class=pl-c1>=</span> <span class=pl-s>&quot;&quot;</span></td>
      </tr>
      <tr>
        <td id="L998" class="blob-num js-line-number" data-line-number="998"></td>
        <td id="LC998" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>for</span> <span class=pl-s1>p</span> <span class=pl-c1>in</span> <span class=pl-s1>permission_list</span>:</td>
      </tr>
      <tr>
        <td id="L999" class="blob-num js-line-number" data-line-number="999"></td>
        <td id="LC999" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-en>getattr</span>(<span class=pl-s1>before</span>.<span class=pl-s1>permissions</span>, <span class=pl-s1>p</span>) <span class=pl-c1>!=</span> <span class=pl-en>getattr</span>(<span class=pl-s1>after</span>.<span class=pl-s1>permissions</span>, <span class=pl-s1>p</span>):</td>
      </tr>
      <tr>
        <td id="L1000" class="blob-num js-line-number" data-line-number="1000"></td>
        <td id="LC1000" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>change</span> <span class=pl-c1>=</span> <span class=pl-en>getattr</span>(<span class=pl-s1>after</span>.<span class=pl-s1>permissions</span>, <span class=pl-s1>p</span>)</td>
      </tr>
      <tr>
        <td id="L1001" class="blob-num js-line-number" data-line-number="1001"></td>
        <td id="LC1001" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>p_msg</span> <span class=pl-c1>+=</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>p</span><span class=pl-kos>}</span></span> Set to <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>change</span><span class=pl-kos>}</span></span><span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L1002" class="blob-num js-line-number" data-line-number="1002"></td>
        <td id="LC1002" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>return</span> <span class=pl-s1>p_msg</span></td>
      </tr>
      <tr>
        <td id="L1003" class="blob-num js-line-number" data-line-number="1003"></td>
        <td id="LC1003" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L1004" class="blob-num js-line-number" data-line-number="1004"></td>
        <td id="LC1004" class="blob-code blob-code-inner js-file-line">    <span class=pl-en>@<span class=pl-s1>commands</span>.<span class=pl-v>Cog</span>.<span class=pl-s1>listener</span>()</span></td>
      </tr>
      <tr>
        <td id="L1005" class="blob-num js-line-number" data-line-number="1005"></td>
        <td id="LC1005" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>async</span> <span class=pl-k>def</span> <span class=pl-en>on_guild_role_update</span>(<span class=pl-s1>self</span>, <span class=pl-s1>before</span>: <span class=pl-s1>discord</span>.<span class=pl-v>Role</span>, <span class=pl-s1>after</span>: <span class=pl-s1>discord</span>.<span class=pl-v>Role</span>) <span class=pl-c1>-&gt;</span> <span class=pl-c1>None</span>:</td>
      </tr>
      <tr>
        <td id="L1006" class="blob-num js-line-number" data-line-number="1006"></td>
        <td id="LC1006" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>guild</span> <span class=pl-c1>=</span> <span class=pl-s1>before</span>.<span class=pl-s1>guild</span></td>
      </tr>
      <tr>
        <td id="L1007" class="blob-num js-line-number" data-line-number="1007"></td>
        <td id="LC1007" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>guild</span>.<span class=pl-s1>id</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>:</td>
      </tr>
      <tr>
        <td id="L1008" class="blob-num js-line-number" data-line-number="1008"></td>
        <td id="LC1008" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1009" class="blob-num js-line-number" data-line-number="1009"></td>
        <td id="LC1009" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>version_info</span> <span class=pl-c1>&gt;=</span> <span class=pl-v>VersionInfo</span>.<span class=pl-en>from_str</span>(<span class=pl-s>&quot;3.4.0&quot;</span>):</td>
      </tr>
      <tr>
        <td id="L1010" class="blob-num js-line-number" data-line-number="1010"></td>
        <td id="LC1010" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>bot</span>.<span class=pl-en>cog_disabled_in_guild</span>(<span class=pl-s1>self</span>, <span class=pl-s1>guild</span>):</td>
      </tr>
      <tr>
        <td id="L1011" class="blob-num js-line-number" data-line-number="1011"></td>
        <td id="LC1011" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1012" class="blob-num js-line-number" data-line-number="1012"></td>
        <td id="LC1012" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;role_change&quot;</span>][<span class=pl-s>&quot;enabled&quot;</span>]:</td>
      </tr>
      <tr>
        <td id="L1013" class="blob-num js-line-number" data-line-number="1013"></td>
        <td id="LC1013" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1014" class="blob-num js-line-number" data-line-number="1014"></td>
        <td id="LC1014" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>try</span>:</td>
      </tr>
      <tr>
        <td id="L1015" class="blob-num js-line-number" data-line-number="1015"></td>
        <td id="LC1015" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>modlog_channel</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;role_change&quot;</span>)</td>
      </tr>
      <tr>
        <td id="L1016" class="blob-num js-line-number" data-line-number="1016"></td>
        <td id="LC1016" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>except</span> <span class=pl-v>RuntimeError</span>:</td>
      </tr>
      <tr>
        <td id="L1017" class="blob-num js-line-number" data-line-number="1017"></td>
        <td id="LC1017" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1018" class="blob-num js-line-number" data-line-number="1018"></td>
        <td id="LC1018" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L1019" class="blob-num js-line-number" data-line-number="1019"></td>
        <td id="LC1019" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L1020" class="blob-num js-line-number" data-line-number="1020"></td>
        <td id="LC1020" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>view_audit_log</span>:</td>
      </tr>
      <tr>
        <td id="L1021" class="blob-num js-line-number" data-line-number="1021"></td>
        <td id="LC1021" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>action</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>AuditLogAction</span>.<span class=pl-s1>role_update</span></td>
      </tr>
      <tr>
        <td id="L1022" class="blob-num js-line-number" data-line-number="1022"></td>
        <td id="LC1022" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>async</span> <span class=pl-k>for</span> <span class=pl-s1>log</span> <span class=pl-c1>in</span> <span class=pl-s1>guild</span>.<span class=pl-en>audit_logs</span>(<span class=pl-s1>limit</span><span class=pl-c1>=</span><span class=pl-c1>5</span>, <span class=pl-s1>action</span><span class=pl-c1>=</span><span class=pl-s1>action</span>):</td>
      </tr>
      <tr>
        <td id="L1023" class="blob-num js-line-number" data-line-number="1023"></td>
        <td id="LC1023" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>target</span>.<span class=pl-s1>id</span> <span class=pl-c1>==</span> <span class=pl-s1>before</span>.<span class=pl-s1>id</span>:</td>
      </tr>
      <tr>
        <td id="L1024" class="blob-num js-line-number" data-line-number="1024"></td>
        <td id="LC1024" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>user</span></td>
      </tr>
      <tr>
        <td id="L1025" class="blob-num js-line-number" data-line-number="1025"></td>
        <td id="LC1025" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L1026" class="blob-num js-line-number" data-line-number="1026"></td>
        <td id="LC1026" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span></td>
      </tr>
      <tr>
        <td id="L1027" class="blob-num js-line-number" data-line-number="1027"></td>
        <td id="LC1027" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>break</span></td>
      </tr>
      <tr>
        <td id="L1028" class="blob-num js-line-number" data-line-number="1028"></td>
        <td id="LC1028" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed_links</span> <span class=pl-c1>=</span> (</td>
      </tr>
      <tr>
        <td id="L1029" class="blob-num js-line-number" data-line-number="1029"></td>
        <td id="LC1029" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>embed_links</span></td>
      </tr>
      <tr>
        <td id="L1030" class="blob-num js-line-number" data-line-number="1030"></td>
        <td id="LC1030" class="blob-code blob-code-inner js-file-line">            <span class=pl-c1>and</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;role_change&quot;</span>][<span class=pl-s>&quot;embed&quot;</span>]</td>
      </tr>
      <tr>
        <td id="L1031" class="blob-num js-line-number" data-line-number="1031"></td>
        <td id="LC1031" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L1032" class="blob-num js-line-number" data-line-number="1032"></td>
        <td id="LC1032" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>time</span> <span class=pl-c1>=</span> <span class=pl-s1>datetime</span>.<span class=pl-s1>datetime</span>.<span class=pl-en>utcnow</span>()</td>
      </tr>
      <tr>
        <td id="L1033" class="blob-num js-line-number" data-line-number="1033"></td>
        <td id="LC1033" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>Embed</span>(<span class=pl-s1>description</span><span class=pl-c1>=</span><span class=pl-s1>after</span>.<span class=pl-s1>mention</span>, <span class=pl-s1>colour</span><span class=pl-c1>=</span><span class=pl-s1>after</span>.<span class=pl-s1>colour</span>, <span class=pl-s1>timestamp</span><span class=pl-c1>=</span><span class=pl-s1>time</span>)</td>
      </tr>
      <tr>
        <td id="L1034" class="blob-num js-line-number" data-line-number="1034"></td>
        <td id="LC1034" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>msg</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;{emoji} `{time}` Updated role **{role}**<span class=pl-cce>\n</span>&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L1035" class="blob-num js-line-number" data-line-number="1035"></td>
        <td id="LC1035" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>emoji</span><span class=pl-c1>=</span><span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;role_change&quot;</span>][<span class=pl-s>&quot;emoji&quot;</span>],</td>
      </tr>
      <tr>
        <td id="L1036" class="blob-num js-line-number" data-line-number="1036"></td>
        <td id="LC1036" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>time</span><span class=pl-c1>=</span><span class=pl-s1>time</span>.<span class=pl-en>strftime</span>(<span class=pl-s>&quot;%H:%M:%S&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L1037" class="blob-num js-line-number" data-line-number="1037"></td>
        <td id="LC1037" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>role</span><span class=pl-c1>=</span><span class=pl-s1>before</span>.<span class=pl-s1>name</span>,</td>
      </tr>
      <tr>
        <td id="L1038" class="blob-num js-line-number" data-line-number="1038"></td>
        <td id="LC1038" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L1039" class="blob-num js-line-number" data-line-number="1039"></td>
        <td id="LC1039" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>after</span> <span class=pl-c1>is</span> <span class=pl-s1>guild</span>.<span class=pl-s1>default_role</span>:</td>
      </tr>
      <tr>
        <td id="L1040" class="blob-num js-line-number" data-line-number="1040"></td>
        <td id="LC1040" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>set_author</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Updated @everyone role &quot;</span>))</td>
      </tr>
      <tr>
        <td id="L1041" class="blob-num js-line-number" data-line-number="1041"></td>
        <td id="LC1041" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L1042" class="blob-num js-line-number" data-line-number="1042"></td>
        <td id="LC1042" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>set_author</span>(</td>
      </tr>
      <tr>
        <td id="L1043" class="blob-num js-line-number" data-line-number="1043"></td>
        <td id="LC1043" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Updated {role} ({r_id}) role &quot;</span>).<span class=pl-en>format</span>(<span class=pl-s1>role</span><span class=pl-c1>=</span><span class=pl-s1>before</span>.<span class=pl-s1>name</span>, <span class=pl-s1>r_id</span><span class=pl-c1>=</span><span class=pl-s1>before</span>.<span class=pl-s1>id</span>)</td>
      </tr>
      <tr>
        <td id="L1044" class="blob-num js-line-number" data-line-number="1044"></td>
        <td id="LC1044" class="blob-code blob-code-inner js-file-line">            )</td>
      </tr>
      <tr>
        <td id="L1045" class="blob-num js-line-number" data-line-number="1045"></td>
        <td id="LC1045" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>perp</span>:</td>
      </tr>
      <tr>
        <td id="L1046" class="blob-num js-line-number" data-line-number="1046"></td>
        <td id="LC1046" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Updated by &quot;</span>) <span class=pl-c1>+</span> <span class=pl-en>str</span>(<span class=pl-s1>perp</span>) <span class=pl-c1>+</span> <span class=pl-s>&quot;<span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L1047" class="blob-num js-line-number" data-line-number="1047"></td>
        <td id="LC1047" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Updated by &quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>perp</span>.<span class=pl-s1>mention</span>)</td>
      </tr>
      <tr>
        <td id="L1048" class="blob-num js-line-number" data-line-number="1048"></td>
        <td id="LC1048" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L1049" class="blob-num js-line-number" data-line-number="1049"></td>
        <td id="LC1049" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Reason &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>reason</span> <span class=pl-c1>+</span> <span class=pl-s>&quot;<span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L1050" class="blob-num js-line-number" data-line-number="1050"></td>
        <td id="LC1050" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Reason &quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>reason</span>)</td>
      </tr>
      <tr>
        <td id="L1051" class="blob-num js-line-number" data-line-number="1051"></td>
        <td id="LC1051" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>role_updates</span> <span class=pl-c1>=</span> {</td>
      </tr>
      <tr>
        <td id="L1052" class="blob-num js-line-number" data-line-number="1052"></td>
        <td id="LC1052" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;name&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Name:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L1053" class="blob-num js-line-number" data-line-number="1053"></td>
        <td id="LC1053" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;color&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Colour:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L1054" class="blob-num js-line-number" data-line-number="1054"></td>
        <td id="LC1054" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;mentionable&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Mentionable:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L1055" class="blob-num js-line-number" data-line-number="1055"></td>
        <td id="LC1055" class="blob-code blob-code-inner js-file-line">            <span class=pl-s>&quot;hoist&quot;</span>: <span class=pl-en>_</span>(<span class=pl-s>&quot;Is Hoisted:&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L1056" class="blob-num js-line-number" data-line-number="1056"></td>
        <td id="LC1056" class="blob-code blob-code-inner js-file-line">        }</td>
      </tr>
      <tr>
        <td id="L1057" class="blob-num js-line-number" data-line-number="1057"></td>
        <td id="LC1057" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>worth_updating</span> <span class=pl-c1>=</span> <span class=pl-c1>False</span></td>
      </tr>
      <tr>
        <td id="L1058" class="blob-num js-line-number" data-line-number="1058"></td>
        <td id="LC1058" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>for</span> <span class=pl-s1>attr</span>, <span class=pl-s1>name</span> <span class=pl-c1>in</span> <span class=pl-s1>role_updates</span>.<span class=pl-en>items</span>():</td>
      </tr>
      <tr>
        <td id="L1059" class="blob-num js-line-number" data-line-number="1059"></td>
        <td id="LC1059" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>before_attr</span> <span class=pl-c1>=</span> <span class=pl-en>getattr</span>(<span class=pl-s1>before</span>, <span class=pl-s1>attr</span>)</td>
      </tr>
      <tr>
        <td id="L1060" class="blob-num js-line-number" data-line-number="1060"></td>
        <td id="LC1060" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>after_attr</span> <span class=pl-c1>=</span> <span class=pl-en>getattr</span>(<span class=pl-s1>after</span>, <span class=pl-s1>attr</span>)</td>
      </tr>
      <tr>
        <td id="L1061" class="blob-num js-line-number" data-line-number="1061"></td>
        <td id="LC1061" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-s1>before_attr</span> <span class=pl-c1>!=</span> <span class=pl-s1>after_attr</span>:</td>
      </tr>
      <tr>
        <td id="L1062" class="blob-num js-line-number" data-line-number="1062"></td>
        <td id="LC1062" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>worth_updating</span> <span class=pl-c1>=</span> <span class=pl-c1>True</span></td>
      </tr>
      <tr>
        <td id="L1063" class="blob-num js-line-number" data-line-number="1063"></td>
        <td id="LC1063" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>before_attr</span> <span class=pl-c1>==</span> <span class=pl-s>&quot;&quot;</span>:</td>
      </tr>
      <tr>
        <td id="L1064" class="blob-num js-line-number" data-line-number="1064"></td>
        <td id="LC1064" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>before_attr</span> <span class=pl-c1>=</span> <span class=pl-s>&quot;None&quot;</span></td>
      </tr>
      <tr>
        <td id="L1065" class="blob-num js-line-number" data-line-number="1065"></td>
        <td id="LC1065" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>after_attr</span> <span class=pl-c1>==</span> <span class=pl-s>&quot;&quot;</span>:</td>
      </tr>
      <tr>
        <td id="L1066" class="blob-num js-line-number" data-line-number="1066"></td>
        <td id="LC1066" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>after_attr</span> <span class=pl-c1>=</span> <span class=pl-s>&quot;None&quot;</span></td>
      </tr>
      <tr>
        <td id="L1067" class="blob-num js-line-number" data-line-number="1067"></td>
        <td id="LC1067" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Before &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>name</span><span class=pl-kos>}</span></span> <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>before_attr</span><span class=pl-kos>}</span></span><span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L1068" class="blob-num js-line-number" data-line-number="1068"></td>
        <td id="LC1068" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;After &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s>f&quot;<span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>name</span><span class=pl-kos>}</span></span> <span class=pl-s1><span class=pl-kos>{</span><span class=pl-s1>after_attr</span><span class=pl-kos>}</span></span><span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L1069" class="blob-num js-line-number" data-line-number="1069"></td>
        <td id="LC1069" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Before &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>name</span>, <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>before_attr</span>))</td>
      </tr>
      <tr>
        <td id="L1070" class="blob-num js-line-number" data-line-number="1070"></td>
        <td id="LC1070" class="blob-code blob-code-inner js-file-line">                <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;After &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>name</span>, <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-en>str</span>(<span class=pl-s1>after_attr</span>))</td>
      </tr>
      <tr>
        <td id="L1071" class="blob-num js-line-number" data-line-number="1071"></td>
        <td id="LC1071" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>p_msg</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>get_role_permission_change</span>(<span class=pl-s1>before</span>, <span class=pl-s1>after</span>)</td>
      </tr>
      <tr>
        <td id="L1072" class="blob-num js-line-number" data-line-number="1072"></td>
        <td id="LC1072" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>p_msg</span> <span class=pl-c1>!=</span> <span class=pl-s>&quot;&quot;</span>:</td>
      </tr>
      <tr>
        <td id="L1073" class="blob-num js-line-number" data-line-number="1073"></td>
        <td id="LC1073" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>worth_updating</span> <span class=pl-c1>=</span> <span class=pl-c1>True</span></td>
      </tr>
      <tr>
        <td id="L1074" class="blob-num js-line-number" data-line-number="1074"></td>
        <td id="LC1074" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Permissions Changed: &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>p_msg</span></td>
      </tr>
      <tr>
        <td id="L1075" class="blob-num js-line-number" data-line-number="1075"></td>
        <td id="LC1075" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Permissions&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>p_msg</span>[:<span class=pl-c1>1024</span>])</td>
      </tr>
      <tr>
        <td id="L1076" class="blob-num js-line-number" data-line-number="1076"></td>
        <td id="LC1076" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>worth_updating</span>:</td>
      </tr>
      <tr>
        <td id="L1077" class="blob-num js-line-number" data-line-number="1077"></td>
        <td id="LC1077" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1078" class="blob-num js-line-number" data-line-number="1078"></td>
        <td id="LC1078" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>embed_links</span>:</td>
      </tr>
      <tr>
        <td id="L1079" class="blob-num js-line-number" data-line-number="1079"></td>
        <td id="LC1079" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>embed</span><span class=pl-c1>=</span><span class=pl-s1>embed</span>)</td>
      </tr>
      <tr>
        <td id="L1080" class="blob-num js-line-number" data-line-number="1080"></td>
        <td id="LC1080" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L1081" class="blob-num js-line-number" data-line-number="1081"></td>
        <td id="LC1081" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>msg</span>)</td>
      </tr>
      <tr>
        <td id="L1082" class="blob-num js-line-number" data-line-number="1082"></td>
        <td id="LC1082" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L1083" class="blob-num js-line-number" data-line-number="1083"></td>
        <td id="LC1083" class="blob-code blob-code-inner js-file-line">    <span class=pl-en>@<span class=pl-s1>commands</span>.<span class=pl-v>Cog</span>.<span class=pl-s1>listener</span>()</span></td>
      </tr>
      <tr>
        <td id="L1084" class="blob-num js-line-number" data-line-number="1084"></td>
        <td id="LC1084" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>async</span> <span class=pl-k>def</span> <span class=pl-en>on_guild_role_create</span>(<span class=pl-s1>self</span>, <span class=pl-s1>role</span>: <span class=pl-s1>discord</span>.<span class=pl-v>Role</span>) <span class=pl-c1>-&gt;</span> <span class=pl-c1>None</span>:</td>
      </tr>
      <tr>
        <td id="L1085" class="blob-num js-line-number" data-line-number="1085"></td>
        <td id="LC1085" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>guild</span> <span class=pl-c1>=</span> <span class=pl-s1>role</span>.<span class=pl-s1>guild</span></td>
      </tr>
      <tr>
        <td id="L1086" class="blob-num js-line-number" data-line-number="1086"></td>
        <td id="LC1086" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>guild</span>.<span class=pl-s1>id</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>:</td>
      </tr>
      <tr>
        <td id="L1087" class="blob-num js-line-number" data-line-number="1087"></td>
        <td id="LC1087" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1088" class="blob-num js-line-number" data-line-number="1088"></td>
        <td id="LC1088" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>version_info</span> <span class=pl-c1>&gt;=</span> <span class=pl-v>VersionInfo</span>.<span class=pl-en>from_str</span>(<span class=pl-s>&quot;3.4.0&quot;</span>):</td>
      </tr>
      <tr>
        <td id="L1089" class="blob-num js-line-number" data-line-number="1089"></td>
        <td id="LC1089" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>bot</span>.<span class=pl-en>cog_disabled_in_guild</span>(<span class=pl-s1>self</span>, <span class=pl-s1>guild</span>):</td>
      </tr>
      <tr>
        <td id="L1090" class="blob-num js-line-number" data-line-number="1090"></td>
        <td id="LC1090" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1091" class="blob-num js-line-number" data-line-number="1091"></td>
        <td id="LC1091" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;role_create&quot;</span>][<span class=pl-s>&quot;enabled&quot;</span>]:</td>
      </tr>
      <tr>
        <td id="L1092" class="blob-num js-line-number" data-line-number="1092"></td>
        <td id="LC1092" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1093" class="blob-num js-line-number" data-line-number="1093"></td>
        <td id="LC1093" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>try</span>:</td>
      </tr>
      <tr>
        <td id="L1094" class="blob-num js-line-number" data-line-number="1094"></td>
        <td id="LC1094" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>modlog_channel</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;role_change&quot;</span>)</td>
      </tr>
      <tr>
        <td id="L1095" class="blob-num js-line-number" data-line-number="1095"></td>
        <td id="LC1095" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>except</span> <span class=pl-v>RuntimeError</span>:</td>
      </tr>
      <tr>
        <td id="L1096" class="blob-num js-line-number" data-line-number="1096"></td>
        <td id="LC1096" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1097" class="blob-num js-line-number" data-line-number="1097"></td>
        <td id="LC1097" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L1098" class="blob-num js-line-number" data-line-number="1098"></td>
        <td id="LC1098" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L1099" class="blob-num js-line-number" data-line-number="1099"></td>
        <td id="LC1099" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>view_audit_log</span>:</td>
      </tr>
      <tr>
        <td id="L1100" class="blob-num js-line-number" data-line-number="1100"></td>
        <td id="LC1100" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>action</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>AuditLogAction</span>.<span class=pl-s1>role_create</span></td>
      </tr>
      <tr>
        <td id="L1101" class="blob-num js-line-number" data-line-number="1101"></td>
        <td id="LC1101" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>async</span> <span class=pl-k>for</span> <span class=pl-s1>log</span> <span class=pl-c1>in</span> <span class=pl-s1>guild</span>.<span class=pl-en>audit_logs</span>(<span class=pl-s1>limit</span><span class=pl-c1>=</span><span class=pl-c1>5</span>, <span class=pl-s1>action</span><span class=pl-c1>=</span><span class=pl-s1>action</span>):</td>
      </tr>
      <tr>
        <td id="L1102" class="blob-num js-line-number" data-line-number="1102"></td>
        <td id="LC1102" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>target</span>.<span class=pl-s1>id</span> <span class=pl-c1>==</span> <span class=pl-s1>role</span>.<span class=pl-s1>id</span>:</td>
      </tr>
      <tr>
        <td id="L1103" class="blob-num js-line-number" data-line-number="1103"></td>
        <td id="LC1103" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>user</span></td>
      </tr>
      <tr>
        <td id="L1104" class="blob-num js-line-number" data-line-number="1104"></td>
        <td id="LC1104" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L1105" class="blob-num js-line-number" data-line-number="1105"></td>
        <td id="LC1105" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span></td>
      </tr>
      <tr>
        <td id="L1106" class="blob-num js-line-number" data-line-number="1106"></td>
        <td id="LC1106" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>break</span></td>
      </tr>
      <tr>
        <td id="L1107" class="blob-num js-line-number" data-line-number="1107"></td>
        <td id="LC1107" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed_links</span> <span class=pl-c1>=</span> (</td>
      </tr>
      <tr>
        <td id="L1108" class="blob-num js-line-number" data-line-number="1108"></td>
        <td id="LC1108" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>embed_links</span></td>
      </tr>
      <tr>
        <td id="L1109" class="blob-num js-line-number" data-line-number="1109"></td>
        <td id="LC1109" class="blob-code blob-code-inner js-file-line">            <span class=pl-c1>and</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;role_create&quot;</span>][<span class=pl-s>&quot;embed&quot;</span>]</td>
      </tr>
      <tr>
        <td id="L1110" class="blob-num js-line-number" data-line-number="1110"></td>
        <td id="LC1110" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L1111" class="blob-num js-line-number" data-line-number="1111"></td>
        <td id="LC1111" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>time</span> <span class=pl-c1>=</span> <span class=pl-s1>datetime</span>.<span class=pl-s1>datetime</span>.<span class=pl-en>utcnow</span>()</td>
      </tr>
      <tr>
        <td id="L1112" class="blob-num js-line-number" data-line-number="1112"></td>
        <td id="LC1112" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>Embed</span>(</td>
      </tr>
      <tr>
        <td id="L1113" class="blob-num js-line-number" data-line-number="1113"></td>
        <td id="LC1113" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>description</span><span class=pl-c1>=</span><span class=pl-s1>role</span>.<span class=pl-s1>mention</span>,</td>
      </tr>
      <tr>
        <td id="L1114" class="blob-num js-line-number" data-line-number="1114"></td>
        <td id="LC1114" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>colour</span><span class=pl-c1>=</span><span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>get_event_colour</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;role_create&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L1115" class="blob-num js-line-number" data-line-number="1115"></td>
        <td id="LC1115" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>timestamp</span><span class=pl-c1>=</span><span class=pl-s1>time</span>,</td>
      </tr>
      <tr>
        <td id="L1116" class="blob-num js-line-number" data-line-number="1116"></td>
        <td id="LC1116" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L1117" class="blob-num js-line-number" data-line-number="1117"></td>
        <td id="LC1117" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed</span>.<span class=pl-en>set_author</span>(</td>
      </tr>
      <tr>
        <td id="L1118" class="blob-num js-line-number" data-line-number="1118"></td>
        <td id="LC1118" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Role created {role} ({r_id})&quot;</span>).<span class=pl-en>format</span>(<span class=pl-s1>role</span><span class=pl-c1>=</span><span class=pl-s1>role</span>.<span class=pl-s1>name</span>, <span class=pl-s1>r_id</span><span class=pl-c1>=</span><span class=pl-s1>role</span>.<span class=pl-s1>id</span>)</td>
      </tr>
      <tr>
        <td id="L1119" class="blob-num js-line-number" data-line-number="1119"></td>
        <td id="LC1119" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L1120" class="blob-num js-line-number" data-line-number="1120"></td>
        <td id="LC1120" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>msg</span> <span class=pl-c1>=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;{emoji} `{time}` Role created {role}<span class=pl-cce>\n</span>&quot;</span>).<span class=pl-en>format</span>(</td>
      </tr>
      <tr>
        <td id="L1121" class="blob-num js-line-number" data-line-number="1121"></td>
        <td id="LC1121" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>emoji</span><span class=pl-c1>=</span><span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;role_create&quot;</span>][<span class=pl-s>&quot;emoji&quot;</span>],</td>
      </tr>
      <tr>
        <td id="L1122" class="blob-num js-line-number" data-line-number="1122"></td>
        <td id="LC1122" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>time</span><span class=pl-c1>=</span><span class=pl-s1>time</span>.<span class=pl-en>strftime</span>(<span class=pl-s>&quot;%H:%M:%S&quot;</span>),</td>
      </tr>
      <tr>
        <td id="L1123" class="blob-num js-line-number" data-line-number="1123"></td>
        <td id="LC1123" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>role</span><span class=pl-c1>=</span><span class=pl-s1>role</span>.<span class=pl-s1>name</span>,</td>
      </tr>
      <tr>
        <td id="L1124" class="blob-num js-line-number" data-line-number="1124"></td>
        <td id="LC1124" class="blob-code blob-code-inner js-file-line">        )</td>
      </tr>
      <tr>
        <td id="L1125" class="blob-num js-line-number" data-line-number="1125"></td>
        <td id="LC1125" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>perp</span>:</td>
      </tr>
      <tr>
        <td id="L1126" class="blob-num js-line-number" data-line-number="1126"></td>
        <td id="LC1126" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Created by&quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>perp</span>.<span class=pl-s1>mention</span>)</td>
      </tr>
      <tr>
        <td id="L1127" class="blob-num js-line-number" data-line-number="1127"></td>
        <td id="LC1127" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;By &quot;</span>) <span class=pl-c1>+</span> <span class=pl-en>str</span>(<span class=pl-s1>perp</span>) <span class=pl-c1>+</span> <span class=pl-s>&quot;<span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L1128" class="blob-num js-line-number" data-line-number="1128"></td>
        <td id="LC1128" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L1129" class="blob-num js-line-number" data-line-number="1129"></td>
        <td id="LC1129" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>msg</span> <span class=pl-c1>+=</span> <span class=pl-en>_</span>(<span class=pl-s>&quot;Reason &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>reason</span> <span class=pl-c1>+</span> <span class=pl-s>&quot;<span class=pl-cce>\n</span>&quot;</span></td>
      </tr>
      <tr>
        <td id="L1130" class="blob-num js-line-number" data-line-number="1130"></td>
        <td id="LC1130" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>embed</span>.<span class=pl-en>add_field</span>(<span class=pl-s1>name</span><span class=pl-c1>=</span><span class=pl-en>_</span>(<span class=pl-s>&quot;Reason &quot;</span>), <span class=pl-s1>value</span><span class=pl-c1>=</span><span class=pl-s1>reason</span>)</td>
      </tr>
      <tr>
        <td id="L1131" class="blob-num js-line-number" data-line-number="1131"></td>
        <td id="LC1131" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>embed_links</span>:</td>
      </tr>
      <tr>
        <td id="L1132" class="blob-num js-line-number" data-line-number="1132"></td>
        <td id="LC1132" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-s1>embed</span><span class=pl-c1>=</span><span class=pl-s1>embed</span>)</td>
      </tr>
      <tr>
        <td id="L1133" class="blob-num js-line-number" data-line-number="1133"></td>
        <td id="LC1133" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L1134" class="blob-num js-line-number" data-line-number="1134"></td>
        <td id="LC1134" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>channel</span>.<span class=pl-en>send</span>(<span class=pl-en>escape</span>(<span class=pl-s1>msg</span>, <span class=pl-s1>mass_mentions</span><span class=pl-c1>=</span><span class=pl-c1>True</span>))</td>
      </tr>
      <tr>
        <td id="L1135" class="blob-num js-line-number" data-line-number="1135"></td>
        <td id="LC1135" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L1136" class="blob-num js-line-number" data-line-number="1136"></td>
        <td id="LC1136" class="blob-code blob-code-inner js-file-line">    <span class=pl-en>@<span class=pl-s1>commands</span>.<span class=pl-v>Cog</span>.<span class=pl-s1>listener</span>()</span></td>
      </tr>
      <tr>
        <td id="L1137" class="blob-num js-line-number" data-line-number="1137"></td>
        <td id="LC1137" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>async</span> <span class=pl-k>def</span> <span class=pl-en>on_guild_role_delete</span>(<span class=pl-s1>self</span>, <span class=pl-s1>role</span>: <span class=pl-s1>discord</span>.<span class=pl-v>Role</span>) <span class=pl-c1>-&gt;</span> <span class=pl-c1>None</span>:</td>
      </tr>
      <tr>
        <td id="L1138" class="blob-num js-line-number" data-line-number="1138"></td>
        <td id="LC1138" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>guild</span> <span class=pl-c1>=</span> <span class=pl-s1>role</span>.<span class=pl-s1>guild</span></td>
      </tr>
      <tr>
        <td id="L1139" class="blob-num js-line-number" data-line-number="1139"></td>
        <td id="LC1139" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>guild</span>.<span class=pl-s1>id</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>:</td>
      </tr>
      <tr>
        <td id="L1140" class="blob-num js-line-number" data-line-number="1140"></td>
        <td id="LC1140" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1141" class="blob-num js-line-number" data-line-number="1141"></td>
        <td id="LC1141" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>version_info</span> <span class=pl-c1>&gt;=</span> <span class=pl-v>VersionInfo</span>.<span class=pl-en>from_str</span>(<span class=pl-s>&quot;3.4.0&quot;</span>):</td>
      </tr>
      <tr>
        <td id="L1142" class="blob-num js-line-number" data-line-number="1142"></td>
        <td id="LC1142" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>if</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>bot</span>.<span class=pl-en>cog_disabled_in_guild</span>(<span class=pl-s1>self</span>, <span class=pl-s1>guild</span>):</td>
      </tr>
      <tr>
        <td id="L1143" class="blob-num js-line-number" data-line-number="1143"></td>
        <td id="LC1143" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1144" class="blob-num js-line-number" data-line-number="1144"></td>
        <td id="LC1144" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-c1>not</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;role_delete&quot;</span>][<span class=pl-s>&quot;enabled&quot;</span>]:</td>
      </tr>
      <tr>
        <td id="L1145" class="blob-num js-line-number" data-line-number="1145"></td>
        <td id="LC1145" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1146" class="blob-num js-line-number" data-line-number="1146"></td>
        <td id="LC1146" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>try</span>:</td>
      </tr>
      <tr>
        <td id="L1147" class="blob-num js-line-number" data-line-number="1147"></td>
        <td id="LC1147" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-en>modlog_channel</span>(<span class=pl-s1>guild</span>, <span class=pl-s>&quot;role_change&quot;</span>)</td>
      </tr>
      <tr>
        <td id="L1148" class="blob-num js-line-number" data-line-number="1148"></td>
        <td id="LC1148" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>except</span> <span class=pl-v>RuntimeError</span>:</td>
      </tr>
      <tr>
        <td id="L1149" class="blob-num js-line-number" data-line-number="1149"></td>
        <td id="LC1149" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>return</span></td>
      </tr>
      <tr>
        <td id="L1150" class="blob-num js-line-number" data-line-number="1150"></td>
        <td id="LC1150" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L1151" class="blob-num js-line-number" data-line-number="1151"></td>
        <td id="LC1151" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-c1>None</span></td>
      </tr>
      <tr>
        <td id="L1152" class="blob-num js-line-number" data-line-number="1152"></td>
        <td id="LC1152" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>view_audit_log</span>:</td>
      </tr>
      <tr>
        <td id="L1153" class="blob-num js-line-number" data-line-number="1153"></td>
        <td id="LC1153" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>action</span> <span class=pl-c1>=</span> <span class=pl-s1>discord</span>.<span class=pl-v>AuditLogAction</span>.<span class=pl-s1>role_delete</span></td>
      </tr>
      <tr>
        <td id="L1154" class="blob-num js-line-number" data-line-number="1154"></td>
        <td id="LC1154" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>async</span> <span class=pl-k>for</span> <span class=pl-s1>log</span> <span class=pl-c1>in</span> <span class=pl-s1>guild</span>.<span class=pl-en>audit_logs</span>(<span class=pl-s1>limit</span><span class=pl-c1>=</span><span class=pl-c1>5</span>, <span class=pl-s1>action</span><span class=pl-c1>=</span><span class=pl-s1>action</span>):</td>
      </tr>
      <tr>
        <td id="L1155" class="blob-num js-line-number" data-line-number="1155"></td>
        <td id="LC1155" class="blob-code blob-code-inner js-file-line">                <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>target</span>.<span class=pl-s1>id</span> <span class=pl-c1>==</span> <span class=pl-s1>role</span>.<span class=pl-s1>id</span>:</td>
      </tr>
      <tr>
        <td id="L1156" class="blob-num js-line-number" data-line-number="1156"></td>
        <td id="LC1156" class="blob-code blob-code-inner js-file-line">                    <span class=pl-s1>perp</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>user</span></td>
      </tr>
      <tr>
        <td id="L1157" class="blob-num js-line-number" data-line-number="1157"></td>
        <td id="LC1157" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>if</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span>:</td>
      </tr>
      <tr>
        <td id="L1158" class="blob-num js-line-number" data-line-number="1158"></td>
        <td id="LC1158" class="blob-code blob-code-inner js-file-line">                        <span class=pl-s1>reason</span> <span class=pl-c1>=</span> <span class=pl-s1>log</span>.<span class=pl-s1>reason</span></td>
      </tr>
      <tr>
        <td id="L1159" class="blob-num js-line-number" data-line-number="1159"></td>
        <td id="LC1159" class="blob-code blob-code-inner js-file-line">                    <span class=pl-k>break</span></td>
      </tr>
      <tr>
        <td id="L1160" class="blob-num js-line-number" data-line-number="1160"></td>
        <td id="LC1160" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>embed_links</span> <span class=pl-c1>=</span> (</td>
      </tr>
      <tr>
        <td id="L1161" class="blob-num js-line-number" data-line-number="1161"></td>
        <td id="LC1161" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span>.<span class=pl-en>permissions_for</span>(<span class=pl-s1>guild</span>.<span class=pl-s1>me</span>).<span class=pl-s1>embed_links</span></td>
      </tr>
      <tr>
        <td id="L1162" class="blob-num js-line-number" data-line-number="1162"></td>
        <td id="LC1162" class="blob-code blob-code-inner js-file-line">            <span class=pl-c1>and</span> <span class=pl-s1>self
