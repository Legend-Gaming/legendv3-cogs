from aiohttp import ClientSession
import asyncio
import json
from redbot.core import commands
import discord
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

key = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6ImQxMjM5OTVkLTI0MjctNGYzYi1hN2NlLTAyMjVlNjc5MTljMSIsImlhdCI6MTU5NjY0MzE3Miwic3ViIjoiZGV2ZWxvcGVyLzYwN2M4NWRiLTBkNzYtM2YxZC0yODBlLTZiMjNhNjFhNDVlOSIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyIxMjguMTI4LjEyOC4xMjgiXSwidHlwZSI6ImNsaWVudCJ9XX0.nT2mCANdy5eVTDzllr-UTvLq_DgqNJavGqnzvIbGpMfKzCDPDpPrCa-2RNxG8xNX6Ckmhmd0wP3tCVIpjXQwMA'
headers = {
    'Accept': 'application/json',
    'Authorization': f'Bearer {key}'
}

player_trophy_list = {}

class CRLeaderBoard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = asyncio.get_event_loop()
        self.session = ClientSession(loop=self.loop)


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
        member_list = {"king slayer(#YPGU8UYP)": 10000}
        embed_list = []

        async for tag in AsyncIter(clan_tags):
            member_list = await(self.get_member_data(tag))
            member_list['king slayer(#YPGU8UYP)'] = 10000
        final = {k: v for k, v in sorted(member_list.items(), key=lambda x: x[1], reverse=True)}

        async for k, v in AsyncIter(enumerate(final)):
            trophies = final[v]

            desc += f"**Number {k+1}**- **{v}** - **{trophies}** trophies \n"
            if (k+1)%20 == 0:
                embed = discord.Embed(color=discord.Color.blue(), title="Legend Trophy Leaderboard", description=desc)
                embed_list.append(embed)
                desc=""
        await menu(ctx, embed_list, DEFAULT_CONTROLS)
        
