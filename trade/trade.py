import discord
import os

from redbot.core import Config
from redbot.core import checks, commands
from redbot.core.data_manager import bundled_data_path
from redbot.core.utils import chat_formatting
from json import load

"""This is a port of GR8's trade cog with minor modifications.
   Original cog: https://github.com/Gr8z/Legend-Cogs/tree/master/trade 
   
   Card stats need to be updated with every new card release.
   It can be found in https://royaleapi.github.io/cr-api-data/json/cards.json"""

# Possible TODO's: 
# 1. Check if user has sufficient cards to give while searching 
#    for possible traders
# 2. Suggest necessary cards for trade give option based on levels.
#    Max levels can be donated. Also cards that are not used/upgraded 
#    can also be given away.


cards_filename = "cards.json"
card_stats_filename = "card_stats.json"

token_type = ["legendary", "epic", "rare", "common"]

member_settings = {
    "want" : {
        "legendary" : [],
        "epic" : [],
        "rare" : [],
        "common" : [],
        },
    "give" : {
        "legendary" : [],
        "epic" : [],
        "rare" : [],
        "common" : [],
        },
    "token" : {
        "legendary" : False,
        "epic" : False,
        "rare" : False,
        "common" : False,
        },    
    }
    
credits="Bot by Legend Gaming"
credits_url = "https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1"

class Trade(commands.Cog):
    """Clash Royale Trading Helper"""

    def __init__(self, bot):
        self.bot = bot
        dir_path = bundled_data_path(self)
        
        file_path = os.path.join(dir_path, cards_filename)
        with open (file_path, 'r') as file:
            self.cards = load(file)
        
        file_path = os.path.join(dir_path, card_stats_filename)
        with open (file_path, 'r') as file:
            self.card_stats = load(file)

        self.database = Config.get_conf(self, identifier=7894561230, force_registration=True)
        self.database.register_member(**member_settings)
        
        # init card data
        self.cards_abbrev = {}

        for k, v in self.cards.items():
            for value in v:
                self.cards_abbrev[value] = k
            self.cards_abbrev[k] = k
            
    async def cardToRarity(self, name):
        """Card name to rarity."""
        for card in self.card_stats:
            if name == card["name"]:
                return card["rarity"]
        return None
        
    async def saveCardWant(self, member, card):
        rarity = await self.cardToRarity(card)
        rarity = rarity.lower()
        
        async with self.database.member(member).want() as want:
            if card not in want[rarity]:
                want[rarity].append(card)
              
    async def removeCardWant(self, member, card):
        rarity = await self.cardToRarity(card)
        rarity = rarity.lower()        
        
        async with self.database.member(member).want() as want:
            if card in want[rarity]:
                want[rarity].remove(card)
                        
    async def saveCardGive(self, member, card):
        rarity = await self.cardToRarity(card)
        rarity = rarity.lower() 
        
        async with self.database.member(member).give() as give:
            if card not in give[rarity]:
                give[rarity].append(card)
   
    async def removeCardGive(self, member, card):
        rarity = await self.cardToRarity(card)
        rarity = rarity.lower() 
        
        async with self.database.member(member).give() as give:
            give[rarity].remove(card)
            
    async def cardInWant(self, member, card):
        rarity = await self.cardToRarity(card)
        rarity = rarity.lower() 
        
        async with self.database.member(member).want() as want:
            if card in want[rarity]:
                return True
            else:
                return False

    async def cardInGive(self, member, card):
        rarity = await self.cardToRarity(card)
        rarity = rarity.lower() 
        
        async with self.database.member(member).give() as give:
            if card in give[rarity]:
                return True
            else:
                return False
            
    async def saveToken(self, member, token_name):
        async with self.database.member(member).token() as token:
            token[token_name] = True
        
    async def removeToken(self, member, token_type):
        async with self.database.member(member).token() as token:
            token[token_type] = False        
    
    async def searchTrades(self, card, guild):
        rarity = await self.cardToRarity(card)
        rarity = rarity.lower() 
        
        trades = {}
        members = await self.database.all_members()
   
        
        if members:
            if guild in members:
                members = members[guild]
                for player in members:
                    player_data = members[player]
                    trades[player] = [False, False, False]
                    if card in player_data['give'][rarity]:
                        trades[player][0] = True
                    if card in player_data['want'][rarity]:
                        trades[player][1] = True
                    if player_data['token'][rarity]:
                        trades[player][2] = True
    
                return trades

            else:
                print("Hmm. No guild. That was not supposed to happen! ")
                return 0                

        else:
            return 0
        
        
    async def sortTrades(self, server, author, trades):
        try:
            author_clan = author.display_name.split("|", 1)[1]
        except IndexError:
            author_clan = None
            
        token_trades = {}
        sorted1 = {}
        sorted2 = {}
        
        for player in trades:
            if player == author.id:
                continue
                    
            try:
                member = server.get_member(player)
                clan = member.display_name.split("|", 1)[1]
            except AttributeError:
                continue
            except IndexError:
                clan = None
                author_clan = None
                
            if author_clan == clan:
                token_trades[player] = trades[player]
            else:
                sorted1[player] = trades[player]
                
        for player in sorted1:
            if trades[player][2]:
                token_trades[player] = trades[player]
            else:
                sorted2[player] = trades[player]        
            
        return { **token_trades, **sorted2}
        

    @commands.group(pass_context = True, no_pm=True)
    async def trade(self, ctx):
        """ Clash Royale trade commands"""
        pass
        
    @trade.group(name="want")
    async def trade_want(self, ctx):
        """Add/Remove cards that you are looking for"""
        pass
        
    @trade_want.command(name="add")    
    async def want_add(self, ctx, *, card):
        """Add card that you are looking for"""
        
        author = ctx.message.author
        
        try:
            card = self.cards_abbrev[card]
        except KeyError:
            return await ctx.send("Error, Invalid card")
            
        if( await self.cardInGive(author, card) ):
            await ctx.send("Cannot add {} as it is present in give list.".format(card))
        else:
            await self.saveCardWant(author, card)
            await ctx.send("You are now looking for {}".format(card))
        
    @trade_want.command(name="remove")
    async def want_remove(self, ctx, *, card):
        """Remove card that you are no longer looking for"""
        
        author = ctx.message.author
        try:
            card = self.cards_abbrev[card]
        except KeyError:
            return await ctx.send("Error, Invalid card")

        await self.removeCardWant(author, card)
        await ctx.send("You are no longer looking for {}".format(card))
   
    @trade.group(name="give")
    async def trade_give(self, ctx):
        """Add/Remove cards that you would like to give away"""
        pass
    
    @trade_give.command(name="add")
    async def give_add(self, ctx, *, card):    
        """Add card that you want to give away"""        
        
        author = ctx.message.author
        
        try:
            card = self.cards_abbrev[card]
        except KeyError:
            return await ctx.send("Error, Invalid card")
    
        if( await self.cardInWant(author, card) ):
            await ctx.send("Cannot add {} as it is present in want list.".format(card))
        else:
            await self.saveCardGive(author, card)
            await ctx.send("You are now looking to donate {}".format(card))

    @trade_give.command(name="remove")
    async def give_remove(self, ctx, *, card):
        """Remove card that you no longer want to give away"""
        
        author = ctx.message.author
        try:
            card = self.cards_abbrev[card]
        except KeyError:
            return await ctx.send("Error, Invalid card")

        await self.removeCardGive(author, card)
        await ctx.send("You are no longer looking to give away {}".format(card))

        
    @trade.command(pass_context=True, no_pm=True)
    async def search(self, ctx, *, card):
        """Search for trades"""
        
        author = ctx.message.author
        server = ctx.guild
        
        try:
            card = self.cards_abbrev[card]
        except KeyError:
            return await ctx.send("Error, Invalid card")
            
        trades = await self.searchTrades(card, ctx.guild.id)
        
        if(trades == 0):
            await ctx.send("No data available in the server")
            return 0   
         
        embed = discord.Embed(color=0xFAA61A, description="We found these members who match your card search.")
        embed.set_author(name="{} Traders".format(card),
                         icon_url="https://i.imgur.com/dtSMITE.jpg")
        embed.set_thumbnail(url="https://royaleapi.github.io/cr-api-assets/cards/{}.png".format(card.replace(" ", "-").lower()))
        embed.set_footer(text=credits, icon_url=credits_url)
        
        trades = await self.sortTrades(server, author, trades)
        givers = "\u200b"
        wanters = "\u200b"
        
        for player in trades:
            try:
                if trades[player][0]:
                    member = server.get_member(player)
                    givers += "• {} ".format(member.display_name)
                    if trades[player][2]:
                        givers += "  - Token :white_check_mark: "
                    else:
                        givers += "  - Token :x: "
                    givers += "\n"
                if trades[player][1]:
                    member = server.get_member(player)
                    wanters += "• {} ".format(member.display_name)
                    if trades[player][2]:
                        wanters += "  - Token :white_check_mark: "
                    else:
                        wanters += "  - Token :x: "                        
                    wanters += "\n"    
                    
            except AttributeError:
                pass
                
        if len(givers) > 1024:
            givers = givers[:1000 - len(givers)] + "..."
        embed.add_field(name="Giving {}".format(card), value=givers + "\n\u200b", inline=False)

        if len(wanters) > 1024:
            wanters = wanters[:1000 - len(wanters)] + "..."
        embed.add_field(name="Want {}".format(card), value=wanters + "\n\u200b", inline=False)

        await ctx.send(embed=embed)                 
                   
    @trade.group(name="token")
    async def trade_token(self, ctx):
        """Add/Remove token """
        pass
    
    @trade_token.command(name="add")    
    async def token_add(self, ctx, token):
        """Add trade token"""
        
        if token in token_type:
            
            author = ctx.message.author
            token = token.lower()
        
            try:
                await self.saveToken(author, token)
            except KeyError:
                return await ctx.send("Error, Invalid token")
            
            await ctx.send("You now have a {} token".format(token))
        else:
            await ctx.send("Thats not a valid token type")
        
    @trade_token.command(name="remove")
    async def token_remove(self, ctx, token):
        """Remove trade token"""
        
        if token in token_type:
            author = ctx.message.author
            token = token.lower()
        
            try:
                await self.removeToken(author, token)
            except KeyError:
                return await ctx.send("Error, Invalid token")
            
            await ctx.send("You no longer have a {} token".format(token))
        else:
            await ctx.send("Thats not a valid token type")            
        
    @trade.command()
    async def info(self, ctx):
        """Display trade data of user"""
        
        member_data = await self.database.member(ctx.author).all()
        pfp = ctx.author.avatar_url
        
        embed = discord.Embed(color=0xFAA61A, description="Trade user info.")
        embed.set_author(name="{} ".format(ctx.author.display_name),
                         icon_url="https://i.imgur.com/dtSMITE.jpg")
        embed.set_thumbnail(url=pfp)
        embed.set_footer(text=credits, icon_url=credits_url)
       
        token = ""
        for rarity, value in member_data['token'].items():
            if member_data['token'][rarity]:
                token += "• " + str(rarity) + " :white_check_mark:" + "\n"
            else:
                token += "• " + str(rarity) + " :x:" + "\n"
                       
        cards_want = ""
        for rarity, cards in member_data['want'].items():
            if member_data['want'][rarity]:
                cards_want += "• " + chat_formatting.humanize_list(member_data['want'][rarity]) + "\n"

        cards_give =""           
        for rarity, cards in member_data['give'].items():
            if member_data['give'][rarity]:
                cards_give += "• " + chat_formatting.humanize_list(member_data['give'][rarity]) + "\n"

        if len(cards_give) > 1024:
            cards_give = cards_give[:1000 - len(cards_give)] + "..."
            
        if len(cards_want) > 1024:
            cards_want = cards_want[:1000 - len(cards_want)] + "..."
                                   
        embed.add_field(name="Token : ", value=token + "\n\u200b", inline=False)
        embed.add_field(name="Want : ", value=cards_want + "\n\u200b", inline=False)
        embed.add_field(name="Give : ", value=cards_give + "\n\u200b", inline=False)
                
        await ctx.send(embed=embed)        
        
    @trade.command()
    @checks.is_owner()
    async def deletedata(self, ctx):
        """ Delete all data of all members"""
        
        await self.database.clear_all_members()
        await ctx.send("Deleted.")
        
