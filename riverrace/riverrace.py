from redbot.core import commands, Config, checks
import discord
import requests
import time
import json
from datetime import datetime


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
         'YLULCRQJ' : ['LeGeND Pride!'   , 738642598243074138 , 750749679771451563]
         }  

key = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjllODA1YmVlLTYzNjItNDVmNy04Y2E1LTMzMWM0NTA1Y2RiYSIsImlhdCI6MTU5OTA1NTM5MCwic3ViIjoiZGV2ZWxvcGVyLzFiYjYxZDk0LTA2NWMtNzJmNi05NmM0LWQwMDY4MDM3NzNjZCIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyIxOC4yMjIuMTMxLjk3Il0sInR5cGUiOiJjbGllbnQifV19.hqovGFRcG0OoYk9f2nwgzXtxcat3L6fUDi7EU1Q2b2Bh_R2eB8JkOU44OdPKMVC8zPNnZPbfrgYfsMtQDjsQtA'
headers = {
          'Accept': 'application/json',
          'Authorization': f'Bearer {key}'
          }

class RiverRace(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        
        
    @commands.command()
    @checks.is_owner()
    async def run(self, ctx):

        for legend in legends:
            message = await ctx.fetch_message(legends[legend][2])
            url = f"https://api.clashroyale.com/v1/clans/%23{legend}/currentriverrace"
            
            embed = discord.Embed(title = f"**{legends[legend][0]} (#{legend})**", color = 0xFAA61A, url = f'https://royaleapi.com/clan/{legend}/war/race', timestamp = datetime.now())
            embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{str(legends[legend][1])}.png?v=1")
            embed.set_author(name="Legend Gaming", url="https://royaleapi.com/clan/family/legend/clans", icon_url="https://media.discordapp.net/attachments/423094817371848716/425389610223271956/legend_logo-trans.png")
            embed.set_footer(text="Bot by Legend Gaming", icon_url="https://images-ext-1.discordapp.net/external/9Xc8I4QRQMnltwDfm2dpj_lb9On3egSt_Il9TC_xeN8/%3Fv%3D1/https/cdn.discordapp.com/emojis/709796075581735012.gif")

          
            
            race_data = json.loads(((requests.get(url, headers = headers)).content).decode("utf-8"))["clans"]

            
            standings = sorted(race_data, key=lambda k: k['fame'], reverse=True) 
            for clan in standings:
                if clan['fame'] < 50000:
                    embed.add_field(name=f"{clan['name']} ({clan['tag']})",
                            value=f"<:cwtrophy:685172750129823759> {clan['clanScore']}     <:repair:750646558483284020> {clan['repairPoints']}     <:fame:685013098540564502> {clan['fame']}",
                            inline=False)
                else:
                    embed.add_field(name=f"✅{clan['name']} ({clan['tag']})",
                            value=f"<:cwtrophy:685172750129823759> {clan['clanScore']}     <:repair:750646558483284020> {clan['repairPoints']}     <:fame:685013098540564502> 50000",
                            inline=False)
            await message.edit(embed=embed)
