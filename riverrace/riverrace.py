import discord
from discord.ext import tasks
from redbot.core import Config, checks, commands
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils.chat_formatting import humanize_list, pagify
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu, start_adding_reactions
from redbot.core.utils.predicates import MessagePredicate
import clashroyale
import requests
import random
import json
import re
from datetime import datetime
from typing import List, Optional
import datetime as Datetime
import asyncio

credits = "Bot by Legend Gaming"
credits_icon = "https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1"

legends = {
         '29YPJYY'  : ['Dragons Eight'   , 702608063185551423 , 750749628747743352],
         'Y8G9C09'  : ['Dragons Eight 2' , 702608063185551423 , 750749630362419231],
         'VJQ0GJ0'  : ['LeGeND Legion!'  , 702608172162088971 , 750749632216170517],
         '9PJYVVL2' : ['LeGeND Titan!'   , 702608239342387240 , 750749633935966239],
         '9P2PQULQ' : ['LeGeND Empire!'  , 702608131573809242 , 750749635907158036],
         'RY9QJU2'  : ['LeGeND Rising!'  , 394868477598498817 , 750749649970790501],
         '80CC8'    : ['LeGeND Squad!'   , 702608145276600460 , 750749651870941315],
         '2LL8LC2R' : ['LeGeND Prime!'   , 702608214750920775 , 750749653498069013],
         '99R2PQVR' : ['LeGeND Dynasty'  , 702608087617634335 , 750749655146561708],
         'P9GG9QQY' : ['LeGeND eSports!' , 702608117250392098 , 750749656937529456],
         '2CJ88808' : ['LeGeND Phantom!' , 702608185143328809 , 750749672313979021],
         'PRCRJYCR' : ['Dragons Eight 3' , 702608063185551423 , 750749674180313191],
         'J0CQ9R9'  : ['White Plague'    , 702608200343617566 , 750749675937726564],
         '8QRQQ8RG' : ['LeGeND Academy!' , 702608103375372489 , 750749677703659520],
         'YLULCRQJ' : ['LeGeND Pride!'   , 738642598243074138 , 750749679771451563],
         'L8J2VC20' : ['LeGeND Eclipse!' , 402178957509918720 , 0]
         }  

tab = "\u200B \u200B \u200B \u200B \u200B"

async def simple_embed(
    ctx: commands.Context,
    message: str,
    success: Optional[bool] = None,
    mentions: dict = dict({"users": True, "roles": True}),
) -> discord.Message:
    """Helper function for embed"""
    if success is True:
        colour = discord.Colour.dark_green()
    elif success is False:
        colour = discord.Colour.dark_red()
    else:
        colour = discord.Colour.blue()
    embed = discord.Embed(description=message, color=colour)
    embed.set_footer(text=credits, icon_url=credits_icon)
    
    
    return await ctx.send(
        embed=embed, allowed_mentions=discord.AllowedMentions(**mentions)
    )

key = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjA0MmIwMjQ5LWFkZGEtNDU1OS1iMzRlLTRiMGY2YWQ1MDllMCIsImlhdCI6MTYwMDAyMDQwOCwic3ViIjoiZGV2ZWxvcGVyLzFiYjYxZDk0LTA2NWMtNzJmNi05NmM0LWQwMDY4MDM3NzNjZCIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyI1MS4xNS4yMjEuOCJdLCJ0eXBlIjoiY2xpZW50In1dfQ.kqYb1IZohSMhHusrDAzPQaVzL2-TcCSPFa9uTu4RSZNUBago4iNcWN4vUCGPWKLDfO41uMdGuzP2maWCu98HdA'
headers = {
          'Accept': 'application/json',
          'Authorization': f'Bearer {key}'
          }

class RiverRace(commands.Cog):
    """Clash royale commands and functions"""

    def __init__(self, bot):
        self.bot = bot
        self.tags = self.bot.get_cog('ClashRoyaleTools').tags
        self.constants = self.bot.get_cog('ClashRoyaleTools').constants

        self.claninfo_path = "/root/.local/share/Red-DiscordBot/data/legendv3/cogs/ClashRoyaleClans/clans.json"
        with open(self.claninfo_path) as file:
            self.family_clans = dict(json.load(file))

        self.token_task = self.bot.loop.create_task(self.crtoken())
        

    async def crtoken(self):
        # Clash Royale API config
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token['token'] is None:
            print("CR Token is not SET. Make sure to have royaleapi ip added (128.128.128.128) Use !set api "
                  "clashroyale token,YOUR_TOKEN to set it")
        self.clash = clashroyale.official_api.Client(token=token['token'], is_async=True,
                                                     url="https://proxy.royaleapi.dev/v1")

    def cog_unload(self):
        if self.token_task:
            self.token_task.cancel()
        if self.clash:
            self.bot.loop.create_task(self.clash.close())

    
    async def clean_time(self, time):
        z = ((time.split("."))[0]).split('T')
        new_time = datetime.strptime(z[0]+z[1], '%Y%m%d%H%M%S')
        return(new_time)
    
    def emoji(self, emoji):
        
        for e in self.bot.emojis:
            if e.name == emoji:
                break
    
        return e.id

    def camelToString(self, label):
        """Convert from camel case to normal"""
        return re.sub(r'((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))', r' \1', label)
        
    async def get_monday(self):
        today = datetime.utcnow()
        Monday = (today - Datetime.timedelta(hours=10)) - Datetime.timedelta(days=today.weekday())
        monday = datetime.strptime((str(Monday).split("."))[0], "%Y-%m-%d %H:%M:%S")
        return monday

    async def get_yday(self):
        today = datetime.utcnow()
        Yday = today - Datetime.timedelta(hours=24)
        yday = datetime.strptime((str(Yday).split("."))[0], "%Y-%m-%d %H:%M:%S")
        return yday

    async def check_accuracy(self, battles, monday):
        last_battle = battles[-1]
        lastbattleTime = await self.clean_time(last_battle["battleTime"])
        if lastbattleTime > monday:
            return False
        else:
            return True


    async def get_riverBattles(self, tag, finishtime):
        
        url = f"https://api.clashroyale.com/v1/players/%23{tag}/battlelog"

        race_data = json.loads(((requests.get(url, headers = headers)).content).decode("utf-8"))
        starttime = await self.get_monday()
        if finishtime == 0:
            finishtime = False
        riverBattles = []
        accuracy = await self.check_accuracy(race_data, starttime)
        if finishtime:
            for i in race_data: 
                if i['type'] in ['riverRaceDuel', 'boatBattle', 'riverRacePvP']:
                    battletime = await self.clean_time(i["battleTime"])
                    if finishtime > battletime and starttime < battletime:
                        riverBattles.append(i)
        else:
            for i in race_data: 
                if i['type'] in ['riverRaceDuel', 'boatBattle', 'riverRacePvP']:
                    battletime = await self.clean_time(i["battleTime"])
                    if starttime < battletime:
                        riverBattles.append(i)
                    
        return accuracy, riverBattles

    async def get_lastriverBattles(self, tag, finishtime):
        
        url = f"https://api.clashroyale.com/v1/players/%23{tag}/battlelog"

        race_data = json.loads(((requests.get(url, headers = headers)).content).decode("utf-8"))
        starttime = await self.get_yday()
        if finishtime == 0:
            finishtime = False
        riverBattles = []
        accuracy = True
        if finishtime:
            for i in race_data: 
                if i['type'] in ['riverRaceDuel', 'boatBattle', 'riverRacePvP']:
                    battletime = await self.clean_time(i["battleTime"])
                    if finishtime > battletime and starttime < battletime:
                        riverBattles.append(i)
        else:
            for i in race_data: 
                if i['type'] in ['riverRaceDuel', 'boatBattle', 'riverRacePvP']:
                    battletime = await self.clean_time(i["battleTime"])
                    if starttime < battletime:
                        riverBattles.append(i)
                    
        return accuracy, riverBattles

    async def seperate(self, allBattles):
        dBB = []
        aBB = []
        pvp = []
        duel = []
        for i in allBattles:
            if i['type'] == 'riverRaceDuel':
                duel.append(i)
            elif i['type'] == 'riverRacePvP':
                pvp.append(i)
            elif i['type'] == 'boatBattle':
                if "startingTrophies" in i['team'][0]:
                    aBB.append(i)
                else:
                    dBB.append(i)
        return dBB, aBB, pvp, duel

    async def calc_fame(self, cards):
        fame = 0
        for card in cards:
            if card['maxLevel'] == 13:
                fame += card['level']
            if card['maxLevel'] == 11:
                fame += card['level'] + 2
            if card['maxLevel'] == 8:
                fame += card['level'] + 5
            if card['maxLevel'] == 5:
                fame += card['level'] + 8
        return fame
                

    async def add_fame(self, battles):

        for battle in battles:
            if battle['type'] == 'boatBattle':
                if battle['team'][0]['crowns'] > 0:
                    battle['fame'] = 2 * (await self.calc_fame(battle['team'][0]['cards']))
                else:
                    battle['fame'] = await self.calc_fame(battle['team'][0]['cards'])
            elif battle['type'] == 'riverRacePvP':
                if battle['team'][0]['crowns'] > battle['opponent'][0]['crowns']:
                    battle['fame'] = 2 * (await self.calc_fame(battle['team'][0]['cards']))
                else:
                    battle['fame'] = await self.calc_fame(battle['team'][0]['cards'])

        return battles

    async def tot(self, battles):
        tot = 0
        for battle in battles:
            if battle['type'] == 'boatBattle':
                if battle['team'][0]['crowns'] > 0:
                    tot += 2 * (await self.calc_fame(battle['team'][0]['cards']))
                else:
                    tot += await self.calc_fame(battle['team'][0]['cards'])
            elif battle['type'] == 'riverRacePvP':
                if battle['team'][0]['crowns'] > battle['opponent'][0]['crowns']:
                    tot += 2 * (await self.calc_fame(battle['team'][0]['cards']))
                else:
                    tot += await self.calc_fame(battle['team'][0]['cards'])

        return tot
        

    @commands.command(name="Swardata", aliases=['swd'])
    @checks.mod_or_permissions()
    async def simple_wardata(
        self,
        ctx: commands.Context,
        clankey: str,
        threshold: int = 500,
    ):
        """Audit for the last war in a simplified form"""
        guild = ctx.guild
        valid_keys = [k["nickname"].lower() for k in self.family_clans.values()]
        if clankey.lower() not in valid_keys:
            return await simple_embed(
                ctx,
                "Please use a valid clanname:\n{}".format(
                    humanize_list(list(valid_keys))
                ),
                False,
            )

        # Get requirements for clan to approve
        for name, data in self.family_clans.items():
            if data.get("nickname").lower() == clankey.lower():
                clan_info = data
        clan_name = clan_info.get("name")
        tag = clan_info.get("tag")

        url = f"https://api.clashroyale.com/v1/clans/%23{tag}/currentriverrace"

        race_data = json.loads(((requests.get(url, headers = headers)).content).decode("utf-8"))["clans"]
#        pages = []
        
        for clan in race_data:
            if clan['tag'] == f'#{tag}':
                p_list = clan['participants']
                p_noboth = []
                p_noT = []
                p_yesT = []
                for p in p_list:
                    famerepair = p['fame'] + p['repairPoints']
                    p['famerepair'] = famerepair
                    if famerepair == 0:
                        p_noboth.append(p)
                    elif famerepair < threshold:
                        p_noT.append(p)
                    else: 
                        p_yesT.append(p)
        await ctx.send(f"**Current RiverRace details for {clan_name} (#{tag})**")                
        if 0 < len(p_noboth) < 20:
            e_noboth = discord.Embed(title = f"**No Fame or Repair**", color = 0xFAA61A)
            e_noboth.set_footer(text=credits, icon_url=credits_icon)

            for i in p_noboth:        
                e_noboth.add_field(name=f"{i['name']} ({i['tag']})",
                                value=f"<:famehammer3:750978996740685835> {i['famerepair']}",
                                inline=True)
            await ctx.send(embed=e_noboth)
            
        elif len(p_noboth) > 20:
            e_noboth = discord.Embed(title = f"**No Fame or Repair**", color = 0xFAA61A)
            e_noboth2 = discord.Embed(title = f"**No Fame or Repair**", color = 0xFAA61A)
            e_noboth.set_footer(text=credits, icon_url=credits_icon)
            e_noboth2.set_footer(text=credits, icon_url=credits_icon)


            count = 0
            for i in p_noboth:
                if count < 20:
                    e_noboth.add_field(name=f"{i['name']} ({i['tag']})",
                                    value=f"<:famehammer3:750978996740685835> {i['famerepair']}",
                                    inline=True)   
                    count += 1
                else: 
                    e_noboth2.add_field(name=f"{i['name']} ({i['tag']})",
                                    value=f"<:famehammer3:750978996740685835> {i['famerepair']}",
                                    inline=True)
                    
            await ctx.send(embed=e_noboth)
            await ctx.send(embed=e_noboth2)
        
        
        if 0 < len(p_noT) < 20:
            e_noT = discord.Embed(title = f"**Under Threshold**", color=0xff4d00)
            e_noT.set_footer(text=credits, icon_url=credits_icon)

            for i in p_noT:
                e_noT.add_field(name=f"{i['name']} ({i['tag']})",
                                value=f"<:famehammer3:750978996740685835> {i['famerepair']}",
                                inline=True)
            await ctx.send(embed=e_noT)
                
        elif len(p_noT) > 20:
            e_noT = discord.Embed(title = f"**Under Threshold**", color=0xff4d00)
            e_noT2 = discord.Embed(title = f"**Under Threshold**", color=0xff4d00)
            e_noT.set_footer(text=credits, icon_url=credits_icon)
            e_noT2.set_footer(text=credits, icon_url=credits_icon)

            count = 0
            for i in p_noT:
                if count < 20:
                    e_noT.add_field(name=f"{i['name']} ({i['tag']})",
                                    value=f"<:famehammer3:750978996740685835> {i['famerepair']}",
                                    inline=True)   
                    count += 1
                else: 
                    e_noT2.add_field(name=f"{i['name']} ({i['tag']})",
                                    value=f"<:famehammer3:750978996740685835> {i['famerepair']}",
                                    inline=True)
                    
            await ctx.send(embed=e_noT)
            await ctx.send(embed=e_noT2)
        
        
        if 0 < len(p_yesT) < 20:
            e_yesT = discord.Embed(title = f"**Above Threshold**", color=0x12b525)
            e_yesT.set_footer(text=credits, icon_url=credits_icon)

            for i in p_yesT:
                e_yesT.add_field(name=f"{i['name']} ({i['tag']})",
                                value=f"<:famehammer3:750978996740685835> {i['famerepair']}",
                                inline=True)
                
            await ctx.send(embed=e_yesT)
            
            
        elif len(p_yesT) > 20:
            e_yesT = discord.Embed(title = f"**Good Bois**", color=0x12b525)
            e_yesT2 = discord.Embed(title = f"**Good Bois**", color=0x12b525)
            e_yesT.set_footer(text=credits, icon_url=credits_icon)
            e_yesT2.set_footer(text=credits, icon_url=credits_icon)

            count = 0
            for i in p_yesT:
                if count < 20:
                    e_yesT.add_field(name=f"{i['name']} ({i['tag']})",
                                    value=f"<:famehammer3:750978996740685835> {i['famerepair']}",
                                    inline=True)   
                    count += 1
                else: 
                    e_yesT2.add_field(name=f"{i['name']} ({i['tag']})",
                                    value=f"<:famehammer3:750978996740685835> {i['famerepair']}",
                                    inline=True)
            await ctx.send(embed=e_yesT)
            await ctx.send(embed=e_yesT2)

#        return await menu(ctx, pages, DEFAULT_CONTROLS, timeout=60)

    @commands.command(name="wardata", aliases=['wd'])
    @checks.admin_or_permissions()
    async def detail_wardata(
        self,
        ctx: commands.Context,
        clankey: str,
        threshold: Optional[int] = 500,
    ):

        """Audit for the last war in a detailed form featuring each players aquirable battle log and last seen data"""

        Pages = []
        guild = ctx.guild
        valid_keys = [k["nickname"].lower() for k in self.family_clans.values()]
        if clankey.lower() not in valid_keys:
            return await simple_embed(
                ctx,
                "Please use a valid clanname:\n{}".format(
                    humanize_list(list(valid_keys))
                ),
                False,
            )

        for name, data in self.family_clans.items():
            if data.get("nickname").lower() == clankey.lower():
                clan_info = data
        tag = clan_info.get("tag")

        url = f"https://api.clashroyale.com/v1/clans/%23{tag}/currentriverrace"
        clan = json.loads(((requests.get(url, headers = headers)).content).decode("utf-8"))["clan"]

        pList = clan['participants']
        noboth = []
        Tminus = []
        Tplus = []

        for p in pList:
            p['total'] = p['fame'] + p['repairPoints']
            if p['total'] == 0:
                noboth.append(p)
            elif p['total'] < threshold:
                Tminus.append(p)
            else:
                Tplus.append(p)

        url2 = f"https://api.clashroyale.com/v1/clans/%23{tag}"
        clandata = json.loads(((requests.get(url2, headers = headers)).content).decode("utf-8"))
        pList2 = clandata["memberList"]

        clanEmbed = discord.Embed(title = f"{clandata['name']} ({clandata['tag']})",
                                description = f"{clandata['description']}",
                                color = 0xD4AF37)

        clanEmbed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{str(legends[clandata['tag'].strip('#')][1])}.png?v=1")
        clanEmbed.set_footer(text=credits, icon_url=credits_icon)
        clanEmbed.add_field(name="Members", value="<:members:685013097530130453> {}/50".format(clandata["members"]), inline=True)
        clanEmbed.add_field(name="Donations", value="<:cards:685013098670850078> {:,}".format(clandata["donationsPerWeek"]), inline=True)
        clanEmbed.add_field(name="Score", value="<:PB:685013097684926472> {:,}".format(clandata["clanScore"]), inline=True)
        clanEmbed.add_field(name="War Trophies",
                        value="<:cwtrophy:685172750129823759> {:,}".format(clandata["clanWarTrophies"]), inline=True)
        clanEmbed.add_field(name="Required Trophies",
                        value="<:crtrophy:685013098801004544> {:,}".format(clandata["requiredTrophies"]), inline=True)
        clanEmbed.add_field(name="Status", value=":envelope_with_arrow: {}".format(self.camelToString(clandata["type"]).capitalize()), inline=True)

        
        embed = discord.Embed(title="No Fame/Repair Points", color = 0xff0000)
        embed.set_footer(text=credits, icon_url=credits_icon)
        Pages.append(embed)

        for i in noboth:
            trophy = 0
            for j in pList2:
                if i['tag'] == j['tag']:
                    lastseen = await self.clean_time(j["lastSeen"])
                    donation = j['donations']
                    level = 'level'+str(j['expLevel'])
                    trophy = j['trophies']
            if trophy != 0:        
                embed = discord.Embed(description = f"**Trophies:** {tab} **Donations:** \n<:crtrophy:685013098801004544> {trophy}{tab*2}<:cards:685013098670850078> {donation}", timestamp = lastseen, color = 0xff0000)
                embed.set_author(name= f"{i['name']} ({i['tag']})", icon_url= f"https://cdn.discordapp.com/emojis/{self.emoji(level)}.png?v=1")
                embed.set_footer(text="Last Seen")
                if 'finishTime' in clan:
                    accuracy, battles = await self.get_riverBattles(i['tag'].strip('#'), await self.clean_time(clan['finishTime']))
                else:
                    accuracy, battles = await self.get_riverBattles(i['tag'].strip('#'), int(0))
                dBB, aBB, pvp, duel = await self.seperate(battles)
                embed.add_field(name= "<:cw2:751746305830682644> __River Stats__ <:cw2:751746305830682644>",
                                value= f"**Fame & Repair:{tab}Total:**\n<:fame:685013098540564502> {i['fame']} \u200B <:repair:750646558483284020> {i['repairPoints']}{tab*3}<:famehammer3:750978996740685835>{i['fame']+i['repairPoints']}", inline=False)
                if accuracy == True: 
                    
                    for l in duel:
                        embed.add_field(name= "<:duel:751728648347844669> River Race Duel <:duel:751728648347844669>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in pvp:
                        embed.add_field(name= "<:PvP:751729032218935339> River Race 1v1 <:PvP:751729032218935339>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in aBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Attack <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in dBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Defense <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                else:
                    embed.add_field(name="⚠INACCURACY ALERT⚠", value= f'{tab}')

                    for l in duel:
                        embed.add_field(name= "<:duel:751728648347844669> River Race Duel <:duel:751728648347844669>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in pvp:
                        embed.add_field(name= "<:PvP:751729032218935339> River Race 1v1 <:PvP:751729032218935339>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in aBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Attack <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in dBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Defense <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                Pages.append(embed)

        embed = discord.Embed(title="Under Threshold", color=0xff4d00)
        embed.set_footer(text=credits, icon_url=credits_icon)
        Pages.append(embed)

        for i in Tminus:
            trophy = 0
            for j in pList2:
                if i['tag'] == j['tag']:
                    lastseen = await self.clean_time(j["lastSeen"])
                    donation = j['donations']
                    level = 'level'+str(j['expLevel'])
                    trophy = j['trophies']
            if trophy != 0:        
                embed = discord.Embed(description = f"**Trophies:** {tab} **Donations:** \n<:crtrophy:685013098801004544> {trophy}{tab*2}<:cards:685013098670850078> {donation}", timestamp =lastseen, color = 0xff4d00)
                embed.set_author(name= f"{i['name']} ({i['tag']})", icon_url= f"https://cdn.discordapp.com/emojis/{self.emoji(level)}.png?v=1")
                embed.set_footer(text="Last Seen")
                if 'finishTime' in clan:
                    accuracy, battles = await self.get_riverBattles(i['tag'].strip('#'), await self.clean_time(clan['finishTime']))
                else:
                    accuracy, battles = await self.get_riverBattles(i['tag'].strip('#'), int(0))
                    dBB, aBB, pvp, duel = await self.seperate(battles)
                embed.add_field(name= "<:cw2:751746305830682644> __River Stats__ <:cw2:751746305830682644>",
                                value= f"**Fame & Repair:{tab}Total:**\n<:fame:685013098540564502> {i['fame']} \u200B <:repair:750646558483284020> {i['repairPoints']}{tab*2}<:famehammer3:750978996740685835>{i['fame']+i['repairPoints']}", inline=False)
                if accuracy == True: 
                    
                    for l in duel:
                        embed.add_field(name= "<:duel:751728648347844669> River Race Duel <:duel:751728648347844669>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in pvp:
                        embed.add_field(name= "<:PvP:751729032218935339> River Race 1v1 <:PvP:751729032218935339>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in aBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Attack <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in dBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Defense <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                else:
                    embed.add_field(name="⚠INACCURACY ALERT⚠", value= f'{tab}')

                    for l in duel:
                        embed.add_field(name= "<:duel:751728648347844669> River Race Duel <:duel:751728648347844669>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in pvp:
                        embed.add_field(name= "<:PvP:751729032218935339> River Race 1v1 <:PvP:751729032218935339>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in aBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Attack <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in dBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Defense <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                Pages.append(embed)

        embed = discord.Embed(title="Above Threshold", color=0x12b525)
        embed.set_footer(text=credits, icon_url=credits_icon)
        Pages.append(embed)

        for i in Tplus:
            trophy = 0
            for j in pList2:
                if i['tag'] == j['tag']:
                    lastseen = await self.clean_time(j["lastSeen"])
                    donation = j['donations']
                    level = 'level'+str(j['expLevel'])
                    trophy = j['trophies']
            if trophy != 0:        
                embed = discord.Embed(description = f"**Trophies:** {tab} **Donations:** \n<:crtrophy:685013098801004544> {trophy}{tab*2}<:cards:685013098670850078> {donation}", timestamp =lastseen, color=0x12b525)
                embed.set_author(name= f"{i['name']} ({i['tag']})", icon_url= f"https://cdn.discordapp.com/emojis/{self.emoji(level)}.png?v=1")
                embed.set_footer(text="Last Seen")
                if 'finishTime' in clan:
                    accuracy, battles = await self.get_riverBattles(i['tag'].strip('#'), await self.clean_time(clan['finishTime']))
                else:
                    accuracy, battles = await self.get_riverBattles(i['tag'].strip('#'), int(0))
                dBB, aBB, pvp, duel = await self.seperate(battles)
                embed.add_field(name= "<:cw2:751746305830682644> __River Stats__ <:cw2:751746305830682644>",
                                value= f"**Fame & Repair:{tab}Total:**\n<:fame:685013098540564502> {i['fame']} \u200B <:repair:750646558483284020> {i['repairPoints']}{tab*2}<:famehammer3:750978996740685835>{i['fame']+i['repairPoints']}", inline=False)
                if accuracy == True: 
                    
                    for l in duel:
                        embed.add_field(name= "<:duel:751728648347844669> River Race Duel <:duel:751728648347844669>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in pvp:
                        embed.add_field(name= "<:PvP:751729032218935339> River Race 1v1 <:PvP:751729032218935339>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in aBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Attack <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in dBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Defense <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                else:
                    embed.add_field(name="⚠INACCURACY ALERT⚠", value= f'{tab}')

                    for l in duel:
                        embed.add_field(name= "<:duel:751728648347844669> River Race Duel <:duel:751728648347844669>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in pvp:
                        embed.add_field(name= "<:PvP:751729032218935339> River Race 1v1 <:PvP:751729032218935339>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in aBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Attack <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    for l in dBB:
                        embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Defense <:boatB:751728931010248724>",
                                        value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                Pages.append(embed)
        await ctx.send(embed=clanEmbed)
        return await menu(ctx, Pages, DEFAULT_CONTROLS, timeout=60)


    @commands.command(name="Pwardata", aliases=['pwd'])
    @checks.admin()
    async def player_wardata(self, ctx, member: discord.Member = None, account: int = 1):

        """Player's perfomance in the last war, data based on available battle log"""

        threshold = 0
        Pages = []
        if member is None:
            member = ctx.author

        if member is not None:
            try:
                player_tag = self.tags.getTag(member.id, account)
                ptag = player_tag
                if player_tag is None:
                    await ctx.send(
                        "You must associate a tag with this member first using "
                        "``{}save #tag @member``".format(ctx.prefix)
                    )
                    return
                player_data = await self.clash.get_player(player_tag)
                player_trophies = player_data.trophies
                player_cards = player_data.cards
                player_pb = player_data.best_trophies
                player_maxwins = player_data.challenge_max_wins
                player_wd_wins = player_data.warDayWins

                if player_data.clan is None:
                    player_clanname = "*None*"
                    return await ctx.send("This player is not in a clan")
                else:
                    tag = player_data.clan.tag.strip('#')
                    player_clanname = player_data.clan.name

                ign = player_data.name
            # REMINDER: Order is important. RequestError is base exception class.
            except clashroyale.NotFoundError:
                return await ctx.send("Player tag is invalid.")
            except clashroyale.RequestError:
                return await ctx.send(
                    "Error: cannot reach Clash Royale Servers. "
                    "Please try again later."
                )   

        url = f"https://api.clashroyale.com/v1/clans/%23{tag}/currentriverrace"
        clan = json.loads(((requests.get(url, headers = headers)).content).decode("utf-8"))["clan"]

        pList = clan['participants']
        noboth = []
        Tminus = []
        Tplus = []
        for p in pList:
            p['total'] = p['fame'] + p['repairPoints']
            if p['total'] == 0:
                noboth.append(p)
            elif p['total'] < threshold:
                Tminus.append(p)
            else:
                Tplus.append(p)

        url2 = f"https://api.clashroyale.com/v1/clans/%23{tag}"
        clandata = json.loads(((requests.get(url2, headers = headers)).content).decode("utf-8"))
        pList2 = clandata["memberList"] 

        for i in pList:
            if i['tag'] =='#'+ptag:
                trophy = 0
                for j in pList2:
                    if i['tag'] == j['tag']:
                        lastseen = await self.clean_time(j["lastSeen"])
                        donation = j['donations']
                        level = 'level'+str(j['expLevel'])
                        trophy = j['trophies']
                if trophy != 0:        
                    embed = discord.Embed(description = f"**Trophies:** {tab} **Donations:** \n<:crtrophy:685013098801004544> {trophy}{tab*2}<:cards:685013098670850078> {donation}", timestamp = lastseen)
                    embed.set_author(name= f"{i['name']} ({i['tag']})", icon_url= f"https://cdn.discordapp.com/emojis/{self.emoji(level)}.png?v=1")
                    embed.set_footer(text="Last Seen")
                    if 'finishTime' in clan:
                        accuracy, battles = await self.get_riverBattles(i['tag'].strip('#'), await self.clean_time(clan['finishTime']))
                    else:
                        accuracy, battles = await self.get_riverBattles(i['tag'].strip('#'), int(0))
                    dBB, aBB, pvp, duel = await self.seperate(battles)
                    embed.add_field(name= "<:cw2:751746305830682644> __River Stats__ <:cw2:751746305830682644>",
                                    value= f"**Fame & Repair:{tab}Total:**\n<:fame:685013098540564502> {i['fame']} \u200B <:repair:750646558483284020> {i['repairPoints']}{tab*3}<:famehammer3:750978996740685835>{i['fame']+i['repairPoints']}", inline=False)
                    if accuracy == True: 
                        
                        for l in duel:
                            embed.add_field(name= "<:duel:751728648347844669> River Race Duel <:duel:751728648347844669>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in pvp:
                            embed.add_field(name= "<:PvP:751729032218935339> River Race 1v1 <:PvP:751729032218935339>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in aBB:
                            embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Attack <:boatB:751728931010248724>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in dBB:
                            embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Defense <:boatB:751728931010248724>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    else:
                        embed.add_field(name="⚠INACCURACY ALERT⚠", value= f'{tab}')

                        for l in duel:
                            embed.add_field(name= "<:duel:751728648347844669> River Race Duel <:duel:751728648347844669>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in pvp:
                            embed.add_field(name= "<:PvP:751729032218935339> River Race 1v1 <:PvP:751729032218935339>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in aBB:
                            embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Attack <:boatB:751728931010248724>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in dBB:
                            embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Defense <:boatB:751728931010248724>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)
                    return await ctx.send(embed=embed)
                else:
                    await ctx.send("`UNKNOWN ERROR`")

    @commands.command(name="Pydata", aliases=['pyd'])
    @checks.admin()
    async def player_Ydata(self, ctx, member: discord.Member = None, account: int = 1):

        """Player's perfomance in the last 24 hours, data based on available battle log"""

        threshold = 0
        Pages = []
        if member is None:
            member = ctx.author

        if member is not None:
            try:
                player_tag = self.tags.getTag(member.id, account)
                ptag = player_tag
                if player_tag is None:
                    await ctx.send(
                        "You must associate a tag with this member first using "
                        "``{}save #tag @member``".format(ctx.prefix)
                    )
                    return
                player_data = await self.clash.get_player(player_tag)
                player_trophies = player_data.trophies
                player_cards = player_data.cards
                player_pb = player_data.best_trophies
                player_maxwins = player_data.challenge_max_wins
                player_wd_wins = player_data.warDayWins

                if player_data.clan is None:
                    player_clanname = "*None*"
                    return await ctx.send("This player is not in a clan")
                else:
                    tag = player_data.clan.tag.strip('#')
                    player_clanname = player_data.clan.name

                ign = player_data.name
            # REMINDER: Order is important. RequestError is base exception class.
            except clashroyale.NotFoundError:
                return await ctx.send("Player tag is invalid.")
            except clashroyale.RequestError:
                return await ctx.send(
                    "Error: cannot reach Clash Royale Servers. "
                    "Please try again later."
                )   

        url = f"https://api.clashroyale.com/v1/clans/%23{tag}/currentriverrace"
        clan = json.loads(((requests.get(url, headers = headers)).content).decode("utf-8"))["clan"]

        pList = clan['participants']
        noboth = []
        Tminus = []
        Tplus = []
        for p in pList:
            p['total'] = p['fame'] + p['repairPoints']
            if p['total'] == 0:
                noboth.append(p)
            elif p['total'] < threshold:
                Tminus.append(p)
            else:
                Tplus.append(p)

        url2 = f"https://api.clashroyale.com/v1/clans/%23{tag}"
        clandata = json.loads(((requests.get(url2, headers = headers)).content).decode("utf-8"))
        pList2 = clandata["memberList"] 

        for i in pList:
            if i['tag'] =='#'+ptag:
                trophy = 0
                for j in pList2:
                    if i['tag'] == j['tag']:
                        lastseen = await self.clean_time(j["lastSeen"])
                        donation = j['donations']
                        level = 'level'+str(j['expLevel'])
                        trophy = j['trophies']
                if trophy != 0:        
                    embed = discord.Embed(description = f"**Trophies:** {tab} **Donations:** \n<:crtrophy:685013098801004544> {trophy}{tab*2}<:cards:685013098670850078> {donation}", timestamp = lastseen)
                    embed.set_author(name= f"{i['name']} ({i['tag']})", icon_url= f"https://cdn.discordapp.com/emojis/{self.emoji(level)}.png?v=1")
                    embed.set_footer(text="Last Seen")
                    if 'finishTime' in clan:
                        accuracy, battles = await self.get_lastriverBattles(i['tag'].strip('#'), await self.clean_time(clan['finishTime']))
                    else:
                        accuracy, battles = await self.get_lastriverBattles(i['tag'].strip('#'), int(0))
                    dBB, aBB, pvp, duel = await self.seperate(battles)
                    embed.add_field(name= "<:cw2:751746305830682644> __River Stats__ <:cw2:751746305830682644>",
                                    value= f"**Fame & Repair:{tab}Total:**\n<:fame:685013098540564502> {i['fame']} \u200B <:repair:750646558483284020> {i['repairPoints']}{tab*3}<:famehammer3:750978996740685835>{i['fame']+i['repairPoints']}", inline=False)
                    if accuracy == True: 
                        
                        for l in duel:
                            embed.add_field(name= "<:duel:751728648347844669> River Race Duel <:duel:751728648347844669>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in pvp:
                            embed.add_field(name= "<:PvP:751729032218935339> River Race 1v1 <:PvP:751729032218935339>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in aBB:
                            embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Attack <:boatB:751728931010248724>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in dBB:
                            embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Defense <:boatB:751728931010248724>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                    else:
                        embed.add_field(name="⚠INACCURACY ALERT⚠", value= f'{tab}')

                        for l in duel:
                            embed.add_field(name= "<:duel:751728648347844669> River Race Duel <:duel:751728648347844669>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in pvp:
                            embed.add_field(name= "<:PvP:751729032218935339> River Race 1v1 <:PvP:751729032218935339>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in aBB:
                            embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Attack <:boatB:751728931010248724>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)

                        for l in dBB:
                            embed.add_field(name= "<:boatB:751728931010248724> Boat Battle Defense <:boatB:751728931010248724>",
                                            value = f"<:blueCrown:685013097173352452> {l['team'][0]['crowns']} - {l['opponent'][0]['crowns']} <:redCrown:685013097408233503>", inline = False)
                    return await ctx.send(embed=embed)
                else:
                    await ctx.send("`UNKNOWN ERROR`")



    @commands.command()
    @checks.mod_or_permissions()
    async def draw(
        self,
        ctx: commands.Context,
        clankey: str,
        threshold: Optional[int] = 500,
        number: Optional[int] = 1,
    ):

        """Draws a number of players above the threshold value based randomly (Probability based on their activity in the past war)"""

        guild = ctx.guild
        valid_keys = [k["nickname"].lower() for k in self.family_clans.values()]
        if clankey.lower() not in valid_keys:
            return await simple_embed(
                ctx,
                "Please use a valid clanname:\n{}".format(
                    humanize_list(list(valid_keys))
                ),
                False,
            )

        # Get requirements for clan to approve
        for name, data in self.family_clans.items():
            if data.get("nickname").lower() == clankey.lower():
                clan_info = data
        clan_name = clan_info.get("name")
        tag = clan_info.get("tag") 

        url = f"https://api.clashroyale.com/v1/clans/%23{tag}/currentriverrace"
        plist = json.loads(((requests.get(url, headers = headers)).content).decode("utf-8"))["clan"]['participants']
        raffle = {}
        details = {}
        if 0 > number > 25:
            await ctx.send("You can only draw 25 winners")
            return
        entry = 0
        for i in plist:
            i['total'] = i['fame'] + i['repairPoints']
            if i['total'] >= threshold:
                tempEntry = i['total'] // 100
                details[i['tag']] = [tempEntry,i['name']]
                raffle[i['tag']] = tempEntry

        choice = list(raffle.keys())
        weight = list(raffle.values())      
        if number > len(choice):
            await ctx.send(f"There is only {len(choice)} choices to choose from. Please try again with a less number of winners.")
            return
        embed = discord.Embed(title="Winners", color=0x12b525)
        embed.set_footer(text=credits, icon_url=credits_icon)
        for winner in range(1,number+1):
            win = random.choices(choice,weights=weight)[0]
            choice.remove(win)
    
            weight.remove(raffle[win])
            embed.add_field(name=details[win][1],value=f"Chances: {details[win][0]}")
        await ctx.send(embed=embed)
