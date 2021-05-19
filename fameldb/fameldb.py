import discord
import asyncio
import aiohttp
from redbot.core import commands

tl_clans = ['RY9QJU2']
sleep_time = 600
channelid = 844120574921539625
fame_emoji = "FAMEEMOJI"

class FameLeaderboard(commands.Cog):
    """Auto-updating leaderboard of clans"""
    def __init__(self, bot):
        self.bot = bot
        self.update_embed_task = bot.loop.create_task(self.update_embed())
        self.tags = self.bot.get_cog('ClashRoyaleTools').tags

    async def update_embed(self):
        try:
            channel = await self.bot.fetch_channel(844120574921539625)
            await asyncio.sleep(10)  # Start-up Time
            prev = None
            while True:
                embed = await self.get_data()
                if prev is not None:
                    await prev.delete()
                prev = await channel.send(embed=embed)


                # Run Every X seconds
                await asyncio.sleep(sleep_time) 
        except asyncio.CancelledError:
            pass

    async def crtoken(self):
        # Clash Royale API
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token.get('token') is None:
            print("CR Token is not SET. Use !set api clashroyale token,YOUR_TOKEN to set it")
            raise RuntimeError
        self.headers = {'authorization': 'Bearer {}'.format(token['token'])}
        

    async def get_data(self) -> discord.Embed:
        podium = ['🥇', '🥈', '🥉']


        embed=discord.Embed(title="TL Clash Royale Fame Leaderboard", description='These are the top fame contributors from Threat Level Clans in the current river race!', color=0x80ff00)
        embed.set_thumbnail(url="https://thumbs.dreamstime.com/b/leaderboard-podium-line-art-icon-apps-websites-195725814.jpg")
        embed.set_footer(text="Bot by: Threat Level Dev Team")

        members = [] # Runs in O(n log n) where n is the amount of members

        for clantag in tl_clans:
            url = 'https://api.clashroyale.com/v1/clans/%23{}/currentriverrace'.format(clantag)
            async with aiohttp.ClientSession() as client:
                async with client.get(url, headers=self.headers) as resp:
                    if(resp.status != 200):
                        return discord.Embed(title='Clash Royale API Error', description = 'Clash Royale API is offline... data cannot be retreived :(')
                    data = await resp.json()
                    members.extend(data['clan']['participants'])
        ldb = sorted(members, key=lambda member: -member['fame']) # sorts in descending order

        for i, memb in enumerate(ldb):
            if(i > 9):
                break
            title = str(i+1)
            if(i < 3):
                title = podium[i]

            title += ' - '

            # Find discord user
            users = self.tags.get_user(memb['tag'].strip('#'))
            for user in users:
                title += f'<@{user[0]}> - '

            title += f"{memb['name']} ({memb['tag']})"
            value = str(memb['fame']) + fame_emoji
            embed.add_field(title = title, value = value, inline=False)
        
        return embed





        


