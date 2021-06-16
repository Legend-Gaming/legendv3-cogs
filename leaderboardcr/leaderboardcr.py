from aiohttp import ClientSession
import asyncio
import json
from redbot.core import commands
import discord
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

player_trophy_list = {}

class CRLeaderBoard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = asyncio.get_event_loop()
        self.session = ClientSession(loop=self.loop)
    
    async def coctoken(self):
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token['token'] is None:
            print("CR token not set")

        CRKEY = token['token']
        global headers
        headers = {"Authorization": f'Bearer {CRKEY}'}


    async def fetch(self, url):
        async with self.session.request("GET", url=url, headers=headers) as response:
            return await response.read()


    async def get_member_data(self, tag):
        url = f"https://proxy.royaleapi.dev/v1/clans/%23{tag}"
        clan_data = json.loads(await self.fetch(url))
        async for member in AsyncIter(clan_data["memberList"]):
            name = member['name']+"("+member['tag']+")"
            player_trophy_list[name] = member['trophies']
        return player_trophy_list
    
    @commands.command()
    async def legendleaderboard(self, ctx):
        desc = ""
        clan_tags = ["8QRQQ8RG", "L8J2VC20", "YLULCRQJ", "99R2PQVR", "PRCRJYCR", "J0CQ9R9", "P9GG9QQY",
                     "Y8G9C09", "2CJ88808", "80CC8", "RY9QJU2", "9P2PQULQ", "9PJYVVL2", "VJQ0GJ0", "29YPJYY", "Q0JJ2GG2"]
        embed_list = []

        async for tag in AsyncIter(clan_tags):
            member_list = await(self.get_member_data(tag))
        final = {k: v for k, v in sorted(member_list.items(), key=lambda x: x[1], reverse=True)}

        async for k, v in AsyncIter(enumerate(final)):
            trophies = final[v]

            desc += f"**Number {k+1}**- **{v}** - **{trophies}** trophies \n"
            if (k+1)%20 == 0:
                embed = discord.Embed(color=discord.Color.blue(), title="Legend Trophy Leaderboard", description=desc)
                embed_list.append(embed)
                desc=""
        await menu(ctx, embed_list, DEFAULT_CONTROLS)
        
