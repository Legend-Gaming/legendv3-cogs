from aiohttp.helpers import HeadersMixin
from redbot.core import Config, commands, checks
import discord
import aiohttp
import asyncio
import json
from redbot.core.data_manager import bundled_data_path
import random
import string
from redbot.core.utils.chat_formatting import pagify
import asyncio


class Helper:

    @staticmethod
    def verifyTag(tag):
        """Check if a player's tag is valid

        Credit: Gr8
        """
        check = ['P', 'Y', 'L', 'Q', 'G', 'R',
                 'J', 'C', 'U', 'V', '0', '2', '8', '9']
        if len(tag) > 15:
            return False
        if any(i not in check for i in tag):
            return False

        return True

    @staticmethod
    def formatTag(tag):
        """Sanitize and format CR Tag

        Credit: Gr8
        """
        return tag.strip('#').upper().replace('O', '0')

    def roleNameConverter(role):
        """Just makes the role names look better"""
        if role == "leader":
            return "Leader of"
        elif role == "coLeader" or role == "admin":
            return "Co-Leader of"
        elif role == "elder":
            return "Elder of"
        else:
            return "Member of"


class ClashOfClans(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=5454514862456)
        self.loop = asyncio.get_event_loop()
        self.session = aiohttp.ClientSession(loop=self.loop)
        default_global = {"members": {}}
        self.config.register_global(**default_global)
        #thanks to nevus for code below
        self.path = str(bundled_data_path(self)) + "/cocclans.json"
        self.rules_path = str(bundled_data_path(self)) + "/rules.txt"
        self.esports_path = str(bundled_data_path(self)) + "/esports.txt"
        self.greetings_path = str(bundled_data_path(self)) + "/greetings.json"
        with open(self.path) as file:
            self.family_clans = dict(json.load(file))
        with open(self.rules_path) as file:
            self.rules_text = file.read()
        with open(self.esports_path) as file:
            self.esports_text = file.read()
        with open(self.greetings_path) as file:
            self.greetings = dict(json.load(file))

    async def coctoken(self):
        token = await self.bot.get_shared_api_tokens("clashofclans")
        if token['token'] is None:
            print("COC token not set")

        COCKEY = token['token']
        global HEADERS
        HEADERS = {"Authorization": f'Bearer {COCKEY}'}

    def get_emoji(self, name):
        """
        Emoji by name.
        Credits: Generaleoley
        """
        name = str(name)
        for emote in self.bot.emojis:
            if emote.name == name.replace(" ", "").replace("-", "").replace(".", ""):
                return '<:{}:{}>'.format(emote.name, emote.id)
        return ''

    def trophy_to_emoji(self, trophies):
        leagues = {
            "UnrankedLeague": [0, 399],
            "BronzeLeague": [400, 799],
            "SilverLeague": [800, 1399],
            "GoldLeague": [1400, 1999],
            "CrystalLeague": [2000, 2599],
            "MasterLeague": [2600, 3199],
            "ChampionLeague": [3200, 4099],
            "TitanLeague": [4100, 4999],
            "LegendLeague": [5000, 50000]
        }
        for league in leagues.keys():
            if leagues[league][0] <= trophies <= leagues[league][1]:
                return self.get_emoji(name=league)

    @commands.command(name="savecoc")
    async def savetagcoc(self, ctx, user_tag, user: discord.User = None):
        if user is not None and user != ctx.author:
            if await self.bot.is_mod(ctx.author) is False:
                return await ctx.send("Sorry you cannot save tags for others. You need a mod permission level")
        if user is None:
            user = ctx.author

        formatted_tag = Helper.formatTag(user_tag)
        if not Helper.verifyTag(formatted_tag):
            return await ctx.send("Incorrect Tag provided")
        url = "https://api.clashofclans.com/v1/players/%23" + formatted_tag
        async with self.session.request("GET", url=url, headers=HEADERS) as resp:
            response = await resp.text()
            if resp.status >= 400:
                return await ctx.send("Can't connect to the servers please try again later")
        async with self.config.members() as database:
            database[user.id] = formatted_tag
            return await ctx.send(f"#{formatted_tag} succesfully saved for {user.mention}")

    @commands.command(name="cocp")
    async def showcocprofile(self, ctx, user: discord.User = None):
        if user is None:
            user = ctx.author
        async with self.config.members() as database:
            if str(user.id) not in database.keys():
                return await ctx.send("You don't have a tag saved please use !savecoc to save your tag")
            player_tag = database[str(user.id)]
            url = "https://api.clashofclans.com/v1/players/%23" + player_tag
        async with self.session.request("GET", url=url, headers=HEADERS) as resp:
            response = await resp.text()
            player_data = json.loads(response)
            name = player_data['name']
            warstars = player_data['warStars']
            townhall = player_data['townHallLevel']
            donations = player_data['donations']
            received = player_data['donationsReceived']
            if "clan" in player_data.keys():
                clan_name = player_data['clan']['name']
                role = player_data['role']
                badge = player_data['clan']['badgeUrls']['small']
            else:
                role = ""
                clan_name = ""
                badge = None
            trophies = player_data['trophies']
            personal_best = player_data['bestTrophies']
            if "league" in player_data.keys():
                league = player_data['league']['iconUrls']['medium']
            else:
                league = None
            Legend_Trophies = 0
            if "legendStatistics" in player_data.keys():
                Legend_Trophies = player_data['legendStatistics']['legendTrophies']
            heroes = None
            if "heroes" in player_data.keys():
                heroes = player_data['heroes']

            embed = discord.Embed(color=discord.Color.blue())
            embed.set_footer(text="By LeGeND Gaming | Kingslayer",
                             icon_url="https://images-ext-2.discordapp.net/external/H_cRTQw-Ww7M8HBYw5SujWCBr3gmlPzaySJ3pJfTAQI/%3Fsize%3D1024/https/cdn.discordapp.com/avatars/295216164487954432/72ae0d96f020064bff3a63d7218386b8.png?width=473&height=473")
            if "league" in player_data.keys():
                embed.set_thumbnail(url=league)
            else:
                embed.set_thumbnail(
                    url="https://static.wikia.nocookie.net/clashofclans/images/c/c0/Unranked_League.png/revision/latest/scale-to-width-down/92?cb=20171003011534")
            if "clan" in player_data.keys():
                embed.set_author(
                    name=name + " (" + "#" + player_tag + ")", icon_url=badge, url="https://www.clashofstats.com/players/"+player_tag)
                embed.add_field(name=Helper.roleNameConverter(
                    role=role), value="{} {}".format(self.get_emoji("clans"), clan_name))
            else:
                embed.set_author(name=name + " (" + "#" + player_tag + ")")
            embed.add_field(name="Current Trophies", value="{} {:,}".format(
                self.trophy_to_emoji(trophies=trophies), trophies))
            embed.add_field(name="Highest Trophies", value="{} {:,}".format(
                self.trophy_to_emoji(trophies=personal_best), personal_best))
            if 'legendStatistics' in player_data.keys():
                embed.add_field(name="Legend League Trophies",
                                value="{} {:,}".format(self.get_emoji("LegendTrophies"), Legend_Trophies))
            embed.add_field(name="Town Hall Level", value="{} {}".format(
                self.get_emoji("TownHall"), townhall))
            embed.add_field(name="War Stars",
                            value=":star: {:,}".format(warstars))
            embed.add_field(name="Troops Received", value="{} {:,}".format(
                self.get_emoji(name="card"), received))
            embed.add_field(name="Troops Donated", value="{} {:,}".format(
                self.get_emoji(name="card"), donations))
            if "heroes" in player_data.keys():
                for hero_data in heroes:
                    hero_name = hero_data['name']
                    hero_level = hero_data['level']
                    hero_max = hero_data['maxLevel']
                    useable = hero_name.replace(" ", "")
                    embed.add_field(name=f"{hero_name} Level", value="{} {}/{}".format(
                        self.get_emoji(useable), hero_level, hero_max))
            await ctx.send(embed=embed)

    @commands.command(name="legendcoc")
    async def showcocclans(self, ctx, member: discord.Member = None):
        final_dict = {}
        total_members = 0
        if member is None:

            for clan in self.family_clans:
                tag = self.family_clans[clan]["tag"]
                url = "https://api.clashofclans.com/v1/clans/%23"+tag
                async with self.session.request("GET", url=url, headers=HEADERS) as resp:
                    response = await resp.text()
                clan_data = json.loads(response)
                total_members += clan_data['members']
                final_dict[clan] = {}
                final_dict[clan]["name"] = self.family_clans[clan]["name"]
                final_dict[clan]["th_level"] = self.family_clans[clan]['th_level']
                final_dict[clan]["tag"] = self.family_clans[clan]["tag"]
                final_dict[clan]['bonus'] = self.family_clans[clan]['bonus']
                final_dict[clan]['trophies'] = clan_data["clanPoints"]
                final_dict[clan]['req_trophies'] = clan_data['requiredTrophies']
                final_dict[clan]['members'] = clan_data['members']
                final_dict[clan]['nick'] = self.family_clans[clan]['nick']

            sorted_items = sorted(final_dict.items(),
                                  key=lambda x: x[1]['trophies'], reverse=True)
            sorted_dict = {k: v for k, v in sorted_items}
            embed = discord.Embed(color=0xFAA61A)
            embed.set_author(name="LeGeND Family Clans",
                             icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
            embed.set_footer(text="By Kingslayer | Legend Gaming",
                             icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
            embed.description = f"Our Family is made up of {len(self.family_clans)} clans with a total of {total_members} members. We have {len(self.family_clans)*50 - total_members} spots left. Hope you decide to join us!"
            for clan in sorted_dict:
                name = f"{sorted_dict[clan]['name']}(#{sorted_dict[clan]['tag']}) {sorted_dict[clan]['bonus']}"
                value = f"{self.get_emoji('members')} \u200b {sorted_dict[clan]['members']}/50 \u200b \u200b \u200b \u200b  {self.get_emoji('PB')} \u200b {sorted_dict[clan]['req_trophies']}+ \u200b \u200b \u200b \u200b  {self.get_emoji('TownHall')} \u200b {sorted_dict[clan]['th_level']}+ \u200b \u200b \u200b \u200b  {self.get_emoji('crtrophy')} \u200b {sorted_dict[clan]['trophies']}"
                embed.add_field(name=name, value=value, inline=False)

            await ctx.send(embed=embed)

        else:
            clan_found = False
            async with self.config.members() as database:
                if str(member.id) not in database.keys():
                    return await ctx.send("You don't have a tag saved please use !savecoc to save your tag")
                player_tag = database[str(member.id)]
                url = "https://api.clashofclans.com/v1/players/%23" + player_tag
                async with self.session.request("GET", url=url, headers=HEADERS) as resp:
                    response = await resp.text()
                player_data = json.loads(response)
                townhall = player_data['townHallLevel']
                trophies = player_data['trophies']

                for clan in self.family_clans:
                    tag = self.family_clans[clan]["tag"]
                    url = "https://api.clashofclans.com/v1/clans/%23"+tag
                    async with self.session.request("GET", url=url, headers=HEADERS) as resp:
                        response = await resp.text()
                    clan_data = json.loads(response)
                    total_members += clan_data['members']
                    if townhall >= self.family_clans[clan]['th_level'] and trophies >= clan_data["requiredTrophies"]:
                        final_dict[clan] = {}
                        final_dict[clan]["name"] = self.family_clans[clan]["name"]
                        final_dict[clan]["th_level"] = self.family_clans[clan]['th_level']
                        final_dict[clan]["tag"] = self.family_clans[clan]["tag"]
                        final_dict[clan]['bonus'] = self.family_clans[clan]['bonus']
                        final_dict[clan]['trophies'] = clan_data["clanPoints"]
                        final_dict[clan]['req_trophies'] = clan_data['requiredTrophies']
                        final_dict[clan]['members'] = clan_data['members']
                        final_dict[clan]['nick'] = self.family_clans[clan]['nick']
                        clan_found = True

                sorted_items = sorted(final_dict.items(),
                                      key=lambda x: x[1]['trophies'], reverse=True)
                sorted_dict = {k: v for k, v in sorted_items}
                embed = discord.Embed(color=0xFAA61A)
                embed.set_author(name="LeGeND Family Clans",
                                 icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
                embed.set_footer(text="By Kingslayer | Legend Gaming",
                                 icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
                embed.description = f"Our Family is made up of {len(self.family_clans)} clans with a total of {total_members} members. We have {len(self.family_clans)*50 - total_members} spots left. Hope you decide to join us!"
                if not(clan_found):
                    embed.add_field(
                        name="uh oh!", value="There are no clans available for you at the moment, please type !legendcoc to see all clans.")
                    return await ctx.send(embed=embed)
                for clan in sorted_dict:
                    name = f"{sorted_dict[clan]['name']}(#{sorted_dict[clan]['tag']}) {sorted_dict[clan]['bonus']}"
                    value = f"{self.get_emoji('members')} \u200b {sorted_dict[clan]['members']}/50 \u200b \u200b \u200b \u200b  {self.get_emoji('PB')} \u200b {sorted_dict[clan]['req_trophies']}+ \u200b \u200b \u200b \u200b  {self.get_emoji('TownHall')} \u200b {sorted_dict[clan]['th_level']}+ \u200b \u200b \u200b \u200b  {self.get_emoji('crtrophy')} \u200b {sorted_dict[clan]['trophies']}"
                    embed.add_field(name=name, value=value, inline=False)

                await ctx.send(embed=embed)

    @commands.group()
    @commands.guild_only()
    @checks.admin()
    async def cocclans(self, ctx):
        pass

    @cocclans.command()
    @commands.guild_only()
    @checks.admin()
    async def settownhall(self, ctx, key: str, level: int):
        nick_correct = False
        nicks = ""
        for clan in self.family_clans:
            nicks += f"{self.family_clans[clan]['nick']}, "
            if self.family_clans[clan]["nick"] == key:
                self.family_clans[clan]["th_level"] = level
                nick_correct = True
                with open(self.path, "w") as json_file:
                    json.dump(self.family_clans, json_file)

        if nick_correct:
            await ctx.send("Clan data changed!")
        else:
            await ctx.send(f"Incorrect clan key provided! Please use any of these {nicks}")

    @cocclans.command()
    @commands.guild_only()
    @checks.admin()
    async def setbonus(self, ctx, key: str, *, bonus: str):
        nick_correct = False
        nicks = ""
        for clan in self.family_clans:
            nicks += f"{self.family_clans[clan]['nick']}, "
            if self.family_clans[clan]["nick"] == key:
                self.family_clans[clan]["bonus"] = bonus
                nick_correct = True
                with open(self.path, "w") as json_file:
                    json.dump(self.family_clans, json_file)

        if nick_correct:
            await ctx.send("Clan data changed!")
        else:
            await ctx.send(f"Incorrect clan key provided! Please use any of these {nicks}")

    @commands.command(name="appcoc")
    @checks.mod()
    @commands.guild_only()
    async def approvecoc(self, ctx, key: str, member: discord.Member):
        if ctx.guild.id == 374596069989810176:
            async with self.config.members() as database:
                if str(member.id) not in database.keys():
                    return await ctx.send("You don't have a tag saved please use !savecoc to save your tag")
                player_tag = database[str(member.id)]
                url = "https://api.clashofclans.com/v1/players/%23" + player_tag
                async with self.session.request("GET", url=url, headers=HEADERS) as resp:
                    response = await resp.text()
                player_data = json.loads(response)
                player_name = player_data['name']
                townhall = player_data['townHallLevel']
                trophies = player_data['trophies']
                nick_correct = False
                nicks = ""
                for clan in self.family_clans:
                    nicks += f"{self.family_clans[clan]['nick']}, "
                    if self.family_clans[clan]["nick"] == key:
                        nick_correct = True
                        tag = self.family_clans[clan]["tag"]
                        url = "https://api.clashofclans.com/v1/clans/%23"+tag
                        async with self.session.request("GET", url=url, headers=HEADERS) as resp:
                            response = await resp.text()
                        clan_data = json.loads(response)
                        if townhall >= self.family_clans[clan]['th_level'] and trophies >= clan_data['requiredTrophies']:
                            if clan_data['members'] == 50:
                                return await ctx.maybe_send_embed(f"Approval failed, the clan is full")
                            await member.edit(nick=f"{player_name} (Approved)")
                            channel = ctx.guild.get_channel(375839851955748874)

                            role_id = self.family_clans[clan]['role']
                            role_to_ping = ctx.guild.get_role(role_id)
                            recruit_code = "".join(
                                random.choice(
                                    string.ascii_uppercase + string.digits)
                                for _ in range(6)
                            )

                            message = f"Congratulations, You have been approved to join {clan}(#{tag}) \n Your **RECRUIT CODE** is: ``{recruit_code}`` \n\n To join Search for #{tag} or {clan} in-game.\n Send a request **using recruit code** above and wait for your clan leadership to accept you. It usually takes a few minutes to get accepted, but it may take up to a few hours. \n\n**IMPORTANT**: Once your clan leadership has accepted your request, let a staff member in discord know that you have been accepted. They will then unlock all the member channels for you."
                            try:
                                await member.send(message)
                            except discord.Forbidden:
                                return await ctx.maybe_send_embed(f"Approval failed, please allow Direct messages from this server and try again later.")
                            await ctx.maybe_send_embed(f"Approval succesful, please check your DMs {member.mention}")
                            embed = discord.Embed(color=0xFAA61A)
                            embed.set_author(name="New Recruit",
                                             icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
                            embed.set_footer(text="By Kingslayer | Legend Gaming",
                                             icon_url="https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1")
                            embed.add_field(name="Name", value=player_name)
                            embed.add_field(name="Recruit Code",
                                            value=recruit_code)
                            embed.add_field(name="Clan", value=clan)
                            await channel.send(f"{role_to_ping.mention}", allowed_mentions=discord.AllowedMentions(roles=True), embed=embed)

                        else:
                            await ctx.maybe_send_embed(f"Approval failed, the player doesn't meet requirements for {clan}")

                if not(nick_correct):
                    return await ctx.send(f"Incorrect clan key provided! Please use any of these as keys {nicks[0:len(nicks)-2]}.")

        else:
            await ctx.send("This command only works on the Legend server")

    @commands.command(name="nmcoc")
    @commands.guild_only()
    async def newmembercoc(self, ctx, member: discord.Member):
        if ctx.guild.id == 374596069989810176:
            async with self.config.members() as database:
                if str(member.id) not in database.keys():
                    return await ctx.send("You don't have a tag saved please use !savecoc to save your tag")
                player_tag = database[str(member.id)]
            url = "https://api.clashofclans.com/v1/players/%23" + player_tag
            async with self.session.request("GET", url=url, headers=HEADERS) as resp:
                response = await resp.text()
            player_data = json.loads(response)
            player_clan_tag = player_data['clan']['tag']

            in_clan = False
            for clan in self.family_clans:
                if player_clan_tag == f"#{self.family_clans[clan]['tag']}":
                    in_clan = True
                    member_role = ctx.guild.get_role(374603334385926156)
                    clan_role = ctx.guild.get_role(
                        self.family_clans[clan]['role'])
                    coc_role = ctx.guild.get_role(768677256133345311)
                    await member.add_roles(member_role, clan_role, coc_role, reason="From COCTools")
                    await member.edit(nick=f"{player_data['name']} {self.family_clans[clan]['suffix']}")
                    await ctx.maybe_send_embed(f"Added **{clan_role.name}, {coc_role.name}, {member_role.name}** roles to {member.display_name} and changed name to **{player_data['name']} {self.family_clans[clan]['suffix']}**")
                    record_channel = ctx.guild.get_channel(375839851955748874)
                    global_channel = ctx.guild.get_channel(374596069989810178)
                    greeting_message = (random.choice(
                        self.greetings['GREETING'])).format(member)
                    record_message = f"**{ctx.author.nick}** recruited **{member.nick}** to **{clan}**"
                    await record_channel.send(record_message)
                    await global_channel.send(greeting_message)
                    try:
                        message = "Hi There! Congratulations on getting accepted into our family. We have unlocked all the member channels for you in LeGeND Discord Server. DM Legend ModMail, <@598662722821029888> if you have any problems.\nPlease do not leave our Discord server while you are in the clan. Thank you."
                        await member.send(message)
                        await asyncio.sleep(45)
                        for page in pagify(self.rules_text, delims=["\n\n\n"]):
                            await member.send(page)
                        await asyncio.sleep(45)
                        await member.send(str(self.esports_text))
                    except discord.errors.Forbidden():
                        return await ctx.send("{} please fix your privacy settings, we are unable to send you Direct Messages.".format(member.mention), allowed_mentions=discord.AllowedMentions(users=True))

            if not(in_clan):
                await ctx.send("The user is not in a LeGeND clan! try again after the user joins a LeGeND clan")
