import discord
from redbot.core import commands, Config, checks
from redbot.core.utils.embed import randomize_colour
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from random import choice
import clashroyale
from typing import Union

class ClashRoyaleCog(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2512325)
        default_user = {"tag" : None, "nick" : None}
        self.config.register_user(**default_user)
        default_guild = {"clans" : {}}
        self.config.register_guild(**default_guild)
        
    async def initialize(self):
        crapikey = await self.bot.get_shared_api_tokens("crapi")
        if crapikey["api_key"] is None:
            raise ValueError("The Clash Royale API key has not been set.")
        self.crapi = clashroyale.OfficialAPI(crapikey["api_key"], is_async=True)

    def badEmbed(self, text):
        bembed = discord.Embed(color=0xff0000)
        bembed.set_author(name=text, icon_url="https://i.imgur.com/FcFoynt.png")
        return bembed
        
    def goodEmbed(self, text):
        gembed = discord.Embed(color=0x45cafc)
        gembed.set_author(name=text, icon_url="https://i.imgur.com/qYmbGK6.png")
        return gembed
    
    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.channel.id == 698556920830754939 and msg.author.id != 599286708911210557:
            try:
                id = int(msg.content)
                user = self.bot.get_user(int(msg.content))
                if user is None:
                    await (self.bot.get_channel(698556920830754939)).send(".")
                tag = await self.config.user(user).tag()
                if tag is None:
                    await (self.bot.get_channel(698556920830754939)).send(".")
                else:
                    await (self.bot.get_channel(698556920830754939)).send(tag.upper())
            except ValueError:
                pass

    @commands.command()
    async def crsave(self, ctx, tag, member: discord.Member = None):
        """Save your Clash Royale player tag"""
        if member == None:
            member = ctx.author        
        
        tag = tag.lower().replace('O', '0')
        if tag.startswith("#"):
            tag = tag.strip('#')

        try:
            player = await self.crapi.get_player("#" + tag)
            await self.config.user(member).tag.set(tag)
            await self.config.user(member).nick.set(player.name)
            await ctx.send(embed = self.goodEmbed("CR account {} was saved to {}".format(player.name, member.name)))
            
        except clashroyale.NotFoundError as e:
            await ctx.send(embed = self.badEmbed("No player with this tag found, try again!"))

        except clashroyale.RequestError as e:
            await ctx.send(embed = self.badEmbed(f"CR API is offline, please try again later! ({str(e)})"))
        
        except Exception as e:
            await ctx.send("**Something went wrong, please send a personal message to LA Modmail bot or try again!**")
            
    @commands.has_permissions(administrator = True) 
    @commands.command()
    async def crunsave(self, ctx, member: discord.Member):
        await self.config.user(member).clear()
        await ctx.send("Done.")
           
    @commands.command(aliases=['rcr'])
    async def renamecr(self, ctx, member:discord.Member=None):
        await ctx.trigger_typing()
        prefix = ctx.prefix
        member = ctx.author if member is None else member
        
        tag = await self.config.user(member).tag()
        if tag is None:
            return await ctx.send(embed = self.badEmbed(f"This user has no tag saved! Use {prefix}crsave <tag>"))
        
        player = await self.crapi.get_player(tag)
        nick = f"{player.name} | {player.clan.name}" if player.clan is not None else f"{player.name}"
        try:
            await member.edit(nick=nick[:31])
            await ctx.send(f"Done! New nickname: `{nick[:31]}`")
        except discord.Forbidden:
            await ctx.send(f"I dont have permission to change nickname of this user!")
        except Exception as e:
            await ctx.send(f"Something went wrong: {str(e)}")
            
    @commands.command(aliases=['crp'])
    async def crprofile(self, ctx, member:Union[discord.Member, str]=None):
        """Clash Royale profile"""
        await ctx.trigger_typing()
        prefix = "/"
        tag = ""

        member = ctx.author if member is None else member

        if isinstance(member, discord.Member):
            tag = await self.config.user(member).tag()
            if tag is None:
                return await ctx.send(embed = self.badEmbed(f"This user has no tag saved! Use {prefix}crsave <tag>"))
        elif isinstance(member, str) and member.startswith("<"):
            id = member.replace("<", "").replace(">", "").replace("@", "").replace("!", "")
            try:
                member = discord.utils.get(ctx.guild.members, id=int(id))
                if member is not None:
                    tag = await self.config.user(member).tag()
                    if tag is None:
                        return await ctx.send(embed = self.badEmbed(f"This user has no tag saved! Use {prefix}crsave <tag>"))
            except ValueError:
                pass
        elif isinstance(member, str) and member.startswith("#"):
            tag = member.upper().replace('O', '0')
        elif isinstance(member, str):
            try:
                member = discord.utils.get(ctx.guild.members, id=int(member))
                if member is not None:
                    tag = await self.config.user(member).tag()
                    if tag is None:
                        return await ctx.send(embed = self.badEmbed(f"This user has no tag saved! Use {prefix}crsave <tag>"))
            except ValueError:
                member = discord.utils.get(ctx.guild.members, name=member)
                if member is not None:
                    tag = await self.config.user(member).tag()
                    if tag is None:
                        return await ctx.send(embed = self.badEmbed(f"This user has no tag saved! Use {prefix}crsave <tag>"))

        if tag is None or tag == "":
            desc = "/profile\n/profile @user\n/profile discord_name\n/profile discord_id\n/profile #CRTAG"
            embed = discord.Embed(title="Invalid argument!", colour=discord.Colour.red(), description=desc)
            return await ctx.send(embed=embed)
        try:
            player = await self.crapi.get_player(tag)
            chests = await self.crapi.get_player_chests(tag)
            
        except clashroyale.NotFoundError:
            return await ctx.send(embed = self.badEmbed("No clan with this tag found, try again!"))

        except clashroyale.RequestError as e:
            return await ctx.send(embed = self.badEmbed(f"CR API is offline, please try again later! ({str(e)})"))
        
        except Exception as e:
            return await ctx.send("**Something went wrong, please send a personal message to LA Modmail bot or try again!****")


        embed=discord.Embed()
        embed.set_author(name=f"{player.name} {player.tag}", icon_url="https://i.imgur.com/Qs0Ter9.png")
        embed.add_field(name="Trophies", value=f"<:trophycr:587316903001718789>{player.trophies}")
        embed.add_field(name="Highest Trophies", value=f"<:nicertrophy:587565339038973963>{player.bestTrophies}")
        embed.add_field(name="Level", value=f"<:level:451064038420381717>{player.expLevel}")
        embed.add_field(name="Arena", value=f"<:training:587566327204544512>{player.arena.name}")
        embed.add_field(name="Star Points", value=f"<:starpoints:737613015242768397>{player.starPoints}")
        if player.clan is not None:
            clanbadge = discord.utils.get(self.bot.emojis, name = str(player.clan.badgeId))
            embed.add_field(name="Clan", value=f"{clanbadge}{player.clan.name}")
            embed.add_field(name="Role", value=f"<:social:451063078096994304>{player.role.capitalize()}")
        embed.add_field(name="Total Games Played", value=f"<:swords:449650442033430538>{player.battleCount}")
        embed.add_field(name="Wins/Losses", value=f"<:starcr:587705837817036821>{player.wins}/{player.losses}")
        embed.add_field(name="Three Crown Wins", value=f"<:crownblue:449649785528516618>{player.threeCrownWins}")
        embed.add_field(name="War Day Wins", value=f"<:cw_win:449644364981993475>{player.warDayWins}")
        embed.add_field(name="Clan Cards Collected", value=f"<:cw_cards:449641339580317707>{player.clanCardsCollected}")
        embed.add_field(name="Max Challenge Wins", value=f"<:tournament:587706689357217822>{player.challengeMaxWins}")
        embed.add_field(name="Challenge Cards Won", value=f"<:cardcr:587702597855477770>{player.challengeCardsWon}")
        embed.add_field(name="Tournament Games Played", value=f"<:swords:449650442033430538>{player.tournamentBattleCount}")
        embed.add_field(name="Tournament Cards Won", value=f"<:cardcr:587702597855477770>{player.tournamentCardsWon}")
        if player.currentFavouriteCard is not None:
            embed.add_field(name="Favourite Card", value=f"<:epic:587708123087634457>{player.currentFavouriteCard.name}")
        embed.add_field(name="Total Donations", value=f"<:deck:451062749565550602>{player.totalDonations}")

        chests_msg = ""
        i = 0
        for chest in chests:
            emoji = discord.utils.get(self.bot.emojis, name = str(chest.name.lower().replace(" ", "")))
            chests_msg += f"{emoji}`{chest.index}`"
            if i == 8:
                chests_msg +="X"
            i+=1
        embed.add_field(name="Upcoming Chests", value=chests_msg.split("X")[0], inline=False)
        embed.add_field(name="Rare Chests", value=chests_msg.split("X")[1], inline=False)
        await ctx.send(embed=randomize_colour(embed))
        
        
    @commands.guild_only()
    @commands.group(aliases=['clan'], invoke_without_command=True)
    async def clans(self, ctx, key:str=None):
        """View all clans saved in this server"""
        offline = False
        prefix = ctx.prefix
        await ctx.trigger_typing()

        if key == "forceoffline":
            offline = True
            key = None

        if key is not None and key != "forceoffline":
            try:
                if key.startswith("<"):
                    memberid = key.replace("<", "").replace(">", "").replace("@", "").replace("!", "")
                    member = discord.utils.get(ctx.guild.members, id=int(memberid))
                    if member is not None:
                        mtag = await self.config.user(member).tag()
                        if mtag is None:
                            return await ctx.send(embed = self.badEmbed(f"This user has no tag saved! Use {prefix}crsave <tag>"))

                        try:
                            player = await self.crapi.get_player(mtag)
                            tag = player.clan.tag
                        except clashroyale.RequestError as e:
                            await ctx.send(embed = self.badEmbed(f"CR API is offline, please try again later! ({str(e)})"))
                else:
                    tag = await self.config.guild(ctx.guild).clans.get_raw(key.lower(), "tag", default=None)
                    if tag is None:
                        return await ctx.send(embed = self.badEmbed(f"{key.title()} isn't crsaved clan in this server!"))
                try:
                    clan = await self.crapi.get_clan(tag)
                    clan = clan.raw_data
                
                except clashroyale.RequestError as e:
                    await ctx.send(embed = self.badEmbed(f"CR API is offline, please try again later! ({str(e)})"))
                    return
                
                badge = discord.utils.get(self.bot.emojis, name = str(clan['badgeId']))
                embed=discord.Embed(title=f"{badge}{clan['name']} ({clan['tag']})", description=f"```{clan['description']}```")
                embed.add_field(name="Members", value=f"<:people:449645181826760734> {clan['members']}/50")
                embed.add_field(name="Required Trophies", value= f"<:trophycr:587316903001718789> {str(clan['requiredTrophies'])}")
                embed.add_field(name="Score", value= f"<:crstar:449647025999314954> {str(clan['clanScore'])}")
                embed.add_field(name="Clan War Trophies", value= f"<:cw_trophy:449640114423988234> {str(clan['clanWarTrophies'])}")
                embed.add_field(name="Type", value= f"<:bslock:552560387279814690> {clan['type'].title()}".replace("only", " Only"))
                embed.add_field(name="Location", value=f":earth_africa: {clan['location']['name']}")
                embed.add_field(name="Average Donations Per Week", value= f"<:deck:451062749565550602> {str(clan['donationsPerWeek'])}")
                return await ctx.send(embed=randomize_colour(embed))            
                
            except Exception as e:
                return await ctx.send("**Something went wrong, please send a personal message to LA Modmail bot or try again!**")
        
        if len((await self.config.guild(ctx.guild).clans()).keys()) < 1:
            return await ctx.send(embed = self.badEmbed(f"This server has no clans saved. Save a clan by using {ctx.prefix}clans add!"))
                                
        try:
            try:
                clans = []
                for key in (await self.config.guild(ctx.guild).clans()).keys():
                    clan = await self.crapi.get_clan(await self.config.guild(ctx.guild).clans.get_raw(key, "tag"))
                    clans.append(clan.raw_data)
            except clashroyale.RequestError as e:
                offline = True
            
            embedFields = []
            
            if not offline:
                clans = sorted(clans, key=lambda sort: (sort['requiredTrophies'], sort['clanScore']), reverse=True)
                
                for i in range(len(clans)):   
                    cemoji = discord.utils.get(self.bot.emojis, name = str(clans[i]['badgeId']))
                    key = ""
                    for k in (await self.config.guild(ctx.guild).clans()).keys():
                        if clans[i]['tag'].replace("#", "") == await self.config.guild(ctx.guild).clans.get_raw(k, "tag"):
                            key = k
                    
                    await self.config.guild(ctx.guild).clans.set_raw(key, 'lastMemberCount', value=clans[i]['members'])            
                    await self.config.guild(ctx.guild).clans.set_raw(key, 'lastRequirement', value=clans[i]['requiredTrophies'])   
                    await self.config.guild(ctx.guild).clans.set_raw(key, 'lastScore', value=clans[i]['clanScore'])               
                    await self.config.guild(ctx.guild).clans.set_raw(key, 'lastPosition', value=i)               
                    await self.config.guild(ctx.guild).clans.set_raw(key, 'lastBadgeId', value=clans[i]['badgeId'])   
                    await self.config.guild(ctx.guild).clans.set_raw(key, 'warTrophies', value=clans[i]['clanWarTrophies'])   
                   
                    info = await self.config.guild(ctx.guild).clans.get_raw(key, "info", default="")
                    e_name = f"{str(cemoji)} {clans[i]['name']} [{key}] ({clans[i]['tag']}) {info}"
                    e_value = f"<:people:449645181826760734>`{clans[i]['members']}` <:trophycr:587316903001718789>`{clans[i]['requiredTrophies']}+` <:crstar:449647025999314954>`{clans[i]['clanScore']}` <:cw_trophy:449640114423988234>`{clans[i]['clanWarTrophies']}`"
                    embedFields.append([e_name, e_value])
            
            else:
                offclans = []
                for k in (await self.config.guild(ctx.guild).clans()).keys():
                    offclans.append([await self.config.guild(ctx.guild).clans.get_raw(k, "lastPosition"), k])
                offclans = sorted(offclans, key=lambda x: x[0])
                                
                for clan in offclans:
                    ckey = clan[1]
                    cscore = await self.config.guild(ctx.guild).clans.get_raw(ckey, "lastScore")
                    cname = await self.config.guild(ctx.guild).clans.get_raw(ckey, "name")
                    ctag = await self.config.guild(ctx.guild).clans.get_raw(ckey, "tag")
                    cinfo = await self.config.guild(ctx.guild).clans.get_raw(ckey, "info")
                    cmembers = await self.config.guild(ctx.guild).clans.get_raw(ckey, "lastMemberCount")
                    creq = await self.config.guild(ctx.guild).clans.get_raw(ckey, "lastRequirement")
                    ccw = await self.config.guild(ctx.guild).clans.get_raw(ckey, "warTrophies")        
                    cemoji = discord.utils.get(self.bot.emojis, name = str(await self.config.guild(ctx.guild).clans.get_raw(ckey, "lastBadgeId")))
                    
                    e_name = f"{cemoji} {cname} [{ckey}] (#{ctag}) {cinfo}"
                    e_value = f"<:people:449645181826760734>`{cmembers}` <:trophycr:587316903001718789>`{creq}+` <:crstar:449647025999314954>`{cscore}` <:cw_trophy:449640114423988234>`{ccw}`"
                    embedFields.append([e_name, e_value])
            
            colour = choice([discord.Colour.green(), discord.Colour.blue(), discord.Colour.purple(), discord.Colour.orange(), discord.Colour.red(), discord.Colour.teal()])
            embedsToSend = []                
            for i in range(0, len(embedFields), 8):
                embed = discord.Embed(colour=colour)
                embed.set_author(name=f"{ctx.guild.name} clans", icon_url=ctx.guild.icon_url)
                footer = "API is offline, showing last saved data." if offline else f"Do you need more info about a clan? Use {ctx.prefix}clan [key]"
                embed.set_footer(text = footer)
                for e in embedFields[i:i+8]:
                    embed.add_field(name=e[0], value=e[1], inline=False)
                embedsToSend.append(embed)
             
            async def next_page(ctx: commands.Context, pages: list, controls: dict, message: discord.Message, page: int, timeout: float, emoji: str):
                perms = message.channel.permissions_for(ctx.me)
                if perms.manage_messages:
                    try:
                        await message.remove_reaction(emoji, ctx.author)
                    except discord.NotFound:
                        pass
                if page == len(pages) - 1:
                    page = 0
                else:
                    page = page + 1
                return await menu(ctx, pages, controls, message=message, page=page, timeout=timeout)                  
            if len(embedsToSend) > 1:                   
                await menu(ctx, embedsToSend, {"➡": next_page} , timeout=300)
            else:
                await ctx.send(embed=embedsToSend[0])
                                
        except Exception as e:
            return await ctx.send("**Something went wrong, please send a personal message to LA Modmail bot or try again!**")
                                
                                
    @commands.guild_only()
    @commands.has_permissions(administrator = True) 
    @clans.command(name="add")
    async def clans_add(self, ctx, key : str, tag : str):
        """
        Add a clan to /clans command
        key - key for the clan to be used in other commands
        tag - in-game tag of the clan
        """
        await ctx.trigger_typing()
        if tag.startswith("#"):
            tag = tag.strip('#').upper().replace('O', '0')
        
        if key in (await self.config.guild(ctx.guild).clans()).keys():
            return await ctx.send(embed = self.badEmbed("This clan is already saved!"))

        try:
            clan = await self.crapi.get_clan(tag)
            clan = clan.raw_data
            result = {
                "name" : clan['name'],
                "nick" : key.title(),
                "tag" : clan['tag'].replace("#", ""),
                "lastMemberCount" : clan['members'],
                "lastRequirement" : clan['requiredTrophies'],
                "lastScore" : clan['clanScore'],
                "info" : "",
                "warTrophies" : clan['clanWarTrophies']
                }
            key = key.lower()
            await self.config.guild(ctx.guild).clans.set_raw(key, value=result)
            await ctx.send(embed = self.goodEmbed(f"{clan['name']} was successfully saved in this server!"))

        except clashroyale.NotFoundError as e:
            await ctx.send(embed = self.badEmbed("No clan with this tag found, try again!"))

        except clashroyale.RequestError as e:
            await ctx.send(embed = self.badEmbed(f"CR API is offline, please try again later! ({str(e)})"))

        except Exception as e:
            return await ctx.send("**Something went wrong, please send a personal message to LA Modmail bot or try again!**")
                                                  
    @commands.guild_only()
    @commands.has_permissions(administrator = True)
    @clans.command(name="remove")
    async def clans_remove(self, ctx, key : str):
        """
        Remove a clan from /clans command
        key - key for the clan used in commands
        """
        await ctx.trigger_typing()
        key = key.lower()
        
        try:
            name = await self.config.guild(ctx.guild).clans.get_raw(key, "name")
            await self.config.guild(ctx.guild).clans.clear_raw(key)
            await ctx.send(embed = self.goodEmbed(f"{name} was successfully removed from this server!"))
        except KeyError:
            await ctx.send(embed = self.badEmbed(f"{key.title()} isn't saved clan!"))

    @commands.guild_only()
    @commands.has_permissions(administrator = True)
    @clans.command(name="info")
    async def clans_info(self, ctx, key : str, *, info : str = ""):
        """Edit clan info"""
        await ctx.trigger_typing()
        try:
            await self.config.guild(ctx.guild).clans.set_raw(key, "info", value=info)
            await ctx.send(embed = self.goodEmbed("Clan info successfully edited!"))
        except KeyError:
            await ctx.send(embed = self.badEmbed(f"{key.title()} isn't saved clan in this server!"))

    @commands.command()
    @commands.guild_only()
    async def refreshLAFC(self, ctx, member:discord.Member=None):
        if member == None:
            member = ctx.author
        msg = ""
        try:
            tag = await self.config.user(member).tag()
            player = await self.crapi.get_player("#" + tag)
            nick = f"{player.name} | {player.clan.name}" if player.clan is not None else f"{player.name}"
            try:
                await member.edit(nick=nick[:31])
                msg += f"Nickname changed: {nick[:31]}\n"
            except discord.Forbidden:
                msg += f":exclamation:Couldn't change nickname of this user. ({nick[:31]})\n"
            trophyRole = None
            if player.trophies >= 8000:
                trophyRole = member.guild.get_role(600325526007054346)
            elif player.trophies >= 7000:
                trophyRole = member.guild.get_role(594960052604108811)
            elif player.trophies >= 6000:
                trophyRole = member.guild.get_role(594960023088660491)
            elif player.trophies >= 5000:
                trophyRole = member.guild.get_role(594959970181709828)
            elif player.trophies >= 4000:
                trophyRole = member.guild.get_role(594959895904649257)
            elif player.trophies >= 3000:
                trophyRole = member.guild.get_role(598396866299953165)
            if trophyRole is not None:
                try:
                    await member.add_roles(trophyRole)
                    msg += f"Assigned roles: {trophyRole.name}\n"
                except discord.Forbidden:
                    msg += f":exclamation:Couldn't change roles of this user. ({trophyRole.name})\n"
            if player.challengeMaxWins >= 20:
                try:
                    wins20Role = member.guild.get_role(593776990604230656)
                    await member.add_roles(wins20Role)
                    msg += f"Assigned roles: {wins20Role.name}\n"
                except discord.Forbidden:
                    msg += f":exclamation:Couldn't change roles of this user. ({wins20Role.name})\n"

        except clashroyale.NotFoundError as e:
            msg += "No player with this tag found, try again!\n"
        except ValueError as e:
            msg += f"**{str(e)}\nTry again or send a personal message to LA Modmail! ({str(e)})**\n"
        except clashroyale.RequestError as e:
            msg += f"Clash Royale API is offline, please try again later! ({str(e)})\n"
        except Exception as e:
            msg += f"**Something went wrong, please send a personal message to LA Modmail or try again! ({str(e)})**\n"
        await ctx.send(embed=discord.Embed(description=msg, colour=discord.Colour.blue()))

    @commands.command()
    @commands.guild_only()
    async def userbytagcr(self, ctx, tag: str):
        """Find user with a specific tag saved"""
        tag = tag.lower().replace('O', '0')
        if tag.startswith("#"):
            tag = tag.strip('#')

        for user in (await self.config.all_users()):
            person = self.bot.get_user(user)
            if person is not None:
                if (await self.config.user(person).tag()) == tag:
                    return await ctx.send(f"This tag belongs to **{str(person)}**.")
        await ctx.send("This tag is either not saved or invalid.")
