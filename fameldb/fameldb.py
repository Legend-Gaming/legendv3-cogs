import discord
import asyncio
import aiohttp
from redbot.core import commands, Config
#TO-DO
"""
Make it work with individual servers
Make the code work with config
"""

tl_clans = ['RY9QJU2', '8UQ2', 'LR9CY9VQ', '9CJ9YGPL', 'P09GPU',
            'Y9G2LQ2Y', 'PGPQQ8UV', 'PPCG80G0', 'YJ8GRVGY', '9Q20L', 'YU20PCQU']
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
        self.update_embed_task = bot.loop.create_task(self.update_embed())
        self.config = Config.get_conf(self, identifier=2345341233)
        default_settings = {"main": {"server_id": 857098966726344704,
                            "use": True,
                            "channel_id": 857098966726344707},
                "clan_servers": {
                "Dragons Eight": {
                    "server_id": 857098966726344704,
                    "use": True,
                    "channel_id": 857128031189860362,
                    "tag": "29YPJYY",
                    "nickname": "D8",
            },
                "LeGeND Legion!": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "VJQ0GJ0",
                    "nickname": "Legion",
            },
                "LeGeND Titan!": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "9PJYVVL2",
                    "nickname": "Titan"
            },
                "Dragons Eight 2": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "Y8G9C09",
                    "nickname": "D82"
            },
                "LeGeND Squad!": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "80CC8",
                    "nickname": "Squad"
            },
                "LeGeND Prime!": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "Q0JJ2GG2",
                    "nickname": "Prime"
            },
                "LeGeND Empire!": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "9P2PQULQ",
                    "nickname": "Empire"
            },
                "LeGeND Dynasty!": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "99R2PQVR",
                    "nickname": "Dynasty"
            },
                "LeGeND eSports!": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "P9GG9QQY",
                    "nickname": "eSports"
            },
                "White Plague": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "J0CQ9R9",
                    "nickname": "Plague"
            },
                "Dragons Eight 3": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "PRCRJYCR",
                    "nickname": "D83"
            },
                "LeGeND Phantom!": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "2CJ88808",
                    "nickname": "Phantom"
            },
                "LeGeND Pride!": {
                    "server_id": None,
                    "use": False,
                    "channel_id": None,
                    "tag": "YLULCRQJ",
                    "nickname": "Pride"
            }
            }}
        self.config.register_global(**default_settings)

    async def update_embed(self):
        try:
            main = await self.config.main()
            clans = await self.config.clan_servers()
            main_embed, clan_embeds = await self.get_fame_data()
            await asyncio.sleep(10)  # Start-up Time
            while True:
                if main['use'] == True:
                    main_guild_id = main['server_id']
                    main_channel_id = main["channel_id"]
                    main_guild = self.bot.get_guild(main_guild_id)
                    main_channel = main_guild.get_channel(main_channel_id)
                    if main.get('last_message_id') == None:
                        message = await main_channel.send(embed=main_embed)
                        async with self.config.main() as data:
                            data['last_message_id'] = message.id
                    else:
                        last_mes_id = main['last_message_id']
                        try:
                            message = await main_channel.fetch_message(last_mes_id)
                            await message.delete()
                        except Exception as e:
                            print(e)
                        message = await main_channel.send()
                        async with self.config.main() as data:
                            data['last_message_id'] = message.id
                if clan_embeds != None:
                    for clan in clans:
                        x = clans[clan]
                        if clans[clan]['use'] == True:
                            clan_guild = self.bot.get_guild(clans[clan]['server_id'])
                            clan_channel = clan_guild.get_channel(clans[clan]['channel_id'])
                            if x.get('last_message_id') == None:
                                if clan_embeds.get(clans[clan]['tag']) == None: #some edge case scenario
                                    pass
                                else:
                                    clan_emb = clan_embeds[[clans][clan]['tag']]
                                    message = await clan_channel.send(embed=clan_emb)
                                    async with self.config.clan_servers() as data:
                                        data[clan]['last_message_id'] = message.id
                            else:
                                # some edge case scenario
                                if clan_embeds.get(clans[clan]['tag']) == None:
                                    pass
                                else:
                                    last_mes_id = clans[clan]['last_message_id']
                                    try:
                                        message = await clan_channel.fetch_message(last_mes_id)
                                        await message.delete()
                                    except Exception as e:
                                        print(e)
                                    clan_emb = clan_embeds[[clans][clan]['tag']]
                                    message = await clan_channel.send(embed=clan_emb)
                                    async with self.config.clan_servers() as data:
                                        data[clan]['last_message_id'] = message.id

                # Run Every X seconds
                    await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            pass

    async def crtoken(self):
        # Clash Royale API
        token = await self.bot.get_shared_api_tokens("ksclashroyale")
        if token.get('token') is None:
            print(
                "CR Token is not SET. Use !set api clashroyale token,YOUR_TOKEN to set it")
            raise RuntimeError
        self.headers = {'authorization': 'Bearer {}'.format(token['token'])}

    def cog_unload(self):
        self.update_embed_task.cancel()
    
    async def ldb_to_emb(self, ldb, base_embed, clan_spec:bool= False):
        # This all looks weird but it's embed formatting
        pos = 9
        if clan_spec == True:
            pos = 4
        podium = ['🥇', '🥈', '🥉']
        for i, memb in enumerate(ldb):
            if(i > pos):
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
            uurl = 'https://api.clashroyale.com/v1/players/%23{}/'.format(
                memb['tag'].strip('#'))
            async with aiohttp.ClientSession() as client:
                async with client.get(uurl, headers=self.headers) as resp:
                    if(resp.status != 200):
                        return discord.Embed(title='Clash Royale API Error', description='Clash Royale API is offline... data cannot be retreived :(')
                    data = await resp.json()
                    clan = data['clan']['name']

            value += f"{memb['name']} ({memb['tag']}) | {clan} "
            base_embed.add_field(name=title, value=value, inline=False)

        return base_embed

    async def get_data_fame(self) -> discord.Embed:
        embed = discord.Embed(title="Legend Clash Royale Fame Leaderboard",
                              description='These are the top fame contributors from Legend Clans in the current river race!', color=0x80ff00)
        embed.set_thumbnail(
            url="https://static.wikia.nocookie.net/clashroyale/images/9/9f/War_Shield.png/revision/latest?cb=20180425130200")
        embed.set_footer(text="Bot by: Legend Dev Team",
                         icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")

        members = []  # Runs in O(n log n) where n is the amount of members
        clan_mem_dict = dict()
        legend_clans = await self.config.clan_servers()
        for clan_data in legend_clans:
            url = 'https://api.clashroyale.com/v1/clans/%23{}/currentriverrace'.format(
                legend_clans[clan_data]['tag'])
            async with aiohttp.ClientSession() as client:
                async with client.get(url, headers=self.headers) as resp:
                    if(resp.status != 200):
                        return discord.Embed(title='Clash Royale API Error', description='Clash Royale API is offline... data cannot be retreived :(')
                    data = await resp.json()
                    members.extend(data['clan']['participants'])
                    if legend_clans[clan_data]['use'] == True:
                        clan_mems = data['clan']['participants']
                        sorted_clan_mems = sorted(clan_mems, key= lambda x: x['fame'], reverse=True)
                        clan_mem_dict[legend_clans[clan_data]['tag']] = sorted_clan_mems 

        # sorts in descending order
        ldb = sorted(members, key=lambda member: -member['fame'])
        main_emb = await self.ldb_to_emb(ldb=ldb, base_embed=embed)
        if len(clan_mem_dict) == 0:
            return main_emb, None
        else:
            embed_dict = dict()
            for tag in clan_mem_dict:
                em = await self.ldb_to_emb(ldb=clan_mem_dict[tag], base_embed=embed, clan_spec=True)
                embed_dict['tag'] = em
            return main_emb, embed_dict

    @commands.command()
    async def topfame(self, ctx):
        """Get Top 10 Fame Contributors this war"""
        async with ctx.typing():
                embed, clan_emb = await self.get_data_fame()
                await ctx.send(embed=embed)

    """
    async def get_data_donations(self) -> discord.Embed:
        podium = ['🥇', '🥈', '🥉']

        embed = discord.Embed(title="TL Clash Royale Donation Leaderboard",
                              description='These are the donators from Threat Level Clans in the current week!', color=0x80ff00)
        embed.set_thumbnail(
            url="https://cdn.royaleapi.com/static/img/badge/legendary-1/Fugi_03.png?t=494e7fc1c")
        embed.set_footer(text="Bot by: Threat Level Dev Team")

        members = []  # Runs in O(n log n) where n is the amount of members

        for clantag in tl_clans:
            url = 'https://api.clashroyale.com/v1/clans/%23{}/'.format(clantag)
            async with aiohttp.ClientSession() as client:
                async with client.get(url, headers=self.headers) as resp:
                    if(resp.status != 200):
                        return discord.Embed(title='Clash Royale API Error', description='Clash Royale API is offline... data cannot be retreived :(')
                    data = await resp.json()
                    members.extend(data['memberList'])
        # sorts in descending order
        ldb = sorted(members, key=lambda member: -member['donations'])

        # This all looks weird but it's embed formatting
        for i, memb in enumerate(ldb):
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
            uurl = 'https://api.clashroyale.com/v1/players/%23{}/'.format(
                memb['tag'].strip('#'))
            async with aiohttp.ClientSession() as client:
                async with client.get(uurl, headers=self.headers) as resp:
                    if(resp.status != 200):
                        return discord.Embed(title='Clash Royale API Error', description='Clash Royale API is offline... data cannot be retreived :(')
                    data = await resp.json()
                    clan = data['clan']['name']

            value += f"{memb['name']} ({memb['tag']}) | {clan} "
            embed.add_field(name=title, value=value, inline=False)

        return embed

    @commands.command()
    async def topdonations(self, ctx):
        Get Top 10 Donators this week
        async with ctx.typing():
            embed = await self.get_data_donations()
            await ctx.send(embed=embed)"""


