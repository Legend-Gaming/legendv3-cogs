# -*- coding: utf-8 -*-
"""
Created on Wed Sep  2 09:30:34 2020

@author: Yasin
"""
  
from redbot.core import commands, Config, checks
import discord
import requests
import time
from bs4 import BeautifulSoup

clans = {
         '29YPJYY'  : 'Dragons Eight'   #, 
#         'Y8G9C09'  : 'Dragons Eight 2' ,
#         'VJQ0GJ0'  : 'LeGeND Legion!'  ,
#         '9PJYVVL2' : 'LeGeND Titan!'   ,
#         '9P2PQULQ' : 'LeGeND Empire!'  ,
#         'RY9QJU2'  : 'LeGeND Rising!'  ,
#         '80CC8'    : 'LeGeND Squad!'   ,
#         '2LL8LC2R' : 'LeGeND Prime!'   ,
#         '99R2PQVR' : 'LeGeND Dynasty'  ,
#         'P9GG9QQY' : 'LeGeND eSports!' ,
#         '2CJ88808' : 'LeGeND Phantom!' ,
#         'PRCRJYCR' : 'Dragons Eight 3' ,
#         'J0CQ9R9'  : 'White Plague'    ,
#         '8QRQQ8RG' : 'LeGeND Academy!' ,
#         'YLULCRQJ' : 'LeGeND Pride!'   
         }  


class RiverRace(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        
        
    @commands.command()
    @checks.is_owner()
    async def run(self, ctx):
        a = 0
        while a == 0:
            for clan in clans: 
                url = f"https://royaleapi.com/clan/{clan}/war/race"
                
                race_data = (requests.get(url)).content
                
                print(f"Clan Loaded: {clans[clan]}\n")
            
                soup = BeautifulSoup(race_data,'lxml')
                pretty = soup.prettify()
                
                standings = soup.table
                #print(standings)
                print("\n"*3)
                st_list = []
                try:
                    for td in standings.find_all("td"):
                        if td.text != "\n\n":
                            st_list.append((td.text).strip("\n"))
                    print(st_list,"\n\n")
                    
                    neat = {
                            "embed": {
                                    "title": f"**{clans[clan]} (#{clan})**",
                                    "color" : 0xFAA61A,
                                    "url" : url,
                                    "fields" : [
                                            { 
                                            "name": st_list[0],
                                            "value": f"<:cwtrophy:685172750129823759> {st_list[1]}     <:repair:750646558483284020> {st_list[2]}     <:fame:685013098540564502> {st_list[3]}",
                                            "inline": False
                                            },
                                            { 
                                            "name": st_list[4],
                                            "value": f"<:cwtrophy:685172750129823759> {st_list[5]}     <:repair:750646558483284020> {st_list[6]}     <:fame:685013098540564502> {st_list[7]}",
                                            "inline": False
                                            },
                                            { 
                                            "name": st_list[8],
                                            "value": f"<:cwtrophy:685172750129823759> {st_list[9]}     <:repair:750646558483284020> {st_list[10]}     <:fame:685013098540564502> {st_list[11]}",
                                            "inline": False
                                            },
                                            { 
                                            "name": st_list[12],
                                            "value": f"<:cwtrophy:685172750129823759> {st_list[13]}     <:repair:750646558483284020> {st_list[14]}     <:fame:685013098540564502> {st_list[15]}",
                                            "inline": False
                                            },
                                            { 
                                            "name": st_list[16],
                                            "value": f"<:cwtrophy:685172750129823759> {st_list[17]}     <:repair:750646558483284020> {st_list[18]}     <:fame:685013098540564502> {st_list[19]}",
                                            "inline": False
                                            }
                                            
                                            ]
                                    }
                                
                            }
                    embed= discord.Embed()
                    embed.from_dict(neat)
                    await ctx.send(embed=embed)
                except AttributeError:
                    await ctx.send("RoyaleAPI is down. Please wait for sometime")
                    break
                
            time.sleep(120)
            

    
    
