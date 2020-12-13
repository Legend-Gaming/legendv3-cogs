import discord
import os
import time
import calendar
import asyncio
import clashroyale
from math import ceil

from redbot.core import Config
from redbot.core import checks, commands
from redbot.core import bank
from redbot.core.utils import chat_formatting
from discord.utils import get
from discord import client
from datetime import datetime
from datetime import timezone 
from redbot.core.utils.chat_formatting import box, humanize_number
from redbot.core.utils.menus import close_menu, menu, DEFAULT_CONTROLS

"""This is a port of GR8's duel cog with some modifications.
   Original cog: https://github.com/Gr8z/Legend-Cogs/tree/master/duels """

# Possible TODO's: 
# 1. Card ban
# 2. Roles for Rank
    
credits="Bot by Legend Gaming"
credits_url = "https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1"

guild_defaults = {
    "mincreds" : 0,
    "active" : 0,
    "player1" : 0,
    "player2" : 0,
    "bet" : 0,
    "time" : 0,
    "accept_timeout" : 180,
    "battle_timeout" : 600,
    "role_id" : 0,
    "private" : 0,
    "private_member_id" : 0
}

member_defaults = {
    "tag" : "",
    "wins" : 0,
    "score" : 0,
    "lifetimewins" : 0,
}

ist_time_diff_in_sec = 19800
max_score = 10000

class NoToken(Exception):
    pass
    
class Duel(commands.Cog):
    """Clash Royale Duels """

    def __init__(self, bot):
        self.bot = bot
                
        self.database = Config.get_conf(self, identifier=7894561230, force_registration=True)
        self.database.register_member(**member_defaults)
        self.database.register_guild(**guild_defaults)
        self.token_task = self.bot.loop.create_task(self.crtoken())
    
    async def crtoken(self):
        """ Set Clash royale API token""" 
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token.get("token") is None:
            log.error("CR Token is not SET."
                "Use [p]set api clashroyale token,YOUR_TOKEN to set it" )
            raise NoToken
        self.clash = clashroyale.official_api.Client(
            token=token["token"], is_async=True, url="https://proxy.royaleapi.dev/v1"
        )
    
    def cog_unload(self):
        if self.token_task:
            self.token_task.cancel()
        if self.clash:
            self.bot.loop.create_task(self.clash.close())
    
    
    async def elo_rating(self, A, B, score, k=32):
        """Calculate the new Elo rating for a player"""

        exp = 1 / (1 + 10 ** ((B - int(A)) / 400))
        return max(0, int(A + k * (score - exp)))
        
    async def cleanTime(self, time):
        """Converts time to timestamp"""
        return int(datetime.strptime(time, '%Y%m%dT%H%M%S.%fZ').timestamp()) + ist_time_diff_in_sec
        
    @commands.group()
    async def duel(self, ctx):
        """Duel in clash royale..."""
        pass    
                
    @duel.command()  
    @checks.is_owner()  
    async def deletedata(self, ctx):
        """ Delete all data of all members"""
        
        await self.database.clear_all_members()
        await ctx.send("Deleted.")
    
    @duel.command(name="reset")
    @checks.is_owner()
    async def duel_reset(self, ctx):
        """Rest wins and score of users"""
        
        data =  await self.database.all_members(ctx.guild)

        for acc in data:
            user_id = acc    
            member = discord.utils.get(ctx.guild.members, id=user_id)
            if member == None:
                pass
            else:
                await self.database.member(member).wins.set(0)
                await self.database.member(member).score.set(0)
        
        await ctx.send("Wins and scores of all members have been reset.")
        
    @duel.command(name="mincreds")
    @checks.admin()
    async def setmincreds(self, ctx, val: int):
        """Sets min creds for duels"""
        
        await self.database.guild(ctx.guild).mincreds.set(val)
        await ctx.send(" Guild minimum credits set to {}.".format(str(val)))
    
    @duel.command(name="register")
    async def savetag(self, ctx, tag:str, user: discord.Member = None):
        """Save tag and Register user for duel"""
        
        if user == None:
            user = ctx.author
            
        tag = tag.strip('#')            
        await self.database.member(user).tag.set(tag.upper())
        await ctx.send("Tag {} saved to {}. Verify using: ```{}duel verify```".format(str(tag), str(user.display_name), str(ctx.prefix)))
        
    @duel.command(name="verify")
    async def verifytag(self, ctx, user:discord.member =None):
        """Displays name of account belonging to saved tag"""
        
        if user == None:
            user = ctx.author
        
        pfp = user.avatar_url    
        saved_tag = await self.database.member(user).tag()
        if saved_tag == "":
            await ctx.send("No tag saved")
            return

        try:
            player_data = await self.clash.get_player(saved_tag)
            player_name = player_data.name
            player_trophy = player_data.trophies
            player_pb = player_data.best_trophies   
            
            if player_data.clan == None:
                player_clan = "None"
            else:
                player_clan = player_data.clan.name
                
        except AttributeError:
            return await ctx.send("Hmm an attribute error. Pls contact striker")
        except clashroyale.NotFoundError:
            return await ctx.send("Player tag is invalid.")
        except clashroyale.RequestError:
            return await ctx.send("Error: cannot reach Clash Royale Servers. "
                "Please try again later.")
        
        
        profile_txt = "{}'s profile ({})".format(str(player_name),str(saved_tag))
        embed = discord.Embed(title=profile_txt, color=discord.Color.green())
        embed.set_thumbnail(url=pfp)
        embed.set_footer(text=credits, icon_url=credits_url)
        
        embed.add_field(name="Trophy        ", value=str(player_trophy))
        embed.add_field(name="Personal Best ", value=str(player_pb))
        embed.add_field(name="Clan          ", value=player_clan)
               
        await ctx.send(embed=embed)  
    
    @duel.command(name="clear")
    @checks.admin()
    async def duel_clear(self, ctx):
        """Clear active duel stats"""
        
        await self.database.guild(ctx.guild).active.set(0)
        await self.database.guild(ctx.guild).player1.set(0)
        await self.database.guild(ctx.guild).player2.set(0)
        await self.database.guild(ctx.guild).bet.set(0)
        await self.database.guild(ctx.guild).time.set(0)
        await self.database.guild(ctx.guild).private.set(0)
        await self.database.guild(ctx.guild).private_member_id.set(0)
        await ctx.send("Duel has been cleared.")

    @duel.command(name="ongoing")
    @checks.admin()
    async def ongoing_duel(self, ctx):
        """See status of ongoing duel"""
        is_active = await self.database.guild(ctx.guild).active()
        player1_id = await self.database.guild(ctx.guild).player1()
        player2_id = await self.database.guild(ctx.guild).player2()        
        user_tag1 = ""
        user_tag2 = ""
        player1 = ""
        player2 = ""
        
        if player1_id == 0:
            player1 = ""
        else:
            member1 = discord.utils.get(ctx.guild.members, id=player1_id)
            if member1 == None:
                await ctx.send("Player not found in database. ??")
                return 0
            player1 = member1.name
            user_tag1 = await self.database.member(member1).tag()
            
        if player2_id == 0:
            player2 = ""
        else:
            member2 = discord.utils.get(ctx.guild.members, id=player2_id)
            if member2 == None:
                await ctx.send("Player not found in database. ??")
                return 0
            player2 = member2.name
            user_tag2 = await self.database.member(member2).tag()            

        is_private = await self.database.guild(ctx.guild).private()
        if is_private:
            private_text = "yes"
        else:
            private_text = "no"
                                        
        bet_amt = await self.database.guild(ctx.guild).bet()
        
        await ctx.send("```Active = {}\nPlayer1 = {}\nPlayer2 = {}\
        \nTag1 = {}\nTag2 = {}\nBet = {}\nPrivate = {}```".format(str(is_active), str(player1), 
        str(player2), str(user_tag1), str(user_tag2), str(bet_amt), str(private_text)))
                
    @duel.command(name="start")
    async def duel_start(self, ctx, bet: int, member: discord.Member=None):
        """Start a duel with bets"""
        
        user = ctx.author            
            
        min_creds = await self.database.guild(ctx.guild).mincreds()
        is_active = await self.database.guild(ctx.guild).active()
        user_tag = await self.database.member(user).tag()
        duel_role = await self.database.guild(ctx.guild).role_id()            
        accept_time = await self.database.guild(ctx.guild).accept_timeout()
        
        if is_active == 1:
            await ctx.send("Another duel is in progress. Pls wait till its over. \
            \nIf its an error, pls ask an admin to clear it using {}duel clear".format(str(ctx.prefix)))
            return 0        
        
        if bet < min_creds:
            await ctx.send("Bet is lower than guild minimum of {}.".format(str(min_creds)))
            return 0
            
        balance = await bank.get_balance(user)
        if bet > balance:
            await ctx.send("You dont have that much credits to duel.")
            return 0
            
        if user_tag == "":
            await ctx.send("Save your tag first using ```{}duel register <tag>```".format(str(ctx.prefix)))
            return 0
              
        if duel_role == 0:
            duel_role_name = ""
        else:
            duel_role_name  = get(ctx.guild.roles, id=(int)(duel_role))
            duel_role_name = duel_role_name.mention
        
        if member == user:
            await ctx.send("Real funny trying to challenge yourself")
            return 0
            
        #if its a private duel, then there is no need to mention the role
        if member == None:
            await ctx.send("{} {} is looking to duel for {}.\nTo accept challenge, use {}duel accept"
            "\nThis duel request will timeout in {} seconds".format( str(duel_role_name), 
            str(ctx.author.display_name), str(bet), str(ctx.prefix), str(accept_time)), allowed_mentions=discord.AllowedMentions(roles=True))
            
        else:
            await self.database.guild(ctx.guild).private.set(1)
            #set player 2 id so that only that player may accept the duel
            await self.database.guild(ctx.guild).private_member_id.set(member.id)

            await ctx.send("{} is looking to duel {} for {}.\nTo accept challenge, use {}duel accept"
            "\nThis duel request will timeout in {} seconds".format( str(ctx.author.display_name), 
            str(member.display_name), str(bet), str(ctx.prefix), str(accept_time)))
            
        
        await self.database.guild(ctx.guild).active.set(1)
        await self.database.guild(ctx.guild).player1.set(ctx.author.id)
        await self.database.guild(ctx.guild).bet.set(bet)  
        start_time = (int)(time.time())   
        await self.database.guild(ctx.guild).time.set(start_time)
        
        #timeout mechanism
        #await asyncio.sleep(accept_time)
        
        timeout_start = time.time()
        while time.time() < timeout_start + accept_time:
            is_active = await self.database.guild(ctx.guild).active()
            if is_active == 0:
                return 0
            await asyncio.sleep(5)
    
        player2_id = await self.database.guild(ctx.guild).player2()     
        if player2_id == 0:
            await ctx.send("No on accepted the challenge.")
            await self.duel_clear(ctx)
            return
        
    @duel.command(name="accept")
    async def duel_accept(self, ctx):
        """Accept the ongoing duel"""
        
        is_active = await self.database.guild(ctx.guild).active()
        user_tag = await self.database.member(ctx.author).tag()
        is_private = await self.database.guild(ctx.guild).private()
        
        if is_active == 0:
            await ctx.send("There is no ongoing duel. To start duel use {}duel start".format(str(ctx.prefix)))
            return 0
        
        if user_tag == "":
            await ctx.send("Save your tag first using ```{}duel register <tag>```".format(ctx.prefix))
            return 0
            
        player1_id = await self.database.guild(ctx.guild).player1()
        
        if player1_id == ctx.author.id:
            await ctx.send("You cannot duel yourself.")
            return 0

        bet = await self.database.guild(ctx.guild).bet()
        balance = await bank.get_balance(ctx.author)
        if bet > balance:
            await ctx.send("You dont have that much credits to duel.")
            return 0
        
        if is_private:
            private_id = await self.database.guild(ctx.guild).private_member_id()
            
            if ctx.author.id == private_id   :
                pass
            else:
                await ctx.send("The duel is a private one, intended for someone else")
                return 0
                
        await self.database.guild(ctx.guild).player2.set(ctx.author.id)

        start_time = (int)(time.time())
        await self.database.guild(ctx.guild).time.set(start_time)

        member1 = discord.utils.get(ctx.guild.members, id=player1_id)
        if member1 == None:
            await ctx.send("Player 1 not in database")
            return 0
                    

        battle_timeout = await self.database.guild(ctx.guild).battle_timeout()
                
        await ctx.send("Lets begin the duel between {} and {} for {} credits."
        "\nRemember that the duel will reset in {} seconds".format(
        str(member1.mention), str(ctx.author.mention), str(bet), str(battle_timeout)))      

        timeout_start = time.time()
        while time.time() < timeout_start + battle_timeout:
            is_active = await self.database.guild(ctx.guild).active()
            if is_active == 0:
                return 0
            await asyncio.sleep(5)
    
        is_active = await self.database.guild(ctx.guild).active()
        if is_active == 0:
            return 0
            
        await ctx.send("Checking results and closing duel...")
            
        member1 = discord.utils.get(ctx.guild.members, id=player1_id)
        if member1 == None:
            await ctx.send("Player 1 not in database")
            return 0
                    
        tag = await self.database.member(member1).tag()
        
        ret = await self.check_result(ctx, member1, ctx.author, tag, user_tag, bet)

        if ret == 2:
            await self.duel_clear(ctx)
        

    @duel.command(name="cancel")
    async def duel_cancel(self, ctx):
        """Cancel ongoing duel"""
        
        is_active = await self.database.guild(ctx.guild).active()
        player1_id = await self.database.guild(ctx.guild).player1()
        player2_id = await self.database.guild(ctx.guild).player2()
                        
        #allow to cancel only if no one accepts it                
        if player2_id == 0:
            if player1_id == ctx.author.id:
                await self.duel_clear(ctx)
                return 0
            else:
                await ctx.send("Only duel initiator may cancel the duel.")
                return 0
        else:
            battle_timeout = await self.database.guild(ctx.guild).battle_timeout()
            await ctx.send("Duel has been accepted. Duel will timeout in {} seconds.\n"
            "Or ask an admin to clear using {}duel clear".format(
            str(battle_timeout), str(ctx.prefix)))
            
            
    @duel.command(name="claim")
    async def duel_claim(self, ctx):
        """Claim your winning from duel"""
        
        is_active = await self.database.guild(ctx.guild).active()
        player1_id = await self.database.guild(ctx.guild).player1()
        player2_id = await self.database.guild(ctx.guild).player2()

        member1 = discord.utils.get(ctx.guild.members, id=player1_id)
        member2 = discord.utils.get(ctx.guild.members, id=player2_id)
        
        bet = await self.database.guild(ctx.guild).bet()

        if is_active == 0:
            await ctx.send("There is no ongoing duel.")
            return 0
            
        if member1 == 0 or member2 == 0:
            await ctx.send("Duel was not initiated/accepted.")
            return 0
            
        if member1 == None:
            await ctx.send("Player1 is missing in database ? ")
            return 0

        if member2 == None:
            await ctx.send("Player2 is missing in database ? ")
            return 0
            
        user_tag1 = await self.database.member(member1).tag()
        user_tag2 = await self.database.member(member2).tag()        
                                   
        if player1_id == ctx.author.id:
            pass
        elif player2_id == ctx.author.id:
            pass
        else:
            await ctx.send("You are not part of the ongoing duel.")
            return 0            
            
        bet = await self.database.guild(ctx.guild).bet()    
        await self.check_result(ctx, member1, member2, user_tag1, user_tag2, bet)
        

    async def check_result(self, ctx, member1, member2, user_tag1, user_tag2, bet):
        """Check results of duel."""
        
        try:
            profiledata = await self.clash.get_player_battles(user_tag1)
        except clashroyale.RequestError:
            return await self.bot.say("Error: cannot reach Clash Royale Servers. Please try again later.")

        start_time = await self.database.guild(ctx.guild).time()
        msg = ""
        print("set time : " + str(start_time))
        for battle in profiledata:
            st_time = await self.cleanTime(battle.battle_time)
            print(st_time)
            if(  st_time > start_time and battle.opponent[0].tag.strip('#') == user_tag2 ) :          
                print(battle)
                res = battle.team[0].crowns - battle.opponent[0].crowns
                
                if (res > 0):
                    await ctx.send("{} won the duel against {}.".format(member1.mention, member2.mention))
                    await self.set_results(ctx, member1, member2, bet)
                    await self.duel_clear(ctx)
                    return 1
                elif res == 0 :
                    await ctx.send("Match Tied.")
                    await self.duel_clear(ctx)                    
                    return 1
                else:
                    await ctx.send("{} lost the duel against {}.".format(member1.mention, member2.mention))
                    await self.set_results(ctx, member2, member1, bet)
                    await self.duel_clear(ctx)                    
                    return 1
                    
        await ctx.send("Didnt find the results")        
        return 2
        
    async def set_results(self, ctx, member1, member2, bet):
        """Set Results for the duels"""
        await bank.withdraw_credits(member2, bet)
        await bank.deposit_credits(member1, bet)
        await ctx.send("{} credits transferred from {} to {}".format(bet, member2.name, member1.name))
        
        user_wins = await self.database.member(member1).wins()
        user_lifetimewins = await self.database.member(member1).lifetimewins()
        user_score1 = await self.database.member(member1).score()
        user_score2 = await self.database.member(member2).score()
        
        updated_score1 = await self.elo_rating(user_score1, user_score2, 1)
        updated_score2 = await self.elo_rating(user_score2, user_score1, 0)
                
        await self.database.member(member1).score.set(updated_score1)
        await self.database.member(member2).score.set(updated_score2)                
        await self.database.member(member1).wins.set(user_wins+1)
        await self.database.member(member1).lifetimewins.set(user_lifetimewins+1)        
        
       
       
    @duel.command(name="stats")
    async def duel_stats(self, ctx, member: discord.Member=None):
        """Show duel stats of a user"""
        
        if member == None:
            user = ctx.author
        else:
            user = member
        
        user_tag = await self.database.member(user).tag()
        user_wins = await self.database.member(user).wins()
        user_lifetimewins = await self.database.member(user).lifetimewins()
        user_score = await self.database.member(user).score()
        
        embed = discord.Embed(color=0x0080ff)
        embed.set_author(name=user.name + " ("+user_tag+")")
        embed.set_thumbnail(url="https://imgur.com/9DoEq22.jpg")
        embed.add_field(name="Duel Wins", value="{}".format(user_wins), inline=True)
        embed.add_field(name="Duel Score", value="{}".format(user_score), inline=True)
        embed.add_field(name="Lifetime wins", value="{}".format(user_lifetimewins), inline=True)
        embed.set_footer(text=credits, icon_url=credits_url)
    
        await ctx.send(embed=embed)  
        
    @duel.command(name="settings")
    @checks.admin()
    async def duel_settings(self, ctx):
        """Server settings for duels"""
        
        accept_timeout = await self.database.guild(ctx.guild).accept_timeout()
        battle_timeout = await self.database.guild(ctx.guild).battle_timeout()        
        min_creds = await self.database.guild(ctx.guild).mincreds()
        
        role_id = await self.database.guild(ctx.guild).role_id()
        role_name  = get(ctx.guild.roles, id=(int)(role_id))
        
        await ctx.send("```Minimum credits = {}\n"
        "Role = {}\n"
        "Accept timeout = {} seconds\n"
        "Battle timeout = {} seconds\n```".format(str(min_creds), str(role_name),
         str(accept_timeout), str(battle_timeout))) 
     
    @duel.command(name="accepttime")
    @checks.admin()
    async def duel_accept_time(self, ctx, sec:int):
        """Set cancel time for accepting a duel"""
        
        await self.database.guild(ctx.guild).accept_timeout.set(sec)
        await ctx.send("Accept time set to {} seconds.".format(str(sec)))
        
    @duel.command(name="battletime")
    @checks.admin()
    async def duel_battle_time(self, ctx, sec:int):
        """Set the timeout for duel battles"""
        
        await self.database.guild(ctx.guild).battle_timeout.set(sec)
        await ctx.send("Battle time set to {} seconds.".format(str(sec)))
    
    @duel.command(name="role")
    @checks.admin()
    async def duel_add_role(self, ctx, role_id : int):
        """Set the duel role to be pinged when someone starts duel.
        To disable, set role to 0"""
        
        if role_id == 0:
            await self.database.guild(ctx.guild).role_id.set(0)
            await ctx.send("Duel role cleared.")
            return 0
                                            
        role_name  = get(ctx.guild.roles, id=(int)(role_id))               
        if role_name == None:
            await ctx.send("Not a valid role.")
            return 1
            
        await self.database.guild(ctx.guild).role_id.set(role_id)
        await ctx.send("Duel role set to {}.".format(role_name))
         
    """
    @duel.command(name="test")
    async def test(self, ctx, member_id: int):
        member = discord.utils.get(ctx.guild.members, id=member_id)
        if member:
            tag = await self.database.member(member).tag()
          
            return await ctx.send(f'{member.name} was found {tag}.')
        await ctx.send(f'No member on the server match the id: {member_id}.')
    """
    
    @duel.command(name="ldb")
    async def duel_ldb(self, ctx, val: str='s'):
        """Leaderboard based on score, wins or lifetimewins"""
        """val = s for score"""
        """val = w for wins"""
        """val = l for lifetimewins"""        
        
        if val not in ['s', 'w', 'l']:
            await ctx.send("Invalid value. Valid ones are: 's', 'w', 'l'")
            return 0
        
        key_param = ""
        heading = "Ranking"
        if val == 's':
            key_param = "score"
            heading = "Duel Score Ranking"
        elif val == 'w':
            key_param= "wins"
            heading = "Duel Wins Ranking"
        else:
            key_param = "lifetimewins"
            heading = "Duel Lifetime Wins Ranking"
            
        data =  await self.database.all_members(ctx.guild)
        infos = sorted(data, key=lambda x: data[x][key_param], reverse=True)
        res = []
        count = 1
        for i in infos:
            tmp = {}
            tmp["id"] = i
            cur = data[i]
            tmp[key_param] = cur[key_param]
            res.append(tmp)
            count += 1
            if count == 10:
                break
        
        #Idea and locgic from economy cog leaderboard
        try:
            key_len = len(humanize_number(res[0][key_param]))
            key_len_max = len(humanize_number(max_score))
            if key_len > key_len_max:
                key_len = key_len_max

        except IndexError:
            return await ctx.send(("There are no accounts in the duel registery."))
            
        pound_len = len(str(len(res)))
        header = "{pound:{pound_len}}{score:{key_len}}{name:2}\n".format(
            pound="#",
            name=("Name"),
            score=("Score"),
            key_len=key_len + 6,
            pound_len=pound_len + 3,
        )
        highscores = []
        pos = 1
        temp_msg = header
             
        base_embed = discord.Embed(title=(heading))
        embed_requested = await ctx.embed_requested()
        footer_message = ("Page {page_num}/{page_len}.")
        

        for acc in res:
            try:
                name = ctx.guild.get_member(acc['id']).display_name
            except AttributeError:
                user_id = ""
                if await ctx.bot.is_owner(ctx.author):
                    user_id = f"({str(acc['id'])})"
                name = f"{user_id}"
                
            score = acc[key_param]
            if score > max_score:
                score = max_score

            balance = humanize_number(score)
            if acc['id'] != ctx.author.id:
                temp_msg += (
                    f"{f'{humanize_number(pos)}.': <{pound_len+2}} "
                    f"{balance: <{key_len + 5}} {name}\n"
                )    
            
                        
            else:
                temp_msg += (
                    f"{f'{humanize_number(pos)}.': <{pound_len+2}} "
                    f"{balance: <{key_len + 5}} "
                    f"<<{ctx.author.display_name}>>\n"
                )
                
            if pos % 10 == 0:
                if embed_requested:
                    embed = base_embed.copy()
                    embed.description = box(temp_msg, lang="md")
                    embed.set_footer(
                        text=footer_message.format(
                            page_num=len(highscores) + 1,
                            page_len=ceil(len(res) / 10),
                        )
                    )
                    highscores.append(embed)
                else:
                    highscores.append(box(temp_msg, lang="md"))
                temp_msg = header
            pos += 1
            
        if temp_msg != header:
            if embed_requested:
                embed = base_embed.copy()
                embed.description = box(temp_msg, lang="md")
                embed.set_footer(
                    text=footer_message.format(
                        page_num=len(highscores) + 1,
                        page_len=ceil(len(res) / 10),
                    )
                )
                highscores.append(embed)
            else:
                highscores.append(box(temp_msg, lang="md"))
        
        if not highscores:
            await ctx.send("No data found.")
        
        if highscores:
            await menu(
                ctx,
                highscores,
                DEFAULT_CONTROLS if len(highscores) > 1 else {"\N{CROSS MARK}": close_menu},
            )

