import discord
from discord.errors import InvalidArgument
from redbot.core import commands, Config, checks
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

class NonNitroEmoji(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=3454353423)
        default_global = {'data': {'guild_id': 599090817704919041}}
        self.config.register_global(**default_global)
    @commands.Cog.listener()
    async def on_message(self, message):
        found_webhook = False
        found_emoji = False
        message_list = message.content.split()
        message_to_send_list = []
        for word in message_list:
            if word == <@740599379290882059> and message.author.id == 868306756638478376:
                return await message.delete()
            if word.startswith(":") and word.endswith(":") and not(message.author.bot):
                emoji_name = word[1:len(word)-1]
                for emoji in self.bot.emojis:
                    if emoji.name.lower() == emoji_name.lower() and emoji.available:
                        found_emoji = True
                        message_to_send_list.append(str(emoji))
                        break
            else:
                message_to_send_list.append(word)
        if found_emoji:
            message_to_send = " ".join(message_to_send_list)
            webhooks = await message.channel.webhooks()
            for webhook in webhooks:
                if webhook.name == "bot_emoji":
                    webhook_to_send = webhook
                    found_webhook = True
                    break
            if not(found_webhook):
                webhook_to_send = await message.channel.create_webhook(name="bot_emoji", reason="from nonitro cog")
            await webhook_to_send.send(message_to_send, username=message.author.display_name, avatar_url=message.author.avatar_url)
            await message.delete()
        
    @commands.command(name="addemoji")
    async def add_emoji(self, ctx, name:str):
        async with self.config.data() as data:
            guild_to_upload = self.bot.get_guild(data['guild_id'])
            if not ctx.message.attachments:
                return await ctx.send("No Image uploaded")
            try:
                img = await ctx.message.attachments[0].read()
            except:
                return await ctx.send("Invalid image format") # Not sure about how attachements work on discord
            try:
                await guild_to_upload.create_custom_emoji(name=name, image=img)
                await ctx.send("Emoji created")
            except InvalidArgument:
                return await ctx.send("Invalid image format")
            except discord.HTTPException:
                return await ctx.send("Please ask the devs to create a new guild")
    @checks.is_owner()
    @commands.command(name="emojiguild")
    async def change_guild(self, ctx, new_guild_id:int):
        async with self.config.data() as data:
            guild = self.bot.get_guild(int(new_guild_id))
            if guild is None:
                await ctx.send("Invalid Guild ID")
            else:
                data['guild_id'] = new_guild_id
                await ctx.send("Guild ID changed")

    @commands.command(name="listemojis")
    async def list_emojis(self, ctx):
        """
        List the emojis available to use
        """
        embed_list = []
        to_append = ""
        for count, emoji in enumerate(self.bot.emojis, start=1):
            if emoji.available:
                to_append += f"{emoji} \u200b \u200b \u200b \u200b {emoji.name}\n"
            else:
                continue
            if count % 10 == 0:
                embed = discord.Embed(
                    color=0xFAA61A, description=to_append)
                embed.set_author(name="List of emojis available",
                                 icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
                embed.set_footer(text="By Kingslayer | Legend Gaming",
                             icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
                embed_list.append(embed)
                to_append = ""
        if len(to_append) == 0:
            pass
        else:
            embed = discord.Embed(color=0xFAA61A, description=to_append)
            embed.set_author(name="List of emojis available")
            embed.set_footer(text="By Kingslayer | Legend Gaming",
                             icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
            embed_list.append(embed)

        await menu(ctx, embed_list, controls=DEFAULT_CONTROLS)

    @commands.command(name="emojihow")
    async def how_to_use(self, ctx):
            await ctx.send("Send animated emotes/emotes from other servers the bot is on by putting your name between two colons.\nSample usage`:name_of_emoji:`\nGet list of emojis available by using `!listemojis`")
