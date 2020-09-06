import discord
import logging

from redbot.core import commands, checks, Config, modlog
from redbot.core.utils.chat_formatting import humanize_list
from redbot.core.i18n import Translator, cog_i18n
from typing import Union

from .eventmixin import EventMixin, CommandPrivs, EventChooser
from .settings import inv_settings


_ = Translator("ExtendedModLog", __file__)
logger = logging.getLogger("red.trusty-cogs.ExtendedModLog")


@cog_i18n(_)
class ExtendedModLog(EventMixin, commands.Cog):
    """
        Extended modlogs
        Works with core modlogset channel
    """

    __author__ = ["RePulsar", "TrustyJAID"]
    __version__ = "2.8.9"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 154457677895, force_registration=True)
        self.config.register_guild(**inv_settings)
        self.config.register_global(version="0.0.0")
        self.settings = {}
        self.loop = bot.loop.create_task(self.invite_links_loop())

    def format_help_for_context(self, ctx: commands.Context):
        """
            Thanks Sinbad!
        """
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, **kwargs):
        """
            Nothing to delete
        """
        return

    async def initialize(self) -> None:
        all_data = await self.config.all_guilds()
        for guild_id, data in all_data.items():
            guild = discord.Object(id=guild_id)
            for entry, default in inv_settings.items():
                if entry not in data:
                    all_data[guild_id][entry] = inv_settings[entry]
                if type(default) == dict:

                    for key, _default in inv_settings[entry].items():
                        if not isinstance(all_data[guild_id][entry], dict):
                            all_data[guild_id][entry] = default
                        try:
                            if key not in all_data[guild_id][entry]:
                                all_data[guild_id][entry][key] = _default
                        except TypeError:
                            # del all_data[guild_id][entry]
                            logger.error("Somehow your dict was invalid.")
                            continue
            if await self.config.version() < "2.8.5":
                logger.info("Saving all guild data to new version type")
                await self.config.guild(guild).set(all_data[guild_id])
                await self.config.version.set("2.8.5")

        self.settings = all_data

    async def modlog_settings(self, ctx: commands.Context) -> None:
        guild = ctx.message.guild
        try:
            _modlog_channel = await modlog.get_modlog_channel(guild)
            modlog_channel = _modlog_channel.mention
        except Exception:
            modlog_channel = "Not Set"
        cur_settings = {
            "message_edit": _("Message edits"),
            "message_delete": _("Message delete"),
            "user_change": _("Member changes"),
            "role_change": _("Role changes"),
            "role_create": _("Role created"),
            "role_delete": _("Role deleted"),
            "voice_change": _("Voice changes"),
            "user_join": _("User join"),
            "user_left": _("User left"),
            "channel_change": _("Channel changes"),
            "channel_create": _("Channel created"),
            "channel_delete": _("Channel deleted"),
            "guild_change": _("Guild changes"),
            "emoji_change": _("Emoji changes"),
            "commands_used": _("Mod/Admin Commands"),
            "invite_created": _("Invite created"),
            "invite_deleted": _("Invite deleted")
        }
        msg = _("Setting for {guild}\n Modlog Channel {channel}\n\n").format(
            guild=guild.name, channel=modlog_channel
        )
        if guild.id not in self.settings:
            self.settings[guild.id] = inv_settings

        data = self.settings[guild.id]
        ign_chans = data["ignored_channels"]
        ignored_channels = []
        for c in ign_chans:
            chn = guild.get_channel(c)
            if chn is None:
                # a bit of automatic cleanup so things don't break
                data["ignored_channels"].remove(c)
            else:
                ignored_channels.append(chn)
        enabled = ""
        disabled = ""
        for settings, name in cur_settings.items():
            msg += f"{name}: **{data[settings]['enabled']}**"
            if data[settings]["channel"]:
                chn = guild.get_channel(data[settings]["channel"])
                if chn is None:
                    # a bit of automatic cleanup so things don't break
                    data[settings]["channel"] = None
                else:
                    msg += f" {chn.mention}\n"
            else:
                msg += "\n"

        if enabled == "":
            enabled = _("None  ")
        if disabled == "":
            disabled = _("None  ")
        if ignored_channels:
            chans = ", ".join(c.mention for c in ignored_channels)
            msg += _("Ignored Channels") + ": " + chans
        await self.config.guild(ctx.guild).set(data)
        # save the data back to config incase we had some deleted channels
        await ctx.maybe_send_embed(msg)

    @checks.admin_or_permissions(manage_channels=True)
    @commands.group(name="modlog", aliases=["modlogtoggle", "modlogs"])
    @commands.guild_only()
    async def _modlog(self, ctx: commands.Context) -> None:
        """
            Toggle various extended modlog notifications
            Requires the channel to be setup with `[p]modlogset modlog #channel`
            Or can be sent to separate channels with `[p]modlog channel #channel event_name`
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        if await self.config.guild(ctx.message.guild).all() == {}:
            await self.config.guild(ctx.message.guild).set(inv_settings)
        if ctx.invoked_subcommand is None:
            await self.modlog_settings(ctx)

    @_modlog.command(name="colour", aliases=["color"])
    async def _set_event_colours(self, ctx: commands.Context, colour: discord.Colour, *events: EventChooser):
        """
            Set custom colours for modlog events
            `colour` must be a hex code or a [built colour.](https://discordpy.readthedocs.io/en/latest/api.html#colour)
            `event` must be one of the following options (more than one event can be provided at once.):
                `message_edit`
                `message_delete`
                `user_change`
                `role_change`
                `role_create`
                `role_delete`
                `voice_change`
                `user_join`
                `user_left`
                `channel_change`
                `channel_create`
                `channel_delete`
                `guild_change`
                `emoji_change`
                `commands_used`
                **Requires Red 3.3 and discord.py 1.3**
                `invite_created`
                `invite_deleted`
        """
        if len(events) == 0:
            return await ctx.send(_("You must provide which events should be included."))
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        if colour:
            new_colour = colour.value
        else:
            new_colour = colour
        for event in events:
            self.settings[ctx.guild.id][event]["colour"] = new_colour
            await self.config.guild(ctx.guild).set_raw(
                event, value=self.settings[ctx.guild.id][event]
            )
        await ctx.send(
            _("{event} has been set to {colour}").format(
                event=humanize_list(events), colour=str(colour)
            )
        )

    @_modlog.command(name="embeds", aliases=["embed"])
    async def _set_embds(self, ctx: commands.Context, set_to: bool, *events: EventChooser) -> None:
        """
            Set modlog events to use embeds or text
            `set_to` The desired embed setting either on or off.
            `[events...]` must be any of the following options (more than one event can be provided at once):
                `message_edit`
                `message_delete`
                `user_change`
                `role_change`
                `role_create`
                `role_delete`
                `voice_change`
                `user_join`
                `user_left`
                `channel_change`
                `channel_create`
                `channel_delete`
                `guild_change`
                `emoji_change`
                `commands_used`
                **Requires Red 3.3 and discord.py 1.3**
                `invite_created`
                `invite_deleted`
        """
        if len(events) == 0:
            return await ctx.send(_("You must provide which events should be included."))
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        for event in events:
            self.settings[ctx.guild.id][event]["embed"] = set_to
            await self.config.guild(ctx.guild).set_raw(
                event, value=self.settings[ctx.guild.id][event]
            )
        await ctx.send(
            _("{event} embed logs have been set to {set_to}").format(
                event=humanize_list(events), set_to=str(set_to)
            )
        )

    @_modlog.command(name="emojiset", send_help=True)
    @commands.bot_has_permissions(add_reactions=True)
    async def _set_event_emoji(
        self, ctx: commands.Context, emoji: Union[discord.Emoji, str], *events: EventChooser,
    ) -> None:
        """
            Set the emoji used in text modlogs.
            `new_emoji` can be any discord emoji or unicode emoji the bot has access to use.
            `[events...]` must be one of the following options (more than one event can be provided at once):
                `message_edit`
                `message_delete`
                `user_change`
                `role_change`
                `role_create`
                `role_delete`
                `voice_change`
                `user_join`
                `user_left`
                `channel_change`
                `channel_create`
                `channel_delete`
                `guild_change`
                `emoji_change`
                `commands_used`
                **Requires Red 3.3 and discord.py 1.3**
                `invite_created`
                `invite_deleted`
        """
        if len(events) == 0:
            return await ctx.send(_("You must provide which events should be included."))
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        if isinstance(emoji, str):
            try:
                await ctx.message.add_reaction(emoji)
            except discord.errors.HTTPException:
                return await ctx.send(_("{emoji} is not a valid emoji.").format(emoji=emoji))
        new_emoji = str(emoji)
        for event in events:
            self.settings[ctx.guild.id][event]["emoji"] = new_emoji
            await self.config.guild(ctx.guild).set_raw(
                event, value=self.settings[ctx.guild.id][event]
            )
        await ctx.send(
            _("{event} emoji has been set to {new_emoji}").format(
                event=humanize_list(events), new_emoji=str(new_emoji)
            )
        )

    @_modlog.command(name="toggle")
    async def _set_event_on_or_off(
        self, ctx: commands.Context, set_to: bool, *events: EventChooser,
    ) -> None:
        """
            Turn on and off specific modlog actions
            `set_to` Either on or off.
            `[events...]` must be one of the following options (more than one event can be provided at once):
                `message_edit`
                `message_delete`
                `user_change`
                `role_change`
                `role_create`
                `role_delete`
                `voice_change`
                `user_join`
                `user_left`
                `channel_change`
                `channel_create`
                `channel_delete`
                `guild_change`
                `emoji_change`
                `commands_used`
                **Requires Red 3.3 and discord.py 1.3**
                `invite_created`
                `invite_deleted`
        """
        if len(events) == 0:
            return await ctx.send(_("You must provide which events should be included."))
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        for event in events:
            self.settings[ctx.guild.id][event]["enabled"] = set_to
            await self.config.guild(ctx.guild).set_raw(
                event, value=self.settings[ctx.guild.id][event]
            )
        await ctx.send(
            _("{event} logs have been set to {set_to}").format(
                event=humanize_list(events), set_to=str(set_to)
            )
        )

    @_modlog.command(name="channel")
    async def _set_event_channel(
        self, ctx: commands.Context, channel: discord.TextChannel, *events: EventChooser,
    ) -> None:
        """
            Set the channel for modlogs.
            `channel` The text channel to send the events to.
            `[events...]` must be one of the following options (more than one event can be provided at once):
                `message_edit`
                `message_delete`
                `user_change`
                `role_change`
                `role_create`
                `role_delete`
                `voice_change`
                `user_join`
                `user_left`
                `channel_change`
                `channel_create`
                `channel_delete`
                `guild_change`
                `emoji_change`
                `commands_used`
                **Requires Red 3.3 and discord.py 1.3**
                `invite_created`
                `invite_deleted`
        """
        if len(events) == 0:
            return await ctx.send(_("You must provide which events should be included."))
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        for event in events:
            self.settings[ctx.guild.id][event]["channel"] = channel.id
            await self.config.guild(ctx.guild).set_raw(
                event, value=self.settings[ctx.guild.id][event]
            )
        await ctx.send(
            _("{event} logs have been set to {channel}").format(
                event=humanize_list(events), channel=channel.mention
            )
        )

    @_modlog.command(name="resetchannel")
    async def _reset_event_channel(
        self, ctx: commands.Context, *events: EventChooser,
    ) -> None:
        """
            Reset the modlog event to the default modlog channel.
            `[events...]` must be one of the following options (more than one event can be provided at once):
                `message_edit`
                `message_delete`
                `user_change`
                `role_change`
                `role_create`
                `role_delete`
                `voice_change`
                `user_join`
                `user_left`
                `channel_change`
                `channel_create`
                `channel_delete`
                `guild_change`
                `emoji_change`
                `commands_used`
                **Requires Red 3.3 and discord.py 1.3**
                `invite_created`
                `invite_deleted`
        """
        if len(events) == 0:
            return await ctx.send(_("You must provide which events should be included."))
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        for event in events:
            self.settings[ctx.guild.id][event]["channel"] = None
            await self.config.guild(ctx.guild).set_raw(
                event, value=self.settings[ctx.guild.id][event]
            )
        await ctx.send(
            _("{event} logs channel have been reset.").format(
                event=humanize_list(events)
            )
        )

    @_modlog.command(name="all", aliaes=["all_settings", "toggle_all"])
    async def _toggle_all_logs(self, ctx: commands.Context, set_to: bool) -> None:
        """
            Turn all logging options on or off
            `<set_to>` what to set all logging settings to must be `true`, `false`, `yes`, `no`.
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        for setting in inv_settings.keys():
            if "enabled" in self.settings[ctx.guild.id][setting]:
                self.settings[ctx.guild.id][setting]["enabled"] = set_to
        await self.config.guild(ctx.guild).set(self.settings[ctx.guild.id])
        await self.modlog_settings(ctx)

    @_modlog.command(name="botedits", aliases=["botedit"])
    async def _edit_toggle_bots(self, ctx: commands.Context) -> None:
        """
            Toggle message edit notifications for bot users
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        guild = ctx.message.guild
        msg = _("Bots edited messages ")
        if not await self.config.guild(guild).message_edit.bots():
            await self.config.guild(guild).message_edit.bots.set(True)
            self.settings[guild.id]["message_edit"]["bots"] = True
            verb = _("enabled")
        else:
            await self.config.guild(guild).message_edit.bots.set(False)
            self.settings[guild.id]["message_edit"]["bots"] = False
            verb = _("disabled")
        await ctx.send(msg + verb)

    @_modlog.command(name="botdeletes", aliases=["botdelete"])
    async def _delete_bots(self, ctx: commands.Context) -> None:
        """
            Toggle message delete notifications for bot users
            This will not affect delete notifications for messages that aren't in bot's cache.
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        guild = ctx.message.guild
        msg = _("Bot delete logs ")
        if not await self.config.guild(guild).message_delete.bots():
            await self.config.guild(guild).message_delete.bots.set(True)
            self.settings[ctx.guild.id]["message_delete"]["bots"] = True
            verb = _("enabled")
        else:
            await self.config.guild(guild).message_delete.bots.set(False)
            self.settings[ctx.guild.id]["message_delete"]["bots"] = False
            verb = _("disabled")
        await ctx.send(msg + verb)

    @_modlog.group(name="delete")
    async def _delete(self, ctx: commands.Context) -> None:
        """
            Delete logging settings
        """
        pass

    @_delete.command(name="bulkdelete")
    async def _delete_bulk_toggle(self, ctx: commands.Context) -> None:
        """
            Toggle bulk message delete notifications
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        guild = ctx.message.guild
        msg = _("Bulk message delete logs ")
        if not await self.config.guild(guild).message_delete.bulk_enabled():
            await self.config.guild(guild).message_delete.bulk_enabled.set(True)
            self.settings[ctx.guild.id]["message_delete"]["bulk_enabled"] = True
            verb = _("enabled")
        else:
            await self.config.guild(guild).message_delete.bulk_enabled.set(False)
            self.settings[ctx.guild.id]["message_delete"]["bulk_enabled"] = False
            verb = _("disabled")
        await ctx.send(msg + verb)

    @_delete.command(name="individual")
    async def _delete_bulk_individual(self, ctx: commands.Context) -> None:
        """
            Toggle individual message delete notifications for bulk message delete
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        guild = ctx.message.guild
        msg = _("Individual message delete logs for bulk message delete ")
        if not await self.config.guild(guild).message_delete.bulk_individual():
            await self.config.guild(guild).message_delete.bulk_individual.set(True)
            self.settings[ctx.guild.id]["message_delete"]["bulk_individual"] = True
            verb = _("enabled")
        else:
            await self.config.guild(guild).message_delete.bulk_individual.set(False)
            self.settings[ctx.guild.id]["message_delete"]["bulk_individual"] = False
            verb = _("disabled")
        await ctx.send(msg + verb)

    @_delete.command(name="cachedonly")
    async def _delete_cachedonly(self, ctx: commands.Context) -> None:
        """
            Toggle message delete notifications for non-cached messages
            Delete notifications for non-cached messages
            will only show channel info without content of deleted message or its author.
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        guild = ctx.message.guild
        msg = _("Delete logs for non-cached messages ")
        if not await self.config.guild(guild).message_delete.cached_only():
            await self.config.guild(guild).message_delete.cached_only.set(True)
            self.settings[ctx.guild.id]["message_delete"]["cached_only"] = True
            verb = _("disabled")
        else:
            await self.config.guild(guild).message_delete.cached_only.set(False)
            self.settings[ctx.guild.id]["message_delete"]["cached_only"] = False
            verb = _("enabled")
        await ctx.send(msg + verb)

    @_modlog.command(name="botchange")
    async def _user_bot_logging(self, ctx: commands.Context) -> None:
        """
            Toggle bots from being logged in user updates
            This includes roles and nickname.
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        setting = self.settings[ctx.guild.id]["user_change"]["bots"]
        self.settings[ctx.guild.id]["user_change"]["bots"] = not setting
        await self.config.guild(ctx.guild).user_change.bots.set(not setting)
        if setting:
            await ctx.send(_("Bots will no longer be tracked in user change logs."))
        else:
            await ctx.send(_("Bots will be tracked in user change logs."))

    @_modlog.command(name="nickname", aliases=["nicknames"])
    async def _user_nickname_logging(self, ctx: commands.Context) -> None:
        """
            Toggle nickname updates for user changes
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        setting = self.settings[ctx.guild.id]["user_change"]["nicknames"]
        self.settings[ctx.guild.id]["user_change"]["nicknames"] = not setting
        await self.config.guild(ctx.guild).user_change.nicknames.set(not setting)
        if setting:
            await ctx.send(_("Nicknames will no longer be tracked in user change logs."))
        else:
            await ctx.send(_("Nicknames will be tracked in user change logs."))

    @_modlog.command(name="commandlevel", aliases=["commandslevel"])
    async def _command_level(self, ctx: commands.Context, *level: CommandPrivs) -> None:
        """
            Set the level of commands to be logged
            `[level...]` must include all levels you want from:
            MOD, ADMIN, BOT_OWNER, GUILD_OWNER, and NONE
            These are the basic levels commands check for in permissions.
            `NONE` is a command anyone has permission to use, where as `MOD`
            can be `mod or permissions`
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        if len(level) == 0:
            return await ctx.send_help()
        guild = ctx.message.guild
        msg = _("Command logs set to: ")
        await self.config.guild(guild).commands_used.privs.set(list(level))
        self.settings[ctx.guild.id]["commands_used"]["privs"] = list(level)
        await ctx.send(msg + humanize_list(level))

    @_modlog.command()
    async def ignore(
        self,
        ctx: commands.Context,
        channel: Union[discord.TextChannel, discord.CategoryChannel, discord.VoiceChannel],
    ) -> None:
        """
            Ignore a channel from message delete/edit events and bot commands
            `channel` the channel or category to ignore events in
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        guild = ctx.message.guild
        if channel is None:
            channel = ctx.channel
        cur_ignored = await self.config.guild(guild).ignored_channels()
        if channel.id not in cur_ignored:
            cur_ignored.append(channel.id)
            await self.config.guild(guild).ignored_channels.set(cur_ignored)
            self.settings[guild.id]["ignored_channels"] = cur_ignored
            await ctx.send(_(" Now ignoring events in ") + channel.mention)
        else:
            await ctx.send(channel.mention + _(" is already being ignored."))

    @_modlog.command()
    async def unignore(
        self,
        ctx: commands.Context,
        channel: Union[discord.TextChannel, discord.CategoryChannel, discord.VoiceChannel],
    ) -> None:
        """
            Unignore a channel from message delete/edit events and bot commands
            `channel` the channel to unignore message delete/edit events
        """
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = inv_settings
        guild = ctx.message.guild
        if channel is None:
            channel = ctx.channel
        cur_ignored = await self.config.guild(guild).ignored_channels()
        if channel.id in cur_ignored:
            cur_ignored.remove(channel.id)
            await self.config.guild(guild).ignored_channels.set(cur_ignored)
            self.settings[guild.id]["ignored_channels"] = cur_ignored
            await ctx.send(_(" Now tracking events in ") + channel.mention)
        else:
            await ctx.send(channel.mention + _(" is not being ignored."))

    def __unload(self):
        self.loop.cancel()42" class="blob-code blob-code-inner js-file-line"><span class=pl-s></span></td>
      </tr>
      <tr>
        <td id="L643" class="blob-num js-line-number" data-line-number="643"></td>
        <td id="LC643" class="blob-code blob-code-inner js-file-line"><span class=pl-s>            `channel` the channel to unignore message delete/edit events</span></td>
      </tr>
      <tr>
        <td id="L644" class="blob-num js-line-number" data-line-number="644"></td>
        <td id="LC644" class="blob-code blob-code-inner js-file-line"><span class=pl-s>        &quot;&quot;&quot;</span></td>
      </tr>
      <tr>
        <td id="L645" class="blob-num js-line-number" data-line-number="645"></td>
        <td id="LC645" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>ctx</span>.<span class=pl-s1>guild</span>.<span class=pl-s1>id</span> <span class=pl-c1>not</span> <span class=pl-c1>in</span> <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>:</td>
      </tr>
      <tr>
        <td id="L646" class="blob-num js-line-number" data-line-number="646"></td>
        <td id="LC646" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>ctx</span>.<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>] <span class=pl-c1>=</span> <span class=pl-s1>inv_settings</span></td>
      </tr>
      <tr>
        <td id="L647" class="blob-num js-line-number" data-line-number="647"></td>
        <td id="LC647" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>guild</span> <span class=pl-c1>=</span> <span class=pl-s1>ctx</span>.<span class=pl-s1>message</span>.<span class=pl-s1>guild</span></td>
      </tr>
      <tr>
        <td id="L648" class="blob-num js-line-number" data-line-number="648"></td>
        <td id="LC648" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>channel</span> <span class=pl-c1>is</span> <span class=pl-c1>None</span>:</td>
      </tr>
      <tr>
        <td id="L649" class="blob-num js-line-number" data-line-number="649"></td>
        <td id="LC649" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>channel</span> <span class=pl-c1>=</span> <span class=pl-s1>ctx</span>.<span class=pl-s1>channel</span></td>
      </tr>
      <tr>
        <td id="L650" class="blob-num js-line-number" data-line-number="650"></td>
        <td id="LC650" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>cur_ignored</span> <span class=pl-c1>=</span> <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>config</span>.<span class=pl-en>guild</span>(<span class=pl-s1>guild</span>).<span class=pl-en>ignored_channels</span>()</td>
      </tr>
      <tr>
        <td id="L651" class="blob-num js-line-number" data-line-number="651"></td>
        <td id="LC651" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>if</span> <span class=pl-s1>channel</span>.<span class=pl-s1>id</span> <span class=pl-c1>in</span> <span class=pl-s1>cur_ignored</span>:</td>
      </tr>
      <tr>
        <td id="L652" class="blob-num js-line-number" data-line-number="652"></td>
        <td id="LC652" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>cur_ignored</span>.<span class=pl-en>remove</span>(<span class=pl-s1>channel</span>.<span class=pl-s1>id</span>)</td>
      </tr>
      <tr>
        <td id="L653" class="blob-num js-line-number" data-line-number="653"></td>
        <td id="LC653" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>self</span>.<span class=pl-s1>config</span>.<span class=pl-en>guild</span>(<span class=pl-s1>guild</span>).<span class=pl-s1>ignored_channels</span>.<span class=pl-en>set</span>(<span class=pl-s1>cur_ignored</span>)</td>
      </tr>
      <tr>
        <td id="L654" class="blob-num js-line-number" data-line-number="654"></td>
        <td id="LC654" class="blob-code blob-code-inner js-file-line">            <span class=pl-s1>self</span>.<span class=pl-s1>settings</span>[<span class=pl-s1>guild</span>.<span class=pl-s1>id</span>][<span class=pl-s>&quot;ignored_channels&quot;</span>] <span class=pl-c1>=</span> <span class=pl-s1>cur_ignored</span></td>
      </tr>
      <tr>
        <td id="L655" class="blob-num js-line-number" data-line-number="655"></td>
        <td id="LC655" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>ctx</span>.<span class=pl-en>send</span>(<span class=pl-en>_</span>(<span class=pl-s>&quot; Now tracking events in &quot;</span>) <span class=pl-c1>+</span> <span class=pl-s1>channel</span>.<span class=pl-s1>mention</span>)</td>
      </tr>
      <tr>
        <td id="L656" class="blob-num js-line-number" data-line-number="656"></td>
        <td id="LC656" class="blob-code blob-code-inner js-file-line">        <span class=pl-k>else</span>:</td>
      </tr>
      <tr>
        <td id="L657" class="blob-num js-line-number" data-line-number="657"></td>
        <td id="LC657" class="blob-code blob-code-inner js-file-line">            <span class=pl-k>await</span> <span class=pl-s1>ctx</span>.<span class=pl-en>send</span>(<span class=pl-s1>channel</span>.<span class=pl-s1>mention</span> <span class=pl-c1>+</span> <span class=pl-en>_</span>(<span class=pl-s>&quot; is not being ignored.&quot;</span>))</td>
      </tr>
      <tr>
        <td id="L658" class="blob-num js-line-number" data-line-number="658"></td>
        <td id="LC658" class="blob-code blob-code-inner js-file-line">
</td>
      </tr>
      <tr>
        <td id="L659" class="blob-num js-line-number" data-line-number="659"></td>
        <td id="LC659" class="blob-code blob-code-inner js-file-line">    <span class=pl-k>def</span> <span class=pl-en>__unload</span>(<span class=pl-s1>self</span>):</td>
      </tr>
      <tr>
        <td id="L660" class="blob-num js-line-number" data-line-number="660"></td>
        <td id="LC660" class="blob-code blob-code-inner js-file-line">        <span class=pl-s1>self</span>.<span class=pl-s1>loop</span>.<span class=pl-en>cancel</span>()</td>
      </tr>
</table>

  <details class="details-reset details-overlay BlobToolbar position-absolute js-file-line-actions dropdown d-none" aria-hidden="true">
    <summary class="btn-octicon ml-0 px-2 p-0 bg-white border border-gray-dark rounded-1" aria-label="Inline file action toolbar">
      <svg class="octicon octicon-kebab-horizontal" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true"><path d="M8 9a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM1.5 9a1.5 1.5 0 100-3 1.5 1.5 0 000 3zm13 0a1.5 1.5 0 100-3 1.5 1.5 0 000 3z"></path></svg>
    </summary>
    <details-menu>
      <ul class="BlobToolbar-dropdown dropdown-menu dropdown-menu-se mt-2" style="width:185px">
        <li>
          <clipboard-copy role="menuitem" class="dropdown-item" id="js-copy-lines" style="cursor:pointer;">
            Copy lines
          </clipboard-copy>
        </li>
        <li>
          <clipboard-copy role="menuitem" class="dropdown-item" id="js-copy-permalink" style="cursor:pointer;">
            Copy permalink
          </clipboard-copy>
        </li>
        <li><a class="dropdown-item js-update-url-with-hash" id="js-view-git-blame" role="menuitem" href="/duanegtr/tltrusty/blame/9465fe0a7820abd293a87871a433b7415cac7bdf/extendedmodlog/extendedmodlog.py">View git blame</a></li>
      </ul>
    </details-menu>
  </details>

  </div>

    </div>

  


  <details class="details-reset details-overlay details-overlay-dark" id="jumpto-line-details-dialog">
    <summary data-hotkey="l" aria-label="Jump to line"></summary>
    <details-dialog class="Box Box--overlay d-flex flex-column anim-fade-in fast linejump" aria-label="Jump to line">
      <!-- '"` --><!-- </textarea></xmp> --></option></form><form class="js-jump-to-line-form Box-body d-flex" action="" accept-charset="UTF-8" method="get">
        <input class="form-control flex-auto mr-3 linejump-input js-jump-to-line-field" type="text" placeholder="Jump to line&hellip;" aria-label="Jump to line" autofocus>
        <button type="submit" class="btn" data-close-dialog>Go</button>
</form>    </details-dialog>
  </details>

    <div class="Popover anim-scale-in js-tagsearch-popover"
     hidden
     data-tagsearch-url="/duanegtr/tltrusty/find-definition"
     data-tagsearch-ref="master"
     data-tagsearch-path="extendedmodlog/extendedmodlog.py"
     data-tagsearch-lang="Python"
     data-hydro-click="{&quot;event_type&quot;:&quot;code_navigation.click_on_symbol&quot;,&quot;payload&quot;:{&quot;action&quot;:&quot;click_on_symbol&quot;,&quot;repository_id&quot;:293222138,&quot;ref&quot;:&quot;master&quot;,&quot;language&quot;:&quot;Python&quot;,&quot;originating_url&quot;:&quot;https://github.com/duanegtr/tltrusty/blob/master/extendedmodlog/extendedmodlog.py&quot;,&quot;user_id&quot;:61340105}}"
     data-hydro-click-hmac="f7f6b98cbbdedd04ead1f9756b9f1256ecadc88c84666518bd6b719efc048a3e">
  <div class="Popover-message Popover-message--large Popover-message--top-left TagsearchPopover mt-1 mb-4 mx-auto Box box-shadow-large">
    <div class="TagsearchPopover-content js-tagsearch-popover-content overflow-auto" style="will-change:transform;">
    </div>
  </div>
</div>




  </div>
</div>

    </main>
  </div>

  </div>

        
<div class="footer container-xl width-full p-responsive" role="contentinfo">
  <div class="position-relative d-flex flex-row-reverse flex-lg-row flex-wrap flex-lg-nowrap flex-justify-center flex-lg-justify-between pt-6 pb-2 mt-6 f6 text-gray border-top border-gray-light ">
    <ul class="list-style-none d-flex flex-wrap col-12 col-lg-5 flex-justify-center flex-lg-justify-between mb-2 mb-lg-0">
      <li class="mr-3 mr-lg-0">&copy; 2020 GitHub, Inc.</li>
        <li class="mr-3 mr-lg-0"><a data-ga-click="Footer, go to terms, text:terms" href="https://github.com/site/terms">Terms</a></li>
        <li class="mr-3 mr-lg-0"><a data-ga-click="Footer, go to privacy, text:privacy" href="https://github.com/site/privacy">Privacy</a></li>
        <li class="mr-3 mr-lg-0"><a data-ga-click="Footer, go to security, text:security" href="https://github.com/security">Security</a></li>
        <li class="mr-3 mr-lg-0"><a href="https://githubstatus.com/" data-ga-click="Footer, go to status, text:status">Status</a></li>
        <li><a data-ga-click="Footer, go to help, text:help" href="https://docs.github.com">Help</a></li>

    </ul>

    <a aria-label="Homepage" title="GitHub" class="footer-octicon d-none d-lg-block mx-lg-4" href="https://github.com">
      <svg height="24" class="octicon octicon-mark-github" viewBox="0 0 16 16" version="1.1" width="24" aria-hidden="true"><path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>
</a>
   <ul class="list-style-none d-flex flex-wrap col-12 col-lg-5 flex-justify-center flex-lg-justify-between mb-2 mb-lg-0">
        <li class="mr-3 mr-lg-0"><a data-ga-click="Footer, go to contact, text:contact" href="https://github.com/contact">Contact GitHub</a></li>
        <li class="mr-3 mr-lg-0"><a href="https://github.com/pricing" data-ga-click="Footer, go to Pricing, text:Pricing">Pricing</a></li>
      <li class="mr-3 mr-lg-0"><a href="https://docs.github.com" data-ga-click="Footer, go to api, text:api">API</a></li>
      <li class="mr-3 mr-lg-0"><a href="https://services.github.com" data-ga-click="Footer, go to training, text:training">Training</a></li>
        <li class="mr-3 mr-lg-0"><a href="https://github.blog" data-ga-click="Footer, go to blog, text:blog">Blog</a></li>
        <li><a data-ga-click="Footer, go to about, text:about" href="https://github.com/about">About</a></li>
    </ul>
  </div>
  <div class="d-flex flex-justify-center pb-6">
    <span class="f6 text-gray-light"></span>
  </div>
</div>



  <div id="ajax-error-message" class="ajax-error-message flash flash-error">
    <svg class="octicon octicon-alert" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true"><path fill-rule="evenodd" d="M8.22 1.754a.25.25 0 00-.44 0L1.698 13.132a.25.25 0 00.22.368h12.164a.25.25 0 00.22-.368L8.22 1.754zm-1.763-.707c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0114.082 15H1.918a1.75 1.75 0 01-1.543-2.575L6.457 1.047zM9 11a1 1 0 11-2 0 1 1 0 012 0zm-.25-5.25a.75.75 0 00-1.5 0v2.5a.75.75 0 001.5 0v-2.5z"></path></svg>
    <button type="button" class="flash-close js-ajax-error-dismiss" aria-label="Dismiss error">
      <svg class="octicon octicon-x" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true"><path fill-rule="evenodd" d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 01-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z"></path></svg>
    </button>
    You can’t perform that action at this time.
  </div>


    <script crossorigin="anonymous" async="async" integrity="sha512-bn/3rKJzBl2H64K38R8KaVcT26vKK7BJQC59lwYc+9fjlHzmy0fwh+hzBtsgTdhIi13dxjzNKWhdSN8WTM9qUw==" type="application/javascript" id="js-conditional-compat" data-src="https://github.githubassets.com/assets/compat-bootstrap-6e7ff7ac.js"></script>
    <script crossorigin="anonymous" integrity="sha512-CxjaMepCmi+z0LTeztU2S8qGD25LyHD6j9t0RSPevy63trFWJVwUM6ipAVLgtpMBBgZ53wq8JPkSeQ6ruaZL2w==" type="application/javascript" src="https://github.githubassets.com/assets/environment-bootstrap-0b18da31.js"></script>
    <script crossorigin="anonymous" async="async" integrity="sha512-0iFuD53Djy/XZAyvqoEIC7zd0eAUgPgftnE6yDTV+Gme6rmZsIlqEI5m56nc2Ixyvc8ssQv78V3wicOJPW3snQ==" type="application/javascript" src="https://github.githubassets.com/assets/vendor-d2216e0f.js"></script>
    <script crossorigin="anonymous" async="async" integrity="sha512-cI+iNNYxkqpDGV8Rui9ouSfFLhI6a/qURXvV8tK1LPu8Ni1tYwJpUSgX6bM1psf5b2YUuhkmyqaWuxzS8m3qtQ==" type="application/javascript" src="https://github.githubassets.com/assets/frameworks-708fa234.js"></script>
    
    <script crossorigin="anonymous" async="async" integrity="sha512-CNroxNfy/sSm19XW3hVvtu9w1gQPr27RegkaFEjXOuehR/1UXv33/Ev89R7Kn8av4FjGT+akvqqciARZJAWErQ==" type="application/javascript" src="https://github.githubassets.com/assets/behaviors-bootstrap-08dae8c4.js"></script>
    
      <script crossorigin="anonymous" async="async" integrity="sha512-NqTqgekwk460TqY5fnqcpQSWPHLK1qsbqM7LJI5BqHR6pm1rYOIUnuqP6w3s6EpoiNdh/YRo7amc5UDIRPF27A==" type="application/javascript" data-module-id="./contributions-spider-graph.js" data-src="https://github.githubassets.com/assets/contributions-spider-graph-36a4ea81.js"></script>
      <script crossorigin="anonymous" async="async" integrity="sha512-rX/efcwdoSNLAclubTNEJumykN9y6jxJ67d9t5HdgpyLlKHsKfVf1AHFLD5M+8NaP5ndpQJQ4gGDilVrpEHbfQ==" type="application/javascript" data-module-id="./drag-drop.js" data-src="https://github.githubassets.com/assets/drag-drop-ad7fde7d.js"></script>
      <script crossorigin="anonymous" async="async" integrity="sha512-iLuC2weaJqL9mYAud2WDWjhd8cJe8dXVxw2KhCH2Rnj6WJvTzlZRmvTtL09wNWX6nRze/TDaQ7gq7BFLchaDYg==" type="application/javascript" data-module-id="./image-crop-element-loader.js" data-src="https://github.githubassets.com/assets/image-crop-element-loader-88bb82db.js"></script>
      <script crossorigin="anonymous" async="async" integrity="sha512-QCuZvSssZHjgPkecs0OO0wA6748zjgY+CIWgc4awUkoaN30LxvwbTD5o/jmUDpz2W8l8ASv6VsznbFcoaiNm8Q==" type="application/javascript" data-module-id="./jump-to.js" data-src="https://github.githubassets.com/assets/jump-to-402b99bd.js"></script>
      <script crossorigin="anonymous" async="async" integrity="sha512-HzWUeLy0p20M4Lc3+EerTwy/VaH3vMuKLvhFJr0PsJfKXnsD9oy5SfashhxStUirglhYZUB4fLYQRM1uzrFyNg==" type="application/javascript" data-module-id="./profile-pins-element.js" data-src="https://github.githubassets.com/assets/profile-pins-element-1f359478.js"></script>
      <script crossorigin="anonymous" async="async" integrity="sha512-qECv/jhsvLFN77eGNu0cjMR2+zvAlLyhQVTnmayJc5OLZoxMLjQZxZW1hK/dhcYro6Wec/aiF21HYf2N5OilYQ==" type="application/javascript" data-module-id="./randomColor.js" data-src="https://github.githubassets.com/assets/randomColor-a840affe.js"></script>
      <script crossorigin="anonymous" async="async" integrity="sha512-vK7rRnsAi4qcmC2HqCfPyEBZgIMWb6Azyb1PJxgL1FtEFMydK//dsnuLdVx+RaPGg71Z58ossFXqkLWgMevvdw==" type="application/javascript" data-module-id="./sortable-behavior.js" data-src="https://github.githubassets.com/assets/sortable-behavior-bcaeeb46.js"></script>
      <script crossorigin="anonymous" async="async" integrity="sha512-mHqsE5aQq7fAmmLd0epHBJK8rn8DOVnjW2YQOT8wvsN1oLrypw0cDFmwXPDwbMghHyo4kKiOtVJ/kEsEzwwibw==" type="application/javascript" data-module-id="./tweetsodium.js" data-src="https://github.githubassets.com/assets/tweetsodium-987aac13.js"></script>
      <script crossorigin="anonymous" async="async" integrity="sha512-64NrdGoMwn8rfUeO96KKyLg7IBjky08csy2744g8171VK6RtKaXQgjEDLxktmgoepKjK+8AuUyLTCQsu2Z1rfA==" type="application/javascript" data-module-id="./user-status-submit.js" data-src="https://github.githubassets.com/assets/user-status-submit-eb836b74.js"></script>
    
    <script crossorigin="anonymous" async="async" integrity="sha512-3ZM/Zfp0tTvefB9GGsqCPGWByIEgp9Kfz7zOq4TK/DgQBs7SWdBtLfvem9F5dH+TrZ3o9h1+7c8jyAkqb61UMw==" type="application/javascript" src="https://github.githubassets.com/assets/repositories-dd933f65.js"></script>
<script crossorigin="anonymous" async="async" integrity="sha512-g7kJtGog/arl2FcMYjpQ96dSinG2snUOeV6psKXQQQPZ8x/0VPpEUb4GvR89O7uQOy1yhYVXBA6lEvLzOSlb5A==" type="application/javascript" src="https://github.githubassets.com/assets/github-bootstrap-83b909b4.js"></script>
  <div class="js-stale-session-flash flash flash-warn flash-banner" hidden
    >
    <svg class="octicon octicon-alert" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true"><path fill-rule="evenodd" d="M8.22 1.754a.25.25 0 00-.44 0L1.698 13.132a.25.25 0 00.22.368h12.164a.25.25 0 00.22-.368L8.22 1.754zm-1.763-.707c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0114.082 15H1.918a1.75 1.75 0 01-1.543-2.575L6.457 1.047zM9 11a1 1 0 11-2 0 1 1 0 012 0zm-.25-5.25a.75.75 0 00-1.5 0v2.5a.75.75 0 001.5 0v-2.5z"></path></svg>
    <span class="js-stale-session-flash-signed-in" hidden>You signed in with another tab or window. <a href="">Reload</a> to refresh your session.</span>
    <span class="js-stale-session-flash-signed-out" hidden>You signed out in another tab or window. <a href="">Reload</a> to refresh your session.</span>
  </div>
  <template id="site-details-dialog">
  <details class="details-reset details-overlay details-overlay-dark lh-default text-gray-dark hx_rsm" open>
    <summary role="button" aria-label="Close dialog"></summary>
    <details-dialog class="Box Box--overlay d-flex flex-column anim-fade-in fast hx_rsm-dialog hx_rsm-modal">
      <button class="Box-btn-octicon m-0 btn-octicon position-absolute right-0 top-0" type="button" aria-label="Close dialog" data-close-dialog>
        <svg class="octicon octicon-x" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true"><path fill-rule="evenodd" d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 01-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z"></path></svg>
      </button>
      <div class="octocat-spinner my-6 js-details-dialog-spinner"></div>
    </details-dialog>
  </details>
</template>

  <div class="Popover js-hovercard-content position-absolute" style="display: none; outline: none;" tabindex="0">
  <div class="Popover-message Popover-message--bottom-left Popover-message--large Box box-shadow-large" style="width:360px;">
  </div>
</div>


  </body>
</html>

