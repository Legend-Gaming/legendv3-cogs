from redbot.core import commands, Config, checks
from redbot.core.utils import predicates
import asyncio
import os
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException
import re
import shutil
import discord


class InvalidPath(Exception):
    pass


class InvalidBrowser(Exception):
    pass


class NoBrowser(Exception):
    pass


def valid_file(path):
    return path is not None and os.path.exists(path) and os.path.isfile(path)


class Cleverbotcog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.browser = None
        self.config = Config.get_conf(self, identifier=2403650443, force_registration=True)
        self.default_global = {
            "firefox": {
                "executable": None,
                "webdriver": None
                },
            "chrome": {
                "executable": None,
                "webdriver": None
                },
        }
        self.default_guild = {
            "autoconnect": False,
            "wait_time": 2,
            "browser_name": "chrome",
        }
        self.config.register_global(**self.default_global)
        self.config.register_guild(**self.default_guild)
        self.url = 'https://www.cleverbot.com'
        self.input_field = 'None'
        self.count = -1
        self.processing = False
        self.browser_name = None
        self.wait_time = None

    def __del__(self):
        if self.browser is not None:
            self.browser.quit()
            self.browser = None

    @commands.group()
    async def cleverbot(self, ctx):
        """ Mock cleverbot API using headless firefox or chrome. """
        pass

    # Use discord.Message.clean_content instead of sanitize_msg
    # async def sanitize_msg(self, message):
    #     for match in re.findall('<[^>]+>', message):
    #         # Discord represents custom emote as <:name:tag> and tag as <@!:id> which looks like
    #         # HTML to cleverbot
    #         custom_emote_pattern = "<:[a-zA-Z0-9]+:[0-9]+>"
    #         user_tag_pattern = "<@!?([0-9]+)"
    #         role_tag_pattern = ""
    #         if re.match(custom_emote_pattern, match):
    #             message = re.sub(custom_emote_pattern, "", message)
    #             continue
    #         # Check if a user was tagged. Replace user tag with username
    #         tag = re.match(user_tag_pattern, match)
    #         if tag:
    #             user_tag = tag.group(1)
    #             user = self.bot.get_user(int(user_tag))
    #             if user is not None:
    #                 message = re.sub("<@!?{}".format(user_tag), user.name, message)
    #             continue

    async def getreply(self, message: str, guild) -> str:
        """ Get reply based on message.
            This is the main function; it connects to browser and url if autoconnect is enabled,
            cleans input, posts it and returns response
        """
        if not self.browser_name or not self.wait_time:
            self.browser_name = await self.config.guild(guild).browser_name()
            self.wait_time = await self.config.guild(guild).wait_time()

        if self.browser is None:
            autoconnect = await self.config.guild(guild).autoconnect()
            if autoconnect:
                try:
                    settings = await self.config.get_raw(self.browser_name)
                    await self.initialize_browser(self.browser_name, settings)
                    self.browser.get(self.url)  # Loads url
                except InvalidPath:
                    return "Path to webdriver is not set. Set path using [p]setcleverbot <browser> webdriver <path>"
            else:
                return "Browser is not running. Try running [p]cleverbot connect command."

        # Chromedriver as of chrome version 83.0 only supports unicode codepoints upto 0xFFF
        # https://bugs.chromium.org/p/chromedriver/issues/detail?id=187
        if self.browser_name == "chrome":
            message = ''.join(c for c in message if ord(c) < 0xFFFF)

        # Cleverbot website checks input for HTML and displays alert if it detects
        # input had < > symbols. The alert window removes focus from text field causing bot to
        # loop.
        p1 = '<DOCTYPE'
        p2 = r'<([^>]+)>' # '<>' is accepted as it is empty and throws error iff <> is not empty
        if re.match(p1, message, flags=re.IGNORECASE):
            new_message = re.sub(p1, "", message, flags=re.IGNORECASE)
        elif re.match(p2, message, flags=re.IGNORECASE):
            new_message = re.sub(p2, "\1", message, flags=re.IGNORECASE)
        else:
            new_message = message
        while self.processing:
            await asyncio.sleep(0.05)
        self.processing = True
        self.send_input(new_message)
        bot_reply = await self.get_response(self.wait_time)
        return bot_reply

    @cleverbot.command()
    @checks.mod()
    async def connect(self, ctx):
        """ Connect to cleverbot. """
        if self.browser is not None:
            await ctx.send("Already connected.")
            return
        try:
            settings = None
            if not self.browser_name:
                self.browser_name = await self.config.guild(ctx.guild).browser_name()
                settings = await self.config.get_raw(self.browser_name)
            await self.initialize_browser(self.browser_name, settings)
            self.browser.get(self.url)  # Loads url
        except InvalidPath:
            await ctx.send("Path to webdriver is not set. Set path using [p]cleverbot setdata")
        await ctx.send("Connection Success!")

    @cleverbot.command()
    async def say(self, ctx, *, message):
        """ Send message to cleverbot. """
        clean = ctx.message.clean_content
        command_used = str(ctx.command)
        # Remove first word(s) based on command used
        # https://stackoverflow.com/a/14098502
        text = clean.split(' ', len(command_used.split()))[-1]
        bot_reply = await self.getreply(text, ctx.guild)
        await ctx.send("{} {}".format(bot_reply, ctx.author.mention))
        self.processing = False

    @commands.Cog.listener()
    async def on_message(self, message):
        bot_id = self.bot.user.id
        msg = message.clean_content
        # Check if bot was tagged
        # https://stackoverflow.com/a/50118016/10168590
        if re.match("^<@!?{}>".format(bot_id), message.content) is not None:
            # Remove first word ie the tag
            text = msg.split(' ', 1)[-1]
            bot_reply = await self.getreply(text, message.guild)
            await message.channel.send("{} {}".format(bot_reply, message.author.mention))
            self.processing = False

    """ Functions below are to be used only for moderation """

    @cleverbot.command()
    @checks.mod()
    async def quit(self, ctx):
        """ Close browser. """
        if self.browser is not None:
            self.browser.quit()
            self.browser = None
            await ctx.send("Closed browser!")
        else:
            await ctx.send("Browser is not running.")

    @cleverbot.command()
    @checks.mod()
    async def usage(self, ctx):
        """ Report CPU and RAM usage of computer running bot. """
        try:
            import psutil
        except ImportError:
            await ctx.send("You need to have `psutil` package installed.")
            return
        msg = "CPU Usage is {}. Ram usage is {}".format(
            psutil.cpu_percent(), dict(psutil.virtual_memory()._asdict())['percent'])
        await ctx.send(msg)

    @cleverbot.command(name="options")
    @checks.mod()
    async def list_options(self, ctx, name=None):
        """ List options."""
        if name is not None:
            try:
                val = self.config.get_raw(name)
            except KeyError:
                try:
                    val = self.config.guild(ctx.guild).get_raw(name)
                except KeyError:
                    await ctx.send("Value not found for {}.", name)
                    return
            await ctx.send(str(val))
            return

        # Recursive generator function to return key with appropriate amount of space and value
        def format_option(dictionary, current_level=0):
            initial_space = ' ' * 4 * current_level
            for key, value in dictionary.items():
                if type(value) is dict:
                    yield "{}{}:\n".format(initial_space, key)
                    for string in format_option(value, current_level + 1):
                        yield string
                else:
                    yield "{}{}: '{}'   \n".format(initial_space, key, value)
        options_str = ""
        for opt in format_option(await self.config.guild(ctx.guild).all()):
            options_str += opt
        for opt in format_option(await self.config.all()):
            options_str += opt
        embed = discord.Embed()
        embed.type = "rich"
        embed.title = "Options for cleverbot:"
        embed.colour = discord.Colour.dark_red()
        nevus = self.bot.get_user(473446760233041929)
        embed.set_footer(text="Bot by " + nevus.name, icon_url=nevus.avatar_url)
        # Put in code block to preserve spaces
        embed.description = "```{}```".format(options_str)
        await ctx.send(embed=embed)

    @cleverbot.command(name="setdata")
    @checks.admin()
    async def set_data(self, ctx, name: str, val):
        """ Set any data for cleverbot. """
        try:
            await self.config.get_attr(name).set(val)
        except KeyError:
            await ctx.send("Variable {} not found.".format(name))
        a = await self.config.get_raw(name)
        await ctx.send("Set {} to {}.".format(name, a))

    @commands.group(name="setcleverbot")
    async def setcleverbot(self, ctx):
        """ Set options for cleverbot """
        pass

    @setcleverbot.command(name="waittime")
    @checks.mod()
    async def set_wait_time(self, ctx, time: int):
        """ Set how long the bot waits for reply from server. """
        await self.config.guild(ctx.guild).wait_time.set(int(time))
        await ctx.send("Set wait time to {}.".format(await self.config.guild(ctx.guild).wait_time()))

    @setcleverbot.group(name="chrome")
    @checks.admin()
    async def chrome_settings(self, ctx):
        """ Set data for chrome. """
        pass

    @chrome_settings.command(name="webdriver")
    async def chrome_webdriver(self, ctx, path):
        """ Set webdriver path for chrome"""
        if not valid_file(path):
            await ctx.send("{} is not a existing file.".format(path))
            return
        previous = await self.config.chrome()
        previous['webdriver'] = path
        await self.config.chrome.set(previous)
        await ctx.send("Set {} to '{}'.".format("chrome webdriver", path))

    @chrome_settings.command(name="executable")
    async def chrome_executable(self, ctx, path):
        """ Set executable path for chrome"""
        if not valid_file(path):
            await ctx.send("{} is not a existing file.".format(path))
            return
        previous = await self.config.chrome()
        previous['executable'] = path
        await self.config.chrome.set(previous)
        await ctx.send("Set {} to '{}'.".format("chrome webdriver", path))

    @setcleverbot.group(name="firefox")
    @checks.admin()
    async def firefox_settings(self, ctx):
        """ Set data for firefox. """
        pass

    @firefox_settings.command(name="webdriver")
    async def firefox_webdriver(self, ctx, path):
        """ Set webdriver path for firefox"""
        if not valid_file(path):
            await ctx.send("{} is not a existing file.".format(path))
            return
        previous = await self.config.firefox()
        previous['webdriver'] = path
        await self.config.firefox.set(previous)
        await ctx.send("Set {} to '{}'.".format("firefox webdriver", path))

    @firefox_settings.command(name="executable")
    async def firefox_executable(self, ctx, path):
        """ Set executable path for chrome"""
        if not valid_file(path):
            await ctx.send("{} is not a existing file.".format(path))
            return
        previous = await self.config.firefox()
        previous['executable'] = path
        await self.config.firefox.set(previous)
        await ctx.send("Set {} to '{}'.".format("firefox webdriver", path))

    @setcleverbot.command(name="autoconnect")
    @checks.mod()
    async def toggle_autoconnect(self, ctx):
        """ Set whether bot attempts autoconnect. """
        current = await self.config.guild(ctx.guild).autoconnect()
        new = not current
        await self.config.guild(ctx.guild).autoconnect.set(new)
        await ctx.send("Set autoconnect to {}.".format(not current))

    @cleverbot.command(name="reset")
    @checks.is_owner()
    async def reset_config_data(self, ctx, attribute):
        """ Reset config data for attribute or all data if attribute is 'all'. """
        async def action_confirm(value):
            await ctx.send('Are you sure you want to reset {}?'.format(value))
            pred = predicates.MessagePredicate.yes_or_no(ctx)
            await self.bot.wait_for("message", check=pred)
            return pred.result
        if attribute.lower() == "all":
            if await action_confirm(attribute):
                await self.config.clear_all()
                await self.config.guild(ctx.guild).clear()
                return await ctx.send("Done!")
        try:
            default = self.default_global[attribute]
            if await action_confirm(attribute):
                await self.config.get_attr(attribute).set(default)
                return await ctx.send("Done!")
        except KeyError:
            try:
                default = self.default_guild[attribute]
                if await action_confirm(attribute):
                    await self.config.guild(ctx.guild).get_attr(attribute).set(default)
                    await ctx.send("Done!")
            except KeyError:
                await ctx.send("Variable {} not found.".format(attribute))
                return

    async def initialize_browser(self, browser_name: str, settings: dict):
        """ Launch browser """
        if browser_name == "firefox":
            webdriver_path = settings.get('webdriver', None)
            executable_path = settings.get('executable', None)
            # If variable is not set look in system path
            if webdriver_path is None:
                if shutil.which("geckodriver") is not None:
                    webdriver_path = "geckodriver"
                # If path is not set and geckodriver is not in system PATH
                else:
                    raise InvalidPath
            # If variable is set check if file exists
            # DOES NOT check if file is valid geckodriver
            elif not valid_file(webdriver_path):
                raise InvalidPath
            options = webdriver.firefox.options.Options()
            options.add_argument("--headless")     # Prevent opening window
            options.add_argument("--safe-mode")
            if executable_path is not None:
                binary = webdriver.firefox.firefox_binary.FirefoxBinary(executable_path)
            else:
                binary = None
            self.browser = webdriver.Firefox(
                executable_path=webdriver_path,
                options=options,
                firefox_binary=binary)
        elif browser_name == "chrome":
            webdriver_path = settings.get('webdriver', None)
            executable_path = settings.get('executable', None)
            # If variable is not set look in system path
            if webdriver_path is None:
                if shutil.which("chromedriver") is not None:
                    webdriver_path = "chromedriver"
                else:
                    raise InvalidPath
            # If variable is set check if file exists
            if not valid_file(webdriver_path):
                raise InvalidPath
            options = webdriver.chrome.options.Options()
            if executable_path is not None:
                options.binary_location = executable_path
            options.add_argument("--headless")      # Prevent opening window
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-gpu")
            options.add_argument("--log-level=3")
            self.browser = webdriver.Chrome(executable_path=webdriver_path, options=options)

    def send_input(self, user_input):
        """ Put user input in text field and submit with enter key. """
        if self.browser is None:
            raise NoBrowser
        while True:
            try:
                self.input_field = self.browser.find_element_by_class_name('stimulus')
                self.input_field.send_keys(user_input + Keys.RETURN)
            except BrokenPipeError:
                continue
            break

    async def get_response(self, wait_time: int) -> str:
        """ Return response from bot """
        if self.browser is None:
            raise NoBrowser
        while True:
            try:
                # Get line, wait for given time and try again
                # If two lines are same ie it has finished loading but not empty break 
                # else try again
                line = self.browser.find_element_by_id('line1')
                await asyncio.sleep(wait_time)
                new_line = self.browser.find_element_by_id('line1')
                if ((line.text == new_line.text 
                       and new_line.text not in [' ', ''] 
                       and new_line.text[-1] in ['.', '?', '!'])):
                    line = self.browser.find_element_by_id('line1')
                else:
                    continue
            except StaleElementReferenceException:
                url = self.url + '/?' + str(int(self.count + 1))
                self.count += 1
                self.browser.get(url)
                continue
            except BrokenPipeError:
                continue
            else:
                return line.text

