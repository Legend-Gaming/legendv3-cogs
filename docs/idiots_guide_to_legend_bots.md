# Idiots Guide to Legends Bots/Cogs
## Disclaimer
- *A lot of this was copy/pasta from [Discord.js Guide](https://discordjs.guide/), which I appropriated and converted/enhanced for discordppy.guide*
- [DiscordJS Guide](https://github.com/discordjs/guide)
- As the python guide is just starting, we of course will not have *everything* the DiscordJS guide has.  As such, make sure to go back to the DiscordJS guide as needed as they have a huge community constantly updating the documentation.

## Introduction
If you are reading this, it probably means you want to learn how to make a bot with discord.py. Awesome! You've come to the right place. This guide will teach you things such as:

- How to get a bot up and running from scratch;
- How to properly create, organize, and expand on your commands;
- How to use the best practices for common situations;
- and much more.
This guide will also cover subjects like common errors and how to solve them, keeping your code clean, setting up a proper development environment, etc. Sounds good? Great! Let's get started, then.

## Before you begin...
Alright, making a bot is cool and all, but there are some prerequisites to it. To create a bot with discord.py, you should have a fairly decent grasp of Python itself. While you can make a bot with very little Python and programming knowledge, trying to do so without understanding the language first will only hinder you. You may get stuck on many uncomplicated issues, struggle with solutions to incredibly easy problems, and all-in-all end up frustrated. Sounds pretty annoying.

If you don't know Python but would like to learn about it, here are a few links to help get you started:

- [CodeCademy's interactive Python3 course](https://www.codecademy.com/learn/learn-python-3)
- Books (If you decide to only read a few books, make sure you read those):
  - [Dive Into Python3](https://diveintopython3.net/), a free online book.
  - [Problem Solving with Algorithms and Data Structures using Python](https://runestone.academy/runestone/books/published/pythonds/index.html) a free online course!
  - [Automate the boring stuff with Python](https://automatetheboringstuff.com/)
  - [Python Cookbook](http://shop.oreilly.com/product/0636920027072.do)
  - [Think Python: How to Think Like a Computer Scientist](http://greenteapress.com/thinkpython/html/index.html)
- [Python Official Documentation](https://docs.python.org/3/)
- Google, your best friend
- Take your pick, learn some Python, and once you feel like you're confident enough to make a bot, come back and get started!

## Installations & Preparations
*NOTE* It is important you follow these in sequence.
- First, you need Python3
- Then, you need discord.py to be installed/added to Python3
- Then, you need RED bot to be installed
- Then, you need a discord bot account to be created, *and* invited
- Then, you need RED bot to be setup
- Finally, you can start interacting with cogs, and writing your own!

### Preparing the essentials
#### Installing Python3
- [Guide to Python](https://docs.python-guide.org/)

#### Install discord.py
- [Installing discord.py](https://discordpy.readthedocs.io/en/latest/intro.html)

#### Install RED
- [Install RED on Windows](https://docs.discord.red/en/stable/install_windows.html) 
- [Install RED on Linux/macOS](https://docs.discord.red/en/stable/install_linux_mac.html)

#### Setting up a bot application
- [RED's guide to Creating a Bot Account](https://discordpy.readthedocs.io/en/v1.3.3/discord.html#creating-a-bot-account)
- Just for your convenience, the Javascript guide for the same below:
  - [Follow these steps to create your actual discord bot application via Discord's website](https://discordjs.guide/preparations/setting-up-a-bot-application.html#creating-your-bot)
  - [Follow these steps to add your bot to servers](https://discordjs.guide/preparations/adding-your-bot-to-servers.html#bot-invite-links)

#### Setup your RED server
- [Follow these steps to get RED up and running locally so you can host your own bot and test it](https://docs.discord.red/en/stable/getting_started.html)

## Writing your own cogs - basic guide
- Writing a bot always follows the same basic steps:
1. Setup your cog/bot directory structure as follows [RED guide to setting up a package](https://docs.discord.red/en/3.1.8/guide_cog_creation.html?highlight=__init__.py#setting-up-a-package):
```
<cog_folder_name>/
├── README.md
├── __init__.py
├── info.json
└── <your_cog_name>.py
```
2. Setup your README.md file:
   - This file should have enough information about what the cog does, all commands, things that can help users and/or future developers to use it or code/upgrade it. Imagine that you are waking up from a 30 year coma, and you have to go back to enhancing/fixing your code... this file should really help you get started!
   - [README Markup Syntax](https://help.github.com/en/github/writing-on-github/basic-writing-and-formatting-syntax)

3. Setup your info.json file as follows:
   - NOTE: [RED Info.json documentation](https://docs.discord.red/en/3.1.8/framework_downloader.html)
   - NOTE2: if you need to learn what [JSON format is](https://www.tutorialspoint.com/json/index.htm)
```
{
  "author": [
    "<yourname>",
    "Legend Clan Development Team"
  ],
  "description": "<Add a descriptive, informative description of what this cog does>",
  "short": "<Add a shorter description, a summary of the above one>",
  "tags": [
    "<(list of strings) - A list of strings that are related to the functionality of the cog. Used to aid in searching.>",
    "<.e.g greeter>"
  ],
  "requirements": [
    "<list python import dependencies, one per line>",
    "e.g. pytz"
  ],
  "type": "COG"
}
```

4. Setup your skeleton code  as follows:
```
from redbot.core import commands

class Mycog(commands.Cog):
    """My custom cog"""

    @commands.command()
    async def mycom(self, ctx):
        """This does stuff!"""
        # Your code will go here
        await ctx.send("I can do stuff!")
```

5. Setup your ```__init__.py``` file as follows:
```
from .mycog import Mycog

def setup(bot):
    bot.add_cog(Mycog())
```

6. Now, code your bot (Make sure that you follow [Redjumpman coding guide](https://github.com/Redjumpman/Jumper-Plugins/wiki/Red-Coding-Guide-V3))
   - Things to look out for:
     - [Using configuration files (persistent data)](https://docs.discord.red/en/latest/framework_config.html#redbot.core.config.Config.register_global)
     - [Building Embeds](https://github.com/AnIdiotsGuide/discordjs-bot-guide/blob/master/first-bot/using-embeds-in-messages.md)
     - The following tool can help you tremendously with Embeds: [EMBED visualizer](https://leovoel.github.io/embed-visualizer/)

7. Check our very simple first tutorial_cog for an idea:
   - ```__init__.py```
```
from .tutorial_cog import Tutorial_Cog

def setup(bot):
    bot.add_cog(Tutorial_Cog(bot))
```
   - ```tutorial_cog.py```
```
from redbot.core import commands

class Tutorial_Cog(commands.Cog):
    "Minimal tutorial bot"
    def __init__(self, bot):
        self.bot = bot
    @commands.group()
    async def simple_cog(self, ctx):
        pass
    @simple_cog.command()
    async def hello(self, ctx, *, message):
        "Says something in a text channel"
        await ctx.send(f"Cog says: Hello World! {message}")
```
   - Then, on your discord test server, enter the following commands:
     - !load tutorial_cog
     - !help simple_cog
     - !simple_cog hello 'My message'   
   - And you can always reload the cog by doing:
     - !reload tutorial_cog
