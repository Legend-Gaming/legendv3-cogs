from discord.channel import TextChannel
from redbot.core import Config, commands, checks
import challonge
import discord
import random
import json
import string
import logging
import math
from redbot.core.utils import AsyncIter
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

"""
Important read below before you read the code
https://api.challonge.com/v1/documents,
teams are saved in the config,dict looks something like this; 'teams': 'participant_id'(from challonge): 'name':
                                                                                                          'captain_id':
                                                                                                          'players':
                                                                                                          'pokemon_choices':
Todo Nevus please do this make something like `!choose_type <pokemon_type>` all 3 users should choose different pokemons and for the valid pokemon types DM Zap
"""

log = logging.getLogger("red.cogs.pokemonleague")

async def embed_helper(ctx, message, colour=None):
    """ Send message as embed """
    colour = colour or discord.Colour.blue()
    embed = discord.Embed(description=message, color=colour)
    return await ctx.send(embed=embed)


class ExistingChannels(Exception):
    pass


class NoToken(Exception):
    pass


class PokemonLeague(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        try:
            self.leagues_file = str(bundled_data_path(self) / "leagues.json")
            with open(self.leagues_file) as file:
                self.gyms = dict(json.load(file))["gyms"]
        except Exception as exc:
            log.exception("Error in gym data.", exc_info=exc)
            raise

        self.config = Config.get_conf(self, identifier=3424234, force_registration=True)
        default_guild = {
            'teams': {},
            'tournament_id': None,
            'tournament_url': None,
            'tournament_name': None,
            'channel_id': 740329767492124682,
            'gym_channels': {},
            'assigned_channels': {}
        }
        self.config.register_guild(**default_guild)

    async def challongetoken(self):
        token = await self.bot.get_shared_api_tokens("challonge")
        if token['token'] is None or token['username'] is None:
            log.error("Challonge API not setup correctly, use !set api challonge username,YOUR_USERNAME token,YOUR_CHALLONGE_TOKEN")
            raise NoToken
        challonge.set_credentials(username=token['username'], api_key=token['token'])

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def createbracket(self, ctx, *, name:str):
        assigned_url = await self.config.guild(ctx.guild).tournament_url()
        tournament_name = await self.config.guild(ctx.guild).tournament_name()
        if assigned_url is None:
            url = "".join(
                        random.choice(string.ascii_lowercase + string.digits)
                        for _ in range(12)
                    )
            tournament = challonge.tournaments.create(name=name, url=url, game_id=49390, game_name='Clash Royale')
            tourney_id = tournament['id']
            url = tournament['full-challonge-url']
            await self.config.guild(ctx.guild).tournament_id.set(tourney_id)
            await self.config.guild(ctx.guild).tournament_url.set(url)
            await self.config.guild(ctx.guild).tournament_name.set(name)
            await embed_helper(ctx, "Tournament named [{}]({}) has been created.".format(name, url))
        else:
            await embed_helper(
                ctx,
                "A tournament, [{}]({}) is already running.".format(tournament_name, assigned_url)
            )

    @commands.command()
    @commands.guild_only()
    @checks.bot_has_permissions(manage_roles=True)
    async def register(self, ctx, user1: discord.Member, user2:discord.Member, *,name:str):
        """
            Register your team with you as captain
        """
        teams = await self.config.guild(ctx.guild).teams()
        url = await self.config.guild(ctx.guild).tournament_url()
        if url is None:
            return await ctx.send("No tournaments running!")
        elif user1 == ctx.author or user2 == ctx.author:
            return await embed_helper(
                ctx,
                (
                    "You cannot add yourself more than once. "
                    "Maybe its your evil twin but they'll need to get their own discord."
                )
            )
        if user1 == user2:
            return await embed_helper(
                ctx,
                "I am sorry. I see only one of {}. Now go get a third member.".format(user1.mention)
            )
        if len(teams) > 0:
            for team_id in teams.keys():
                if teams[team_id]['name'] == name:
                    return await embed_helper(ctx, "This name is already taken. Choose a better name.")
                elif (
                        user1.id in teams[team_id]['players']
                        or user2.id in teams[team_id]['players']
                        or ctx.author.id in teams[team_id]['players']
                ):
                    return await embed_helper(ctx, "A team member is already registered with team {}".format(teams[team_id]['name']))

        tournament = await self.config.guild(ctx.guild).tournament_id()
        try:
            participant = challonge.participants.create(tournament=tournament, name=name)
        except challonge.api.ChallongeException as e:
            return await ctx.send("Registerations have ended")
        participant_id = participant['id']
        async with self.config.guild(ctx.guild).teams() as teams:
            teams[participant_id] = {}
            teams[participant_id]['name'] = name
            teams[participant_id]['captain_id'] = ctx.author.id
            teams[participant_id]['players'] = [user1.id, user2.id, ctx.author.id]
            teams[participant_id]['pokemon_choices'] = {}
            role = discord.utils.get(ctx.guild.roles, name=name)
            if role:
                await embed_helper(ctx, "There is already a role with name {}. Please contact the admins for the team roles.".format(name))
                return
            else:
                role = await ctx.guild.create_role(name=name)
                await ctx.author.add_roles(role)
                await user1.add_roles(role)
                await user2.add_roles(role)
            await embed_helper(ctx, "Team {} successfuly registered.".format(name))

    @commands.command()
    @commands.guild_only()
    async def showteam(self, ctx, *, name:str):
        team_found = False
        url = await self.config.guild(ctx.guild).tournament_url()
        if url is None:
            return await ctx.send("No tournaments running!")
        teams = await self.config.guild(ctx.guild).teams()
        if len(teams) > 0:
            for team_id in teams.keys():
                if teams[team_id]['name'] == name:
                    team_found = True
                    captain_id = teams[team_id]['captain_id']
                    players_id = teams[team_id]['players']
                    players_id.remove(captain_id)
                    embed = discord.Embed(colour=0xFAA61A, title=name, url=url)
                    captain = ctx.guild.get_member(captain_id)
                    embed.add_field(name="Captain", value=captain.mention, inline=False)
                    description = ""
                    for player_id in players_id:
                        user = ctx.guild.get_member(player_id)
                        description += str(user.mention + "  ")
                    embed.add_field(name="Players", value=description, inline=False)
                    return await ctx.send(embed=embed)
            if not(team_found):
                await embed_helper(ctx, "Team not found")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.bot_has_permissions(manage_roles=True)
    async def removeteam(self, ctx, *,team_name):
        team_found = False
        url = await self.config.guild(ctx.guild).tournament_url()
        tournament_name = await self.config.guild(ctx.guild).tournament_name()
        tournament_id = await self.config.guild(ctx.guild).tournament_id()
        if url is None:
            return await embed_helper(ctx, "No tournaments running!")
        teams_data = await self.config.guild(ctx.guild).teams()
        for team_id in teams_data.keys():
            if teams_data[team_id]['name'] == team_name:
                team_found = True
                try:
                    challonge.participants.destroy(tournament_id, team_id)
                except challonge.api.ChallongeException as e:
                    return await embed_helper(ctx, "Tournament already started!")
                async with self.config.guild(ctx.guild).teams() as teams:
                    del teams[team_id]
                role = discord.utils.get(ctx.guild.roles, name=team_name)
                if role:
                    await role.delete()
                return await embed_helper(ctx, "Team {} has been removed from {}".format(team_name, tournament_name))
        if not(team_found):
            await embed_helper(ctx, "Team {} not found".format(team_name))

    @commands.command()
    @commands.guild_only()
    @checks.bot_has_permissions(manage_roles=True)
    async def update(self, ctx, *, team_name):
        """
            Report win for a team
        """
        channel_id = await self.config.guild(ctx.guild).channel_id()
        channel = ctx.guild.get_channel(channel_id)
        url = await self.config.guild(ctx.guild).tournament_url()
        tournament = await self.config.guild(ctx.guild).tournament_id()
        if url is None:
            return await ctx.send("No tournaments running!")
        match_found = False
        team_found = False
        teams_data = await self.config.guild(ctx.guild).teams()

        team_1_id = None
        team_2_id = None

        for team_id in teams_data.keys():
            if teams_data[team_id]['name'] == team_name:
                if ctx.author.id != teams_data[team_id]["captain_id"] and not await self.bot.is_admin(ctx.author):
                    return await embed_helper(ctx, "Only captains and admins are allowed to update wins.")
                team_found = True
                matches_list = challonge.matches.index(tournament=tournament)
                async for single_match_data in AsyncIter(matches_list):
                    if single_match_data['state'] == "open":
                        if int(team_id) == single_match_data['player1-id'] or int(team_id) == single_match_data['player2-id']:
                            if int(team_id) == single_match_data['player1-id']:
                                scores = "1-0"
                            else:
                                scores = "0-1"
                            match_id = single_match_data['id']
                            challonge.matches.update(tournament=tournament, match_id=match_id, winner_id=team_id, scores_csv=scores)

                            # Revoke perms for players
                            assigned_channels = await self.config.guild(ctx.guild).assigned_channels()
                            team_1_id = str(single_match_data['player1-id'])
                            team_1_name = teams_data[str(team_1_id)]['name']
                            team_1_channel_id = assigned_channels.get(team_1_name, None)
                            team_2_id = str(single_match_data['player2-id'])
                            team_2_name = teams_data[str(team_2_id)]['name']
                            team_2_channel_id = assigned_channels.get(team_2_name, None)

                            if team_1_channel_id != team_2_channel_id:
                                await ctx.send("Something is wrong with the bot data. Please contact the admins.")
                            team_1_role = discord.utils.get(ctx.guild.roles, name=team_1_name)
                            team_2_role = discord.utils.get(ctx.guild.roles, name=team_2_name)
                            badge_to_award = None
                            for gym in self.gyms.values():
                                    if gym["level"] == (single_match_data["round"] - 1):
                                        badge_to_award = gym["badge"]
                                        break
                            badge_role = discord.utils.get(ctx.guild.roles, name=badge_to_award)
                            if badge_role:
                                for player_id in teams_data[team_id]['players']:
                                    player = ctx.guild.get_member(player_id)
                                    await player.add_roles(badge_role)
                            team_1_channel = self.bot.get_channel(team_1_channel_id)
                            team_2_channel = self.bot.get_channel(team_2_channel_id)
                            if team_1_channel:
                                await team_1_channel.set_permissions(team_1_role, read_messages=False, send_messages=False)
                            if team_2_channel:
                                await team_2_channel.set_permissions(team_2_role, read_messages=False, send_messages=False)
                            assigned_channels[team_1_name] = None
                            assigned_channels[team_2_name] = None
                            await self.config.guild(ctx.guild).assigned_channels.set(assigned_channels)

                            match_found = True
                if match_found: # search for next match
                    new_match_found = False
                    matches_list = challonge.matches.index(tournament=tournament)
                    async for single_match in AsyncIter(matches_list):
                        if single_match['state'] == "open":
                            if int(team_id) == single_match['player1-id'] or int(team_id) == single_match['player2-id']:
                                new_match_found = True
                                team_1_id = str(single_match['player1-id'])
                                team_2_id = str(single_match['player2-id'])
                                teams = await self.config.guild(ctx.guild).teams()
                                team_1_captain_id = teams[team_1_id]['captain_id']
                                team_2_captain_id = teams[team_2_id]['captain_id']
                                team_1_captain = ctx.guild.get_member(team_1_captain_id)
                                team_2_captain = ctx.guild.get_member(team_2_captain_id)
                                team_1_name = teams[team_1_id]['name']
                                team_2_name = teams[team_2_id]['name']

                                assigned_channels = await self.config.guild(ctx.guild).assigned_channels()
                                highest_gym = None
                                team_1_channel_id = assigned_channels.get(team_1_name, None)
                                team_2_channel_id = assigned_channels.get(team_2_name, None)
                                for gym in self.gyms.values():
                                    if gym["level"] == (single_match["round"] - 1):
                                        current_gym = gym
                                        break
                                team_1_role = discord.utils.get(ctx.guild.roles, name=team_1_name)
                                team_2_role = discord.utils.get(ctx.guild.roles, name=team_2_name)
                                all_channels = (await self.config.guild(ctx.guild).gym_channels())[current_gym["name"]]

                                team_channel = None
                                if team_1_channel_id is not None and team_2_channel_id is not None:
                                    # If both are not None check if they are in channel for their respective gym
                                    # If they are not in proper gym channels, remove access to other gyms
                                    team_1_channel = self.bot.get_channel(team_1_channel_id)
                                    team_2_channel = self.bot.get_channel(team_2_channel_id)

                                    if  (
                                            team_1_channel is None
                                            or (team_1_channel.category.name != gym["name"])
                                            or team_2_channel is None
                                            or (team_2_channel.category.name != gym["name"])
                                            or team_1_channel_id != team_2_channel_id
                                        ):
                                        if team_1_channel:
                                            await team_1_channel.set_permissions(team_1_role, read_messages=False, send_messages=False)
                                        if team_2_channel:
                                            await team_2_channel.set_permissions(team_2_role, read_messages=False, send_messages=False)
                                    else:
                                        team_channel = team_1_channel
                                elif team_1_channel_id is not None:
                                    # If one is not None, remove its perms and assign to new channel
                                    team_1_channel = self.bot.get_channel(team_1_channel_id)
                                    if team_1_channel:
                                        await team_1_channel.set_permissions(team_1_role, read_messages=False, send_messages=False)
                                elif team_2_channel_id is not None:
                                    team_2_channel = self.bot.get_channel(team_2_channel_id)
                                    if team_2_channel:
                                        await team_2_channel.set_permissions(team_2_role, read_messages=False, send_messages=False)
                                if not team_channel:
                                    assignable_channels = list([channel for channel in all_channels if channel not in assigned_channels.values()])
                                    if len(assignable_channels) < 1:
                                        await embed_helper(ctx, f"Gym {current_gym['name']} does not currently have a gym leader. "
                                            "Please ask the moderators to summon them."
                                        )
                                    else:
                                        team_channel = self.bot.get_channel(assignable_channels[0])
                                if team_channel:
                                    await team_channel.set_permissions(team_1_role, read_messages=True, send_messages=True)
                                    await team_channel.set_permissions(team_2_role, read_messages=True, send_messages=True)
                                    assigned_channels[team_1_name] = team_channel.id
                                    assigned_channels[team_2_name] = team_channel.id
                                await self.config.guild(ctx.guild).assigned_channels.set(assigned_channels)

                                await embed_helper(channel, "{} vs {}\nCaptains: {}  {}\nGym: {}".format(
                                    team_1_name, team_2_name,
                                    team_1_captain.mention, team_2_captain.mention,
                                    current_gym["name"],
                                    )
                                )

                    if not(new_match_found):
                        await embed_helper(ctx, "Thanks for updating the scores. You don't have any new matches pending as of now.")
                elif not(match_found):
                    await embed_helper(ctx, "You have either been eliminated or your match is still pending, check [bracket]({})".format(url))


        if not(team_found):
            await ctx.send("Team not found")

    @commands.command(name="startbracket")
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.bot_has_permissions(manage_roles=True)
    async def command_startbracket(self, ctx):
        tournament_url = await self.config.guild(ctx.guild).tournament_url()
        tournament = await self.config.guild(ctx.guild).tournament_id()
        tournament_name = await self.config.guild(ctx.guild).tournament_name()
        if tournament_url is None:
            return await embed_helper("No tournaments running!")
        try:
            await self.discord_setup(ctx)
        except ExistingChannels:
            return
        except Exception as e:
            log.exception("Encountered error when preparing server for upcoming battles.")
            await ctx.send("Error when prepping up the gyms.")
            return
        challonge.participants.randomize(tournament=tournament)
        challonge.tournaments.start(tournament=tournament)
        await embed_helper(ctx, "Tournament [{}]({}) has been started.".format(tournament_name, tournament_url))

    @commands.command(name="deletebracket")
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.bot_has_permissions(manage_roles=True, add_reactions=True)
    async def command_deletebracket(self, ctx):
        channel_id = await self.config.guild(ctx.guild).channel_id()
        url = await self.config.guild(ctx.guild).tournament_url()
        tournament = await self.config.guild(ctx.guild).tournament_id()
        if url is None:
            return await embed_helper(ctx, "No tournaments running!")
        teams_data = await self.config.guild(ctx.guild).teams()
        for team in teams_data.values():
            name = team["name"]
            role = discord.utils.get(ctx.guild.roles, name=name)
            if role:
                try:
                    await role.delete()
                except discord.HTTPException:
                    await embed_helper(ctx, "Failed to delete role {}".format(role.mention))
        await self.config.guild(ctx.guild).clear()
        await embed_helper(ctx, "Bracket has been removed from the bot but still can be accessed [here]({}).".format(url))
        msg = await embed_helper(ctx, "Do you want to delete from the challonge site too?")
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)
        if pred.result is True:
            challonge.api.fetch(
                "DELETE",
                "tournaments/{}".format(tournament)
            )
        await self.config.guild(ctx.guild).channel_id.set(channel_id)
        await ctx.tick()

    @commands.command(name="makematches")
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def command_makematches(self, ctx):
        channel_id = await self.config.guild(ctx.guild).channel_id()
        channel = ctx.guild.get_channel(channel_id)
        url = await self.config.guild(ctx.guild).tournament_url()
        tournament = await self.config.guild(ctx.guild).tournament_id()
        if url is None:
            return await ctx.send("No tournaments running!")
        all_matches = challonge.matches.index(tournament=tournament)
        async for single_match in AsyncIter(all_matches):
            if single_match['state'] == "open":
                team_1_id = str(single_match['player1-id'])
                team_2_id = str(single_match['player2-id'])
                teams = await self.config.guild(ctx.guild).teams()
                team_1_captain_id = teams[str(team_1_id)]['captain_id']
                team_2_captain_id = teams[str(team_2_id)]['captain_id']
                team_1_captain = ctx.guild.get_member(team_1_captain_id)
                team_2_captain = ctx.guild.get_member(team_2_captain_id)
                team_1_name = teams[str(team_1_id)]['name']
                team_2_name = teams[str(team_2_id)]['name']
                team_1_players = teams[str(team_1_id)]['players']
                team_2_players = teams[str(team_2_id)]['players']

                assigned_channels = await self.config.guild(ctx.guild).assigned_channels()
                highest_gym = None
                team_1_channel_id = assigned_channels.get(team_1_name, None)
                team_2_channel_id = assigned_channels.get(team_2_name, None)
                for gym in self.gyms.values():
                    if gym["level"] == (single_match["round"] - 1):
                        current_gym = gym
                        break
                team_1_role = discord.utils.get(ctx.guild.roles, name=team_1_name)
                team_2_role = discord.utils.get(ctx.guild.roles, name=team_2_name)
                all_channels = (await self.config.guild(ctx.guild).gym_channels())[current_gym["name"]]

                team_channel = None
                if team_1_channel_id is not None and team_2_channel_id is not None:
                    # If both are not None check if they are in channel for their respective gym
                    # If they are not in proper gym channels, remove access to other gyms
                    team_1_channel = self.bot.get_channel(team_1_channel_id)
                    team_2_channel = self.bot.get_channel(team_2_channel_id)

                    if  (
                            team_1_channel is None
                            or (team_1_channel.category.name != gym["name"])
                            or team_2_channel is None
                            or (team_2_channel.category.name != gym["name"])
                            or team_1_channel_id != team_2_channel_id
                        ):
                        if team_1_channel:
                            await team_1_channel.set_permissions(team_1_role, read_messages=False, send_messages=False)
                        if team_2_channel:
                            await team_2_channel.set_permissions(team_2_role, read_messages=False, send_messages=False)
                    else:
                        team_channel = team_1_channel
                elif team_1_channel_id is not None:
                    # If one is not None, remove its perms and assign to new channel
                    team_1_channel = self.bot.get_channel(team_1_channel_id)
                    if team_1_channel:
                        await team_1_channel.set_permissions(team_1_role, read_messages=False, send_messages=False)
                elif team_2_channel_id is not None:
                    team_2_channel = self.bot.get_channel(team_2_channel_id)
                    if team_2_channel:
                        await team_2_channel.set_permissions(team_2_role, read_messages=False, send_messages=False)
                if not team_channel:
                    available_channels = list([channel for channel in all_channels if channel not in assigned_channels.values()])
                    if len(available_channels) > 0:
                        team_channel = self.bot.get_channel(available_channels)
                    else:
                        await embed_helper(
                            ctx,
                            f"Gym {current_gym['name']} does not currently have a gym leader. "
                            "Please ask the moderators to summon them."
                    )
                if team_channel:
                    await team_channel.set_permissions(team_1_role, read_messages=True, send_messages=True)
                    await team_channel.set_permissions(team_2_role, read_messages=True, send_messages=True)
                    assigned_channels[team_1_name] = team_channel.id
                    assigned_channels[team_2_name] = team_channel.id
                await self.config.guild(ctx.guild).assigned_channels.set(assigned_channels)
                # for role in team_1_captain.roles:
                #     for gym_name, gym_data in self.gyms.items():
                #         if role.name == gym_data["badge"]:
                # if team_1_name not in assigned_channels and team_2_name not in assigned_channels:
                #     # This part is used to assign channels for round 1
                #     all_channels = (await self.config.guild(ctx.guild).gym_channels())["Violet City"]
                #     team_1_role = discord.utils.get(ctx.guild.roles, name=team_1_name)
                #     team_2_role = discord.utils.get(ctx.guild.roles, name=team_2_name)
                #     team_channel_id = list([channel for channel in all_channels if channel not in assigned_channels.values()])[0]
                    # team_channel = self.bot.get_channel(team_channel_id)
                    # await team_channel.set_permissions(team_1_role, read_messages=True, send_messages=True)
                    # await team_channel.set_permissions(team_2_role, read_messages=True, send_messages=True)
                #     assigned_channels[team_1_name] = team_channel.id
                #     assigned_channels[team_2_name] = team_channel.id
                #     await self.config.guild(ctx.guild).assigned_channels.set(assigned_channels)
                await embed_helper(channel, "{} vs {}\nCaptains: {}  {}\nGym: {}".format(
                    team_1_name, team_2_name,
                    team_1_captain.mention, team_2_captain.mention,
                    current_gym["name"],
                    )
                )

    async def discord_setup(self, ctx):
        teams = await self.config.guild(ctx.guild).teams()

        number_of_gyms = int(math.floor(math.log(len(teams), 2)))
        # number of people eliminated in first round to make number
        # of teams power of 2 is distance to nearest power of 2
        first_elimination = int(len(teams) - 2**number_of_gyms)
        number_of_gyms += 1 if first_elimination > 0 else 0

        log.info("{} gyms required for {} teams.".format(number_of_gyms, len(teams)))

        everyone_role = ctx.author.roles[0]

        channels_created = {}

        last_position = 0
        for c in ctx.guild.categories:
                if c.name not in self.gyms.keys():
                    last_position = c.position

        for index, gym in enumerate(self.gyms.values()):
            if index >= number_of_gyms:
                break

            log.info("Checking for {}".format(gym["name"]))

            role = discord.utils.get(ctx.guild.roles, name=gym["badge"]) or await ctx.guild.create_role(name=gym["badge"])

            category = None
            category = discord.utils.get(ctx.guild.categories, name=gym["name"])
            if not category:
                category = await ctx.guild.create_category(gym["name"], position=last_position + 1 + index)
            else:
                if len(category.channels) > 0:
                    await ctx.send((
                        f"There are channels under category {category.name}. This might cause messed up permissions."
                        "Are you sure you want to continue without deleting those channels?"
                        )
                    )
                    pred = MessagePredicate.yes_or_no(ctx)
                    await self.bot.wait_for("message", check=pred)
                    if pred.result is False:
                        await ctx.send("Use {}deletebadgechannels commands to delete all channels.".format(ctx.prefix))
                        raise ExistingChannels
            channels_created[category.name] = list()
            #     await ctx.send("Editing pos of {} using {} + {} to {}".format(category.name, last_position, index, last_position + 1 + index))
            #     await category.edit(position=last_position + 1 + index)
            await category.set_permissions(everyone_role, read_messages=False, send_messages=False)

            if first_elimination == 0:
                number_of_channels_required = int(len(teams) / (2 ** (gym["level"] + 1)))
            else:
                if index == 0:
                    number_of_channels_required = first_elimination
                else:
                    number_of_channels_required = int(len(teams) / (2 ** gym["level"]))
            log.info("Creating {} channels under {}".format(number_of_channels_required, category.name))
            for index in range(number_of_channels_required):
                new_channel = None
                new_channel = await category.create_text_channel(name=gym["badge"].replace(' ', '-'))
                if new_channel:
                    channels_created[category.name].append(new_channel.id)
                await new_channel.set_permissions(everyone_role, read_messages=False, send_messages=False)
        await self.config.guild(ctx.guild).gym_channels.set(channels_created)
        await ctx.tick()

    @commands.command(name="deletebadgechannels")
    @checks.admin()
    @checks.bot_has_permissions(manage_channels=True)
    async def command_deletebadgechannels(self, ctx):
        """
            Delete all text channels with badge in their name
            To be used when tournament ends to prepare for next tournament
        """
        url = await self.config.guild(ctx.guild).tournament_url()
        if url:
            await embed_helper("There is a tournament running in the server! You cannot delete channels without finishing the tournament.")
            return
        await ctx.send((
            f"This command will delete all channels that have `badge` in ther name. Are you sure you want to do that?"
            )
        )
        pred = MessagePredicate.yes_or_no(ctx)
        await self.bot.wait_for("message", check=pred)
        if pred.result is False:
            await ctx.send("You have chosen not to delete the channels.")
            return
        try:
            for channel in ctx.guild.text_channels:
                if "badge" in channel.name:
                    await channel.delete()
        except discord.Forbidden:
            return await embed_helper(ctx, "No permission to delete channel.")
        except discord.HTTPException:
            return await embed_helper(ctx, "Error when deleting channel.")
        await ctx.tick()

    @commands.command(name="setleaguechannel")
    @checks.admin_or_permissions()
    async def command_setleaguechannel(self, ctx, channel:discord.TextChannel):
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.tick()


