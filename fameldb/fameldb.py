import discord
import asyncio
import aiohttp
from redbot.core import commands

tl_clans = ['RY9QJU2', '8UQ2', 'LR9CY9VQ', '9CJ9YGPL', 'P09GPU', 'Y9G2LQ2Y', 'PGPQQ8UV', 'PPCG80G0', 'YJ8GRVGY', '9Q20L', 'YU20PCQU']
sleep_time = 600
fameid = 844662799379595305
donationsid = 844663013058543676
fame_emoji = "<:cwfame:844641612608176178>"
donations_emoji = "<:donations:844657488389472338>"

class FameLeaderboard(commands.Cog):
    """Auto-updating leaderboard of clans"""
    def __init__(self, bot):
        self.bot = bot
        self.tags = self.bot.get_cog('ClashRoyaleTools').tags
        # print(self.bot.get_cog('ClashRoyaleTools').meme)
        self.update_embed_task = bot.loop.create_task(self.update_embed())

    async def update_embed(self):
        try:
            famechannel = await self.bot.fetch_channel(fameid)
            donationchannel = await self.bot.fetch_channel(donationsid)
            await asyncio.sleep(10)  # Start-up Time
            prev = None
            prev2 = None
            while True:
                embed = await self.get_data_fame()
                if prev is not None:
                    await prev.delete()
                prev = await famechannel.send(embed=embed)
                embed2 = await self.get_data_donations()
                if prev2 is not None:
                    await prev2.delete()
                prev2 = await donationchannel.send(embed=embed2)


                # Run Every X seconds
                await asyncio.sleep(sleep_time) 
        except asyncio.CancelledError:
            pass

    async def crtoken(self):
        # Clash Royale API
        token = await self.bot.get_shared_api_tokens("clashroyaleb")
        if token.get('token') is None:
            print("CR Token is not SET. Use !set api clashroyale token,YOUR_TOKEN to set it")
            raise RuntimeError
        self.headers = {'authorization': 'Bearer {}'.format(token['token'])}
    
    def cog_unload(self):
        self.update_embed_task.cancel()
        

    async def get_data_fame(self) -> discord.Embed:
        podium = ['🥇', '🥈', '🥉']


        embed=discord.Embed(title="TL Clash Royale Fame Leaderboard", description='These are the top fame contributors from Threat Level Clans in the current river race!', color=0x80ff00)
        embed.set_thumbnail(url="https://static.wikia.nocookie.net/clashroyale/images/9/9f/War_Shield.png/revision/latest?cb=20180425130200")
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

        for i, memb in enumerate(ldb): # This all looks weird but it's embed formatting
            if(i > 9):
                break
            title = str(i+1)
            if(i < 3):
                title = podium[i]

            title += ' - ' + str(memb['fame']) + fame_emoji

            # Find discord user
            value = ''
            try:
                users = self.tags.getUser(memb['tag'].strip('#'))
                for user in users:
                    value += f'<@{user[0]}> - '
            except Exception as e:
                print(e)

            # Get Clan
            clan = ''
            uurl = 'https://api.clashroyale.com/v1/players/%23{}/'.format(memb['tag'].strip('#'))
            async with aiohttp.ClientSession() as client:
                async with client.get(uurl, headers=self.headers) as resp:
                    if(resp.status != 200):
                        return discord.Embed(title='Clash Royale API Error', description = 'Clash Royale API is offline... data cannot be retreived :(')
                    data = await resp.json()
                    clan = data['clan']['name']

            value += f"{memb['name']} ({memb['tag']}) | {clan} "
            embed.add_field(name = title, value = value, inline=False)
        
        return embed


    async def get_data_donations(self) -> discord.Embed:
        podium = ['🥇', '🥈', '🥉']


        embed=discord.Embed(title="TL Clash Royale Donation Leaderboard", description='These are the donators from Threat Level Clans in the current week!', color=0x80ff00)
        embed.set_thumbnail(url="https://cdn.royaleapi.com/static/img/badge/legendary-1/Fugi_03.png?t=494e7fc1c")
        embed.set_footer(text="Bot by: Threat Level Dev Team")

        members = [] # Runs in O(n log n) where n is the amount of members

        for clantag in tl_clans:
            url = 'https://api.clashroyale.com/v1/clans/%23{}/'.format(clantag)
            async with aiohttp.ClientSession() as client:
                async with client.get(url, headers=self.headers) as resp:
                    if(resp.status != 200):
                        return discord.Embed(title='Clash Royale API Error', description = 'Clash Royale API is offline... data cannot be retreived :(')
                    data = await resp.json()
                    members.extend(data['memberList'])
        ldb = sorted(members, key=lambda member: -member['donations']) # sorts in descending order

        for i, memb in enumerate(ldb): # This all looks weird but it's embed formatting
            if(i > 9):
                break
            title = str(i+1)
            if(i < 3):
                title = podium[i]

            title += ' - ' + str(memb['donations']) + donations_emoji

            # Find discord user
            value = ''
            try:
                users = self.tags.getUser(memb['tag'].strip('#'))
                for user in users:
                    value += f'<@{user[0]}> - '
            except Exception as e:
                print(e)

            # Get Clan
            clan = ''
            uurl = 'https://api.clashroyale.com/v1/players/%23{}/'.format(memb['tag'].strip('#'))
            async with aiohttp.ClientSession() as client:
                async with client.get(uurl, headers=self.headers) as resp:
                    if(resp.status != 200):
                        return discord.Embed(title='Clash Royale API Error', description = 'Clash Royale API is offline... data cannot be retreived :(')
                    data = await resp.json()
                    clan = data['clan']['name']

            value += f"{memb['name']} ({memb['tag']}) | {clan} "
            embed.add_field(name = title, value = value, inline=False)
        
        return embed

    @commands.command()
    async def topdonations(self, ctx):
        """Get Top 10 Donators this week"""
        async with ctx.typing():
            embed = await self.get_data_donations()
            await ctx.send(embed=embed)


    @commands.command()
    async def topfame(self, ctx):
        """Get Top 10 Fame Contributors this war"""
        async with ctx.typing():
            embed = await self.get_data_fame()
            await ctx.send(embed=embed)





        


