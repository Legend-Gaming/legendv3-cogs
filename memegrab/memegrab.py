import praw  # pip install praw
from redbot.core import commands, bank, Config
from redbot.core import checks
import discord
from datetime import date
import time


class MemeGrab(commands.Cog):
    """Red V3 Cog for Getting Memes off Reddit"""
    reddit = None

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=293878237)
        default_global = {'index': 0,
                         'lastref': '1970-01-01',
                         'dailycnt': 5,
                         'idlist': []
                         }
        self.config.register_global(**default_global)

    async def check(self):
        reddit_keys = await self.bot.get_shared_api_tokens("reddit")
        if reddit_keys.get("client_id") is None or reddit_keys.get("client_secret") is None:
            raise ValueError(
                "Client ID or Secret is missing. Set it using [p]set api reddit client_id,YOUR_CLIENT_ID "
                "client_secret,YOUR_CLIENT_SECRET")
        self.reddit = praw.Reddit(client_id=reddit_keys.get("client_id"),
                                  client_secret=reddit_keys.get("client_secret"),
                                  user_agent="windows:n/a:v1.1 (by u/generalLeoley)")

    def refresh_memes(self, limit: int):
        id_list = []
        for submission in self.reddit.subreddit('memes').top(limit=limit, time_filter='day'):
            detail = {'title': submission.title, 'ups': submission.ups, 'url': submission.url,
                      'permalink': submission.permalink}
            id_list.append(detail)
        return id_list

    def getEmbed(self, memeid):
        submission = memeid
        embed = discord.Embed(title=submission['title'],
                              url="https://www.reddit.com{}".format(submission['permalink']),
                              description="Upvotes: {}".format(submission['ups']), color=0x008000)
        embed.set_image(url=submission['url'])
        embed.set_footer(text="Bot by: Generaleoley | Legend Family")
        return embed

    @commands.command()
    async def meme(self, ctx):
        """Get a Meme"""
        lastref = await self.config.lastref()
        memeind = await self.config.index()
        dailymax = await self.config.dailycnt()

        if str(date.today()) != lastref:
            await self.config.lastref.set(str(date.today()))
            idlist = self.refresh_memes(dailymax)
            await self.config.idlist.set(idlist)
            await self.config.index.set(0)
            memeind = -1

        if memeind >= dailymax:
            dailymax *= 2
            await self.config.dailycnt.set(dailymax)
            idlist = self.refresh_memes(dailymax)
            await self.config.idlist.set(idlist)

        idlist = await self.config.idlist()

        embed = self.getEmbed(memeid=idlist[memeind])
        await ctx.send(embed=embed)

        memeind += 1
        await self.config.index.set(memeind)

    @commands.command()
    @checks.mod_or_permissions(manage_roles=True)
    async def resetdata(self, ctx):
        await self.config.clear()
        await ctx.send("Done")

    @commands.command()
    async def memeinfo(self, ctx):
        guilddata = self.config
        ref = await guilddata.lastref()
        inx = await guilddata.index()
        cnt = await guilddata.dailycnt()
        embed = discord.Embed(title='Meme Cog Configuration', description='Note values may change dynamically')
        embed.add_field(name='Last Refresh', value=ref)
        embed.add_field(name='Current Index', value=inx)
        embed.add_field(name='Daily Refresh Count', value=cnt)
        embed.set_footer(text="Bot by: Generaleoley | Legend Family")
        await ctx.send(embed=embed)
       
