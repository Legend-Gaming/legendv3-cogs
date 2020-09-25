import asyncio
import json
import logging
import math
import random
import re
import string
from typing import Dict, Optional

import clashroyale
import discord
from redbot.core import Config, checks, commands
from redbot.core.data_manager import bundled_data_path
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import humanize_list
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu, start_adding_reactions
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate

from .src.challonge.account import Account, ChallongeException

"""
Important read below before you read the code:
https://api.challonge.com/v1/documents

Teams are saved in the config:
'teams': {
    'participant_id': <from challonge>,
    'name': <name>
    'captain_id': <id>,
    'players': <list of id>,
    'pokemon_choices': <list of type>
}

regex:
    to check await :     ^((?!await).)* embed_helper
    to check ctx:         r"embed_helper\(\n?[\t ]*(ctx|channel),"
"""

log = logging.getLogger("red.cogs.pokemonleague")


async def embed_helper(
    ctx: commands.Context, message: str, colour: Optional[discord.Colour] = None
):
    """Send message as embed."""
    colour = colour or discord.Colour.blue()
    embed = discord.Embed(description=message, color=colour)
    return await ctx.send(embed=embed)


class ExistingChannels(Exception):
    """Signal that existing channels are present."""

    pass


class NoToken(Exception):
    """No token has been set."""

    pass


class PokemonLeague(commands.Cog):
    """Cog to manage pokemon themed clash royale tournaments."""

    def __init__(self, bot):
        self.bot = bot

        try:
            self.leagues_file = str(bundled_data_path(self) / "leagues.json")
            with open(self.leagues_file) as file:
                self.gyms = dict(json.load(file))["gyms"]
        except Exception as exc:
            log.exception("Error in gyms data.", exc_info=exc)
            raise
        try:
            self.pokemons_file = str(bundled_data_path(self) / "pokemons.json")
            with open(self.pokemons_file) as file:
                self.pokemons = dict(json.load(file))
        except Exception as exc:
            log.exception("Error in pokemon data.", exc_info=exc)
            raise

        self.constants = getattr(
            self.bot.get_cog("ClashRoyaleTools"), "constants", None
        )

        self.config = Config.get_conf(self, identifier=3424234, force_registration=True)
        default_guild = {
            "teams": {},
            "tournament_id": None,
            "tournament_url": None,
            "tournament_name": None,
            "channel_id": 740329767492124682,
            "gym_channels": {},
            "assigned_channels": {},
        }
        default_user = {"pokemons": []}
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)
        self.assigned_channel_lock = asyncio.Lock()
        self.challonge = None
        self.token_task = self.bot.loop.create_task(self.challongetoken())
        self.clash = None
        self.crtoken_task = self.bot.loop.create_task(self.crtoken())

    async def crtoken(self):
        # Initialize clashroyale API
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token.get("token") is None:
            log.error(
                "CR Token is not SET. "
                "Use [p]set api clashroyale token,YOUR_TOKEN to set it"
            )
        else:
            self.clash = clashroyale.official_api.Client(
                token=token["token"],
                is_async=True,
                url="https://proxy.royaleapi.dev/v1",
            )

    async def challongetoken(self):
        """Set challonge api token."""
        token = await self.bot.get_shared_api_tokens("challonge")
        if token.get("token") is None or token.get("username") is None:
            log.error(
                "Challonge API not setup correctly. "
                "Use !set api challonge username,YOUR_USERNAME token,YOUR_CHALLONGE_TOKEN"
            )
            raise NoToken
        self.challonge = Account(token["username"], token["token"], timeout=60)

    def cog_unload(self):
        """Cleanup resources on cog unload."""
        if self.token_task:
            self.token_task.cancel()
        if self.challonge and not self.challonge._session.closed:
            self.bot.loop.create_task(self.challonge._session.close())

        if self.crtoken_task:
            self.crtoken_task.cancel()
        if self.clash:
            self.bot.loop.create_task(self.clash.close())

    # Completed
    @commands.command(name="createbracket")
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def command_createbracket(self, ctx: commands.Context, *, name: str):
        """Start a new tournament."""
        assigned_url = await self.config.guild(ctx.guild).tournament_url()
        tournament_name = await self.config.guild(ctx.guild).tournament_name()
        if assigned_url is None:
            url = "".join(
                random.choice(string.ascii_lowercase + string.digits) for _ in range(12)
            )
            try:
                tournament = await self.challonge.tournaments.create(
                    name=name, url=url, game_id=49390, game_name="Clash Royale"
                )
            except ChallongeException as e:
                log.exception("Error when creating tournament: ", exc_info=e)
                return await embed_helper(ctx, "Failed to create tournament")
            tournament_id = tournament["id"]
            url = tournament["full-challonge-url"]
            await self.config.guild(ctx.guild).tournament_id.set(tournament_id)
            await self.config.guild(ctx.guild).tournament_url.set(url)
            await self.config.guild(ctx.guild).tournament_name.set(name)
            await embed_helper(
                ctx, "Tournament named [{}]({}) has been created.".format(name, url)
            )
        else:
            await embed_helper(
                ctx,
                "A tournament, [{}]({}) is already running.".format(
                    tournament_name, assigned_url
                ),
            )

    # Completed
    @commands.command(name="registerteam")
    @commands.guild_only()
    @checks.bot_has_permissions(manage_roles=True)
    async def command_registerteam(
        self,
        ctx: commands.Context,
        user1: discord.Member,
        user2: discord.Member,
        *,
        name: str,
    ):
        """Register your team with you as captain."""
        url = await self.config.guild(ctx.guild).tournament_url()
        if url is None:
            return await embed_helper(ctx, "No tournaments running!")
        tournament = await self.config.guild(ctx.guild).tournament_id()
        try:
            start_time = (await self.challonge.tournaments.show(tournament=tournament))[
                "started-at"
            ]
        except ChallongeException as e:
            log.exception("Error when getting tournament info: ", exc_info=e)
            return await embed_helper(ctx, "Failed to get tournament info.")
        if start_time is not None:
            return await embed_helper(
                ctx, "Tournament has already been started. Registrations are closed."
            )

        if user1 == ctx.author or user2 == ctx.author:
            return await embed_helper(
                ctx,
                (
                    "You cannot add yourself more than once. "
                    "Maybe its your evil twin but they'll need to get their own discord."
                ),
            )
        if user1 == user2:
            return await embed_helper(
                ctx,
                "I am sorry. I see only one of {}. Now go get a third member.".format(
                    user1.mention
                ),
            )
        teams = await self.config.guild(ctx.guild).teams()
        captain_pokemons = set(await self.config.user(ctx.author).pokemons())
        user_1_pokemons = set(await self.config.user(user1).pokemons())
        user_2_pokemons = set(await self.config.user(user2).pokemons())
        if any(
            [len(p) != 2 for p in [captain_pokemons, user_1_pokemons, user_2_pokemons]]
        ):
            return await embed_helper(
                ctx, "Team members have not set their pokemon types."
            )
        # Each team member's pokemon type should be unique ie disjoint set
        if not set(captain_pokemons).isdisjoint(user_1_pokemons):
            return await embed_helper(
                ctx, f"{ctx.author.mention} has same pokemon type as {user1.mention}."
            )
        if not set(captain_pokemons).isdisjoint(user_2_pokemons):
            return await embed_helper(
                ctx, f"{ctx.author.mention} has same pokemon type as {user2.mention}."
            )
        if not set(user_2_pokemons).isdisjoint(user_1_pokemons):
            return await embed_helper(
                ctx, f"{user2.mention} has same pokemon type as {user1.mention}."
            )

        for team_id in teams.keys():
            if teams[team_id]["name"] == name:
                return await embed_helper(
                    ctx, "This name is already taken. Choose a better name."
                )
            if any(
                [u.id in teams[team_id]["players"] for u in [user1, user2, ctx.author]]
            ) or any(
                [u.id in teams[team_id]["subs"] for u in [user1, user2, ctx.author]]
            ):
                return await embed_helper(
                    ctx,
                    "A team member is already registered with team {}.".format(
                        teams[team_id]["name"]
                    ),
                )

        try:
            participant = await self.challonge.participants.create(
                tournament=tournament, name=name
            )
        except ChallongeException as e:
            log.exception("Error when registering team", exc_info=e)
            return await ctx.send(
                "Error when registering team.\nPlease contact the moderators with:`{}`".format(
                    e
                )
            )

        participant_id = participant["id"]
        async with self.config.guild(ctx.guild).teams() as teams:
            teams[participant_id] = {}
            teams[participant_id]["name"] = name
            teams[participant_id]["captain_id"] = ctx.author.id
            teams[participant_id]["players"] = [user1.id, user2.id, ctx.author.id]
            teams[participant_id]["pokemon_choices"] = list(
                list(captain_pokemons) + list(user_1_pokemons) + list(user_2_pokemons)
            )
            teams[participant_id]["subs"] = list()
        role = discord.utils.get(ctx.guild.roles, name=name)
        if role:
            return await embed_helper(
                ctx,
                "There is already a role with name {}. "
                "Please contact the moderators for the team roles.".format(name),
            )
        else:
            try:
                role = await ctx.guild.create_role(name=name)
            except discord.Forbidden:
                await embed_helper(
                    ctx, "Failed to create role. Ask the admins to give bot perms."
                )
        try:
            await ctx.author.add_roles(role)
            await user1.add_roles(role)
            await user2.add_roles(role)
        except discord.Forbidden:
            await embed_helper(
                ctx,
                "Failed to add role for one of team members. Please contact moderators.",
            )
        await embed_helper(ctx, "Team {} successfully registered.".format(name))
        await ctx.tick()

    # Completed
    @commands.command(name="registersubs")
    @commands.guild_only()
    @checks.bot_has_permissions(manage_roles=True)
    async def command_registersubs(
        self, ctx: commands.Context, team_name: str, *substitute_players: discord.Member
    ):
        """Register your subtitute players."""
        if not substitute_players:
            return await ctx.send_help()

        url = await self.config.guild(ctx.guild).tournament_url()
        if url is None:
            return await embed_helper(ctx, "No tournaments running!")
        tournament = await self.config.guild(ctx.guild).tournament_id()

        try:
            start_time = (await self.challonge.tournaments.show(tournament=tournament))[
                "started-at"
            ]
        except ChallongeException as e:
            log.exception("Error when getting tournament info: ", exc_info=e)
            return await embed_helper(ctx, "Failed to get tournament info.")
        if start_time is not None:
            return await embed_helper(
                ctx, "Tournament has already been started. Registrations are closed."
            )

        substitute_players = set(substitute_players)
        teams = await self.config.guild(ctx.guild).teams()
        team_id_to_modify = None

        if any(
            [
                len(set(await self.config.user(p).pokemons())) != 2
                for p in substitute_players
            ]
        ):
            return await embed_helper(
                ctx, "Some members have not set their pokemon types."
            )

        for team_id in teams.keys():
            # Need to iterate through all items even after match is found to check
            # if any of substitute players are registered with other teams
            if any([u.id in teams[team_id]["players"] for u in substitute_players]):
                return await embed_helper(
                    ctx,
                    f"A member is already registered as a team player with "
                    f"team {teams[team_id]['name']}",
                )
            if any([u.id in teams[team_id]["subs"] for u in substitute_players]):
                return await embed_helper(
                    ctx,
                    f"A member is already registered as a substitute player with "
                    f"team {teams[team_id]['name']}",
                )

            if teams[team_id]["name"] == team_name:
                if ctx.author.id != teams[team_id][
                    "captain_id"
                ] and not await self.bot.is_admin(ctx.author):
                    return await embed_helper(
                        ctx, "Only captains and admins are allowed to add players."
                    )
                team_id_to_modify = team_id

        if team_id_to_modify is None:
            return await embed_helper(ctx, f"No team named {team_name} found")
        role = discord.utils.get(ctx.guild.roles, name=team_name)
        if not role:
            return await embed_helper(
                ctx,
                f"There is no role with name {team_name}. "
                "Please contact the moderators for the team roles.",
            )
        async with self.config.guild(ctx.guild).teams() as teams:
            for substitute_player in substitute_players:
                teams[team_id_to_modify]["subs"].append(substitute_player.id)
                try:
                    await substitute_player.add_roles(role)
                except discord.Forbidden:
                    await embed_helper(
                        ctx, f"No permissions to add role for {substitute_player}"
                    )
                except discord.HTTPException:
                    await embed_helper(
                        ctx, f"Failed to add role for {substitute_player}"
                    )
        await embed_helper(
            ctx,
            f"Registered {humanize_list([p.mention for p in substitute_players])} as subs",
        )

    @commands.command(name="startbracket")
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.bot_has_permissions(manage_roles=True, manage_channels=True)
    async def command_startbracket(self, ctx: commands.Context):
        """Start the bracket and end registration."""
        tournament_url = await self.config.guild(ctx.guild).tournament_url()
        if tournament_url is None:
            return await embed_helper(ctx, "No tournaments running!")
        tournament = await self.config.guild(ctx.guild).tournament_id()
        tournament_name = await self.config.guild(ctx.guild).tournament_name()
        try:
            start_time = (await self.challonge.tournaments.show(tournament=tournament))[
                "started-at"
            ]
        except ChallongeException as e:
            log.exception("Error when getting tournament info: ", exc_info=e)
            return await embed_helper(ctx, "Failed to get tournament info.")
        if start_time is not None:
            return await embed_helper(ctx, "Tournament has already been started!")
        try:
            await self.discord_setup(ctx)
        except ExistingChannels:
            return
        except Exception as e:
            log.exception(
                "Encountered error when preparing server for upcoming battles.",
                exc_info=e,
            )
            await embed_helper(ctx, "Error when prepping up the gyms.")
            return
        try:
            await self.challonge.participants.randomize(tournament=tournament)
            await self.challonge.tournaments.start(tournament=tournament)
        except ChallongeException as e:
            log.exception("Error when starting tournament: ", exc_info=e)
            return await embed_helper(ctx, "Failed to start tournament.")
        await embed_helper(
            ctx,
            "Tournament [{}]({}) has been started.".format(
                tournament_name, tournament_url
            ),
        )

    @commands.command(name="updatescore")
    @commands.guild_only()
    @checks.bot_has_permissions(manage_roles=True)
    async def command_updatescore(self, ctx: commands.Context, *, team_name: str):
        """Report win for a team."""
        channel_id = await self.config.guild(ctx.guild).channel_id()
        channel = ctx.guild.get_channel(channel_id)
        url = await self.config.guild(ctx.guild).tournament_url()
        tournament = await self.config.guild(ctx.guild).tournament_id()
        if url is None:
            return await embed_helper(ctx, "No tournaments running!")
        try:
            start_time = (await self.challonge.tournaments.show(tournament=tournament))[
                "started-at"
            ]
        except ChallongeException as e:
            log.exception("Error when getting tournament info: ", exc_info=e)
            return await embed_helper(ctx, "Failed to get tournament info.")
        if start_time is None:
            return await embed_helper(ctx, "Tournament has not been started.")

        match_found = False
        team_found = False
        teams_data = await self.config.guild(ctx.guild).teams()
        for team_id in teams_data.keys():
            if teams_data[team_id]["name"] == team_name:
                if ctx.author.id != teams_data[team_id][
                    "captain_id"
                ] and not await self.bot.is_admin(ctx.author):
                    return await embed_helper(
                        ctx, "Only captains and admins are allowed to update wins."
                    )
                team_found = True
                try:
                    matches_list = await self.challonge.matches.index(
                        tournament=tournament
                    )
                except ChallongeException as e:
                    log.exception("Error when getting match info: ", exc_info=e)
                    return await embed_helper(ctx, "Failed to get match info.")
                async for single_match_data in AsyncIter(matches_list):
                    if single_match_data["state"] == "open":
                        if (
                            int(team_id) == single_match_data["player1-id"]
                            or int(team_id) == single_match_data["player2-id"]
                        ):
                            if int(team_id) == single_match_data["player1-id"]:
                                scores = "1-0"
                            else:
                                scores = "0-1"
                            match_id = single_match_data["id"]
                            try:
                                await self.challonge.matches.update(
                                    tournament=tournament,
                                    match_id=match_id,
                                    winner_id=team_id,
                                    scores_csv=scores,
                                )
                            except ChallongeException as e:
                                log.exception("Error when updating score: ", exc_info=e)
                                return await embed_helper(
                                    ctx, "Failed to update score."
                                )

                            async with self.assigned_channel_lock:
                                # Revoke perms for players
                                assigned_channels = await self.config.guild(
                                    ctx.guild
                                ).assigned_channels()
                                team_1_id = str(single_match_data["player1-id"])
                                team_1_name = teams_data[str(team_1_id)]["name"]
                                team_1_channel_id = assigned_channels.get(
                                    team_1_name, None
                                )
                                team_2_id = str(single_match_data["player2-id"])
                                team_2_name = teams_data[str(team_2_id)]["name"]
                                team_2_channel_id = assigned_channels.get(
                                    team_2_name, None
                                )

                                if team_1_channel_id != team_2_channel_id:
                                    await embed_helper(
                                        ctx,
                                        "Something is wrong with the bot data. "
                                        "Please contact the admins.",
                                    )
                                team_1_role = discord.utils.get(
                                    ctx.guild.roles, name=team_1_name
                                )
                                team_2_role = discord.utils.get(
                                    ctx.guild.roles, name=team_2_name
                                )
                                badge_to_award = None
                                for gym in self.gyms.values():
                                    if gym["level"] == (single_match_data["round"] - 1):
                                        badge_to_award = gym["badge"]
                                        break
                                badge_role = discord.utils.get(
                                    ctx.guild.roles, name=badge_to_award
                                )
                                if badge_role:
                                    for player_id in teams_data[team_id]["players"]:
                                        player = ctx.guild.get_member(player_id)
                                        await player.add_roles(badge_role)
                                    for player_id in teams_data[team_id]["subs"]:
                                        player = ctx.guild.get_member(player_id)
                                        await player.add_roles(badge_role)
                                team_1_channel = self.bot.get_channel(team_1_channel_id)
                                team_2_channel = self.bot.get_channel(team_2_channel_id)
                                if team_1_channel:
                                    await team_1_channel.set_permissions(
                                        team_1_role,
                                        read_messages=False,
                                        send_messages=False,
                                    )
                                if team_2_channel:
                                    await team_2_channel.set_permissions(
                                        team_2_role,
                                        read_messages=False,
                                        send_messages=False,
                                    )
                                assigned_channels[team_1_name] = None
                                assigned_channels[team_2_name] = None
                                await self.config.guild(
                                    ctx.guild
                                ).assigned_channels.set(assigned_channels)

                            match_found = True
                            break
                if match_found:  # search for next match
                    new_match_found = False
                    try:
                        matches_list = await self.challonge.matches.index(
                            tournament=tournament
                        )
                    except ChallongeException as e:
                        log.exception("Error when getting match info: ", exc_info=e)
                        return await embed_helper(ctx, "Failed to get match info.")
                    async for single_match in AsyncIter(matches_list):
                        if single_match["state"] == "open":
                            if (
                                int(team_id) == single_match["player1-id"]
                                or int(team_id) == single_match["player2-id"]
                            ):
                                new_match_found = True
                                team_1_id = str(single_match["player1-id"])
                                team_2_id = str(single_match["player2-id"])
                                teams = await self.config.guild(ctx.guild).teams()
                                team_1_captain_id = teams[team_1_id]["captain_id"]
                                team_2_captain_id = teams[team_2_id]["captain_id"]
                                team_1_captain = ctx.guild.get_member(team_1_captain_id)
                                team_2_captain = ctx.guild.get_member(team_2_captain_id)
                                team_1_name = teams[team_1_id]["name"]
                                team_2_name = teams[team_2_id]["name"]

                                async with self.assigned_channel_lock:
                                    assigned_channels = await self.config.guild(
                                        ctx.guild
                                    ).assigned_channels()
                                    team_1_channel_id = assigned_channels.get(
                                        team_1_name, None
                                    )
                                    team_2_channel_id = assigned_channels.get(
                                        team_2_name, None
                                    )
                                    current_gym = None
                                    for gym in self.gyms.values():
                                        if gym["level"] == (single_match["round"] - 1):
                                            current_gym = gym
                                            break
                                    team_1_role = discord.utils.get(
                                        ctx.guild.roles, name=team_1_name
                                    )
                                    team_2_role = discord.utils.get(
                                        ctx.guild.roles, name=team_2_name
                                    )
                                    all_channels = (
                                        await self.config.guild(
                                            ctx.guild
                                        ).gym_channels()
                                    )[current_gym["name"]]

                                    team_channel = None
                                    if (
                                        team_1_channel_id is not None
                                        and team_2_channel_id is not None
                                    ):
                                        # If both are not None check
                                        # if they are in channel for their respective gym
                                        # If they are not in proper gym channels,
                                        # remove access to other gyms
                                        team_1_channel = self.bot.get_channel(
                                            team_1_channel_id
                                        )
                                        team_2_channel = self.bot.get_channel(
                                            team_2_channel_id
                                        )

                                        if (
                                            team_1_channel is None
                                            or (
                                                team_1_channel.category.name
                                                != current_gym["name"]
                                            )
                                            or team_2_channel is None
                                            or (
                                                team_2_channel.category.name
                                                != current_gym["name"]
                                            )
                                            or team_1_channel_id != team_2_channel_id
                                        ):
                                            if team_1_channel:
                                                await team_1_channel.set_permissions(
                                                    team_1_role,
                                                    read_messages=False,
                                                    send_messages=False,
                                                )
                                            if team_2_channel:
                                                await team_2_channel.set_permissions(
                                                    team_2_role,
                                                    read_messages=False,
                                                    send_messages=False,
                                                )
                                        else:
                                            team_channel = team_1_channel
                                    elif team_1_channel_id is not None:
                                        # remove its perms and assign to new channel
                                        team_1_channel = self.bot.get_channel(
                                            team_1_channel_id
                                        )
                                        if team_1_channel:
                                            await team_1_channel.set_permissions(
                                                team_1_role,
                                                read_messages=False,
                                                send_messages=False,
                                            )
                                    elif team_2_channel_id is not None:
                                        team_2_channel = self.bot.get_channel(
                                            team_2_channel_id
                                        )
                                        if team_2_channel:
                                            await team_2_channel.set_permissions(
                                                team_2_role,
                                                read_messages=False,
                                                send_messages=False,
                                            )
                                    if not team_channel:
                                        assignable_channels = list(
                                            [
                                                channel
                                                for channel in all_channels
                                                if channel
                                                not in assigned_channels.values()
                                            ]
                                        )
                                        if len(assignable_channels) < 1:
                                            await embed_helper(
                                                ctx,
                                                f"Gym {current_gym['name']} "
                                                "does not currently have a gym leader. "
                                                "Please ask the moderators to summon them.",
                                            )
                                        else:
                                            team_channel = self.bot.get_channel(
                                                assignable_channels[0]
                                            )
                                    if team_channel:
                                        await team_channel.set_permissions(
                                            team_1_role,
                                            read_messages=True,
                                            send_messages=True,
                                        )
                                        await team_channel.set_permissions(
                                            team_2_role,
                                            read_messages=True,
                                            send_messages=True,
                                        )
                                        assigned_channels[team_1_name] = team_channel.id
                                        assigned_channels[team_2_name] = team_channel.id
                                    await self.config.guild(
                                        ctx.guild
                                    ).assigned_channels.set(assigned_channels)

                                message = "{} vs {}\nCaptains: {}  {}\nGym: {}".format(
                                    team_1_name,
                                    team_2_name,
                                    team_1_captain.mention,
                                    team_2_captain.mention,
                                    current_gym["name"],
                                )
                                embed = discord.Embed(
                                    description=message, color=discord.Colour.blue()
                                )
                                if channel:
                                    return await channel.send(
                                        content=f"{team_1_captain.mention}{team_2_captain.mention}",
                                        embed=embed,
                                        allowed_mentions=discord.AllowedMentions(
                                            users=True
                                        ),
                                    )
                                else:
                                    await embed_helper(
                                        ctx,
                                        f"Announcement channel not set. "
                                        f"Use {ctx.prefix}setleaguechannel command",
                                    )

                    if not new_match_found:
                        await embed_helper(
                            ctx,
                            "Thanks for updating the scores. "
                            "You don't have any new matches pending as of now.",
                        )
                elif not match_found:
                    await embed_helper(
                        ctx,
                        "You have either been eliminated or your match is still pending, "
                        "check [bracket]({}).".format(url),
                    )
        if not team_found:
            await embed_helper(ctx, f"Team {team_name} not found")

    # Completed
    @commands.command(name="changecaptain")
    async def command_changecaptain(
        self, ctx: commands.Context, team_name: str, new_captain: discord.Member
    ):
        """Change captain to new one."""
        team_found = False
        teams_data = await self.config.guild(ctx.guild).teams()
        for team_id in teams_data.keys():
            # Need to iterate through all data even after match if found in order to check if
            # new captain is registered with another team
            if (
                new_captain.id in teams_data[team_id]["players"]
                and teams_data[team_id]["name"] != team_name
            ):
                return await embed_helper(
                    ctx,
                    f"Player {new_captain.mention} is already registered with team "
                    f"{teams_data[team_id]['name']}",
                )
            if teams_data[team_id]["name"] == team_name:
                team_found = True
                if ctx.author.id != teams_data[team_id][
                    "captain_id"
                ] and not await self.bot.is_admin(ctx.author):
                    return await embed_helper(
                        ctx, "Only captains and admins are allowed to change captains."
                    )
                if new_captain.id not in teams_data[team_id]["players"]:
                    return await embed_helper(
                        ctx,
                        f"{new_captain.mention} is not a team member for {team_name}",
                    )
                if new_captain.id == teams_data[team_id]["captain_id"]:
                    await ctx.send("You assigning yourself as captain: ")
                    return await ctx.send(
                        "https://i.kym-cdn.com/entries/icons/facebook/000/030/329/cover1.jpg"
                    )
                teams_data[team_id]["captain_id"] = new_captain.id

        if team_found:
            await self.config.guild(ctx.guild).teams.set(teams_data)
        else:
            await embed_helper(ctx, f"Team {team_name} not found")
        await ctx.tick()

    # TODO: Optimize assignment of channel
    @commands.command(name="makematches")
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.bot_has_permissions(manage_roles=True, manage_channels=True)
    async def command_makematches(self, ctx: commands.Context):
        """Post matches in channel."""
        url = await self.config.guild(ctx.guild).tournament_url()
        tournament = await self.config.guild(ctx.guild).tournament_id()
        if url is None:
            return await embed_helper(ctx, "No tournaments running!")
        try:
            start_time = (await self.challonge.tournaments.show(tournament=tournament))[
                "started-at"
            ]
        except ChallongeException as e:
            log.exception("Error when getting tournament info: ", exc_info=e)
            return await embed_helper(ctx, "Failed to get tournament info.")
        if start_time is None:
            return await embed_helper(ctx, "Tournament has not been started.")
        channel_id = await self.config.guild(ctx.guild).channel_id()
        channel = ctx.guild.get_channel(channel_id)
        try:
            all_matches = await self.challonge.matches.index(tournament=tournament)
        except ChallongeException as e:
            log.exception("Error when getting match info: ", exc_info=e)
            return await embed_helper(ctx, "Failed to get match info.")
        async for single_match in AsyncIter(all_matches):
            if single_match["state"] == "open":
                team_1_id = str(single_match["player1-id"])
                team_2_id = str(single_match["player2-id"])
                teams = await self.config.guild(ctx.guild).teams()
                team_1_captain_id = teams[str(team_1_id)]["captain_id"]
                team_2_captain_id = teams[str(team_2_id)]["captain_id"]
                team_1_captain = ctx.guild.get_member(team_1_captain_id)
                team_2_captain = ctx.guild.get_member(team_2_captain_id)
                team_1_name = teams[str(team_1_id)]["name"]
                team_2_name = teams[str(team_2_id)]["name"]
                current_gym = None
                async with self.assigned_channel_lock:
                    assigned_channels = await self.config.guild(
                        ctx.guild
                    ).assigned_channels()

                    team_1_channel_id = assigned_channels.get(team_1_name, None)
                    team_2_channel_id = assigned_channels.get(team_2_name, None)
                    for gym in self.gyms.values():
                        if gym["level"] < (single_match["round"] - 1):
                            for player_id in teams[str(team_1_id)]["players"]:
                                player = ctx.guild.get_member(player_id)
                                if player:
                                    badge_role = discord.utils.get(
                                        ctx.guild.roles, name=gym["badge"]
                                    )
                                    if badge_role:
                                        player.add_roles(badge_role)
                                    else:
                                        await embed_helper(
                                            ctx, f"Role {gym['badge']} not found"
                                        )
                                else:
                                    await embed_helper(
                                        ctx, f"Player {player_id} not found"
                                    )
                            for player_id in teams[str(team_2_id)]["players"]:
                                player = ctx.guild.get_member(player_id)
                                if player:
                                    badge_role = discord.utils.get(
                                        ctx.guild.roles, name=gym["badge"]
                                    )
                                    if badge_role:
                                        player.add_roles(badge_role)
                                    else:
                                        await embed_helper(
                                            ctx, f"Role {gym['badge']} not found"
                                        )
                                else:
                                    await embed_helper(
                                        ctx, f"Player {player_id} not found"
                                    )
                        if gym["level"] == (single_match["round"] - 1):
                            current_gym = gym
                            break
                    team_1_role = discord.utils.get(ctx.guild.roles, name=team_1_name)
                    team_2_role = discord.utils.get(ctx.guild.roles, name=team_2_name)
                    all_channels = (await self.config.guild(ctx.guild).gym_channels())[
                        current_gym["name"]
                    ]
                    team_channel = None
                    if team_1_channel_id is not None and team_2_channel_id is not None:
                        # If both are not None check if they are in proper channel
                        # If they are not in proper gym channels, remove access to other gyms
                        team_1_channel = self.bot.get_channel(team_1_channel_id)
                        team_2_channel = self.bot.get_channel(team_2_channel_id)

                        if (
                            team_1_channel is None
                            or (team_1_channel.category.name != current_gym["name"])
                            or team_2_channel is None
                            or (team_2_channel.category.name != current_gym["name"])
                            or team_1_channel_id != team_2_channel_id
                        ):
                            if team_1_channel:
                                await team_1_channel.set_permissions(
                                    team_1_role,
                                    read_messages=False,
                                    send_messages=False,
                                )
                            if team_2_channel:
                                await team_2_channel.set_permissions(
                                    team_2_role,
                                    read_messages=False,
                                    send_messages=False,
                                )
                        else:
                            team_channel = team_1_channel
                    elif team_1_channel_id is not None:
                        # If one is not None, remove its perms and assign to new channel
                        team_1_channel = self.bot.get_channel(team_1_channel_id)
                        if team_1_channel:
                            await team_1_channel.set_permissions(
                                team_1_role, read_messages=False, send_messages=False
                            )
                    elif team_2_channel_id is not None:
                        team_2_channel = self.bot.get_channel(team_2_channel_id)
                        if team_2_channel:
                            await team_2_channel.set_permissions(
                                team_2_role, read_messages=False, send_messages=False
                            )
                    if not team_channel:
                        available_channels = list(
                            [
                                ch
                                for ch in all_channels
                                if ch not in assigned_channels.values()
                            ]
                        )

                        if len(available_channels) > 0:
                            team_channel = self.bot.get_channel(available_channels[0])
                        else:
                            await embed_helper(
                                ctx,
                                f"Gym {current_gym['name']} does not currently have a gym leader. "
                                "Please ask the moderators to summon them.",
                            )
                    if team_channel:
                        await team_channel.set_permissions(
                            team_1_role, read_messages=True, send_messages=True
                        )
                        await team_channel.set_permissions(
                            team_2_role, read_messages=True, send_messages=True
                        )
                        assigned_channels[team_1_name] = team_channel.id
                        assigned_channels[team_2_name] = team_channel.id
                    await self.config.guild(ctx.guild).assigned_channels.set(
                        assigned_channels
                    )

                    message = "{} vs {}\nCaptains: {}  {}\nGym: {}".format(
                        team_1_name,
                        team_2_name,
                        team_1_captain.mention,
                        team_2_captain.mention,
                        current_gym["name"],
                    )
                    embed = discord.Embed(
                        description=message, color=discord.Colour.blue()
                    )
                    if channel:
                        return await channel.send(
                            content=f"{team_1_captain.mention} {team_2_captain.mention}",
                            embed=embed,
                            allowed_mentions=discord.AllowedMentions(users=True),
                        )
                    else:
                        await embed_helper(
                            ctx,
                            f"Announcement channel not set. "
                            f"Use {ctx.prefix}setleaguechannel command",
                        )

    # Completed
    @commands.command(name="deletebracket")
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.bot_has_permissions(manage_roles=True, add_reactions=True)
    async def command_deletebracket(self, ctx: commands.Context):
        """Delete a bracket from bot and optionally from challonge site too."""
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
                except discord.Forbidden:
                    await embed_helper(
                        ctx, "No permissions to delete role {}".format(role.mention)
                    )
                except discord.HTTPException:
                    await embed_helper(
                        ctx, "Failed to delete role {}".format(role.mention)
                    )
        await self.config.guild(ctx.guild).clear()
        await embed_helper(
            ctx,
            "Bracket has been removed from the bot but still can be accessed [here]({}).".format(
                url
            ),
        )
        msg = await embed_helper(
            ctx, "Do you want to delete from the challonge site too?"
        )
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)
        if pred.result is True:
            try:
                await self.challonge.tournaments.destroy(tournament)
            except ChallongeException as e:
                log.exception("Error when deleting tournament: ", exc_info=e)
                return await embed_helper(ctx, "Failed to delete tournament.")
        await self.config.guild(ctx.guild).channel_id.set(channel_id)
        await ctx.tick()

    # Completed
    @commands.command(name="deletebadgechannels")
    @checks.admin()
    @checks.bot_has_permissions(manage_channels=True)
    async def command_deletebadgechannels(self, ctx: commands.Context):
        """
        Delete all text channels with badge in their name.

        To be used when tournament ends to prepare for next tournament
        """
        url = await self.config.guild(ctx.guild).tournament_url()
        if url:
            return await embed_helper(
                ctx,
                (
                    "There is a tournament running in the server! "
                    "You cannot delete channels without finishing the tournament."
                ),
            )
        await ctx.send(
            (
                "This command will delete all channels that have `badge` in their name. "
                "Are you sure you want to do that?"
            )
        )
        pred = MessagePredicate.yes_or_no(ctx)
        await self.bot.wait_for("message", check=pred)
        if pred.result is False:
            return await ctx.send("You have chosen not to delete the channels.")
        for channel in ctx.guild.text_channels:
            if "badge" in channel.name:
                try:
                    await channel.delete()
                except discord.Forbidden:
                    return await embed_helper(
                        ctx, f"No permission to delete channel {channel.name}."
                    )
                except discord.HTTPException:
                    return await embed_helper(
                        ctx, f"Error when deleting channel {channel.name}."
                    )
        await ctx.tick()

    # Completed
    @commands.command(name="resetbadges")
    @checks.admin()
    @checks.bot_has_permissions(manage_roles=True)
    async def command_resetbadges(self, ctx: commands.Context):
        """Remove badge from all guild members."""
        url = await self.config.guild(ctx.guild).tournament_url()
        if url:
            return await embed_helper(
                ctx,
                "There is a tournament running in the server! "
                "You cannot reset without finishing the tournament.",
            )
        await ctx.send(
            (
                "This command will delete all badge roles. Are you sure you want to do that?"
            )
        )
        pred = MessagePredicate.yes_or_no(ctx)
        await self.bot.wait_for("message", check=pred)
        if not pred.result:
            return await ctx.send("You have chosen not to reset the badges.")

        gym_badges = [g["badge"] for g in self.gyms.values()]
        for badge_name in gym_badges:
            for role in ctx.guild.roles:
                if role.name == badge_name:
                    member_list = role.members
                    for member in member_list:
                        try:
                            await member.remove_roles(role)
                        except discord.Forbidden:
                            return await embed_helper(
                                ctx,
                                f"No permission to remove roles for {member.mention}",
                            )
                        except discord.HTTPException:
                            return await embed_helper(
                                ctx, f"Error when removing roles for {member.mention}"
                            )
        await ctx.tick()

    # Completed
    @commands.command(name="setleaguechannel")
    @checks.admin_or_permissions()
    async def command_setleaguechannel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        """Set announcement channel for matches."""
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.tick()

    # Completed
    @commands.command(name="choosepokemontype")
    @commands.guild_only()
    @checks.bot_has_permissions(manage_roles=True)
    async def command_choosepokemontype(
        self, ctx: commands.Context, pokemontype1, pokemontype2
    ):
        """Choose your pokemon types."""
        teams_data = await self.config.guild(ctx.guild).teams()
        for team in teams_data.values():
            if ctx.author.id in team["players"]:
                return await embed_helper(
                    ctx, f"You are already registered for team {team['name']}"
                )
        valid_types = [name.split(" ")[0].lower() for name in self.pokemons.keys()]
        pokemon_role_names = [
            (pokemon.lower().capitalize().split(" ")[0] + " Player")
            for pokemon in self.pokemons.keys()
        ]
        if pokemontype1.lower() not in valid_types:
            return await embed_helper(
                ctx, f"{pokemontype1} is not a valid pokemon type."
            )
        if pokemontype2.lower() not in valid_types:
            return await embed_helper(
                ctx, f"{pokemontype2} is not a valid pokemon type."
            )
        await self.config.user(ctx.author).pokemons.set(
            [pokemontype1.lower(), pokemontype2.lower()]
        )
        for pokemon_role_name in pokemon_role_names:
            poke_role = discord.utils.get(ctx.author.roles, name=pokemon_role_name)
            if poke_role:
                try:
                    await ctx.author.remove_roles(poke_role)
                except discord.Forbidden:
                    return await embed_helper(
                        ctx, f"No permission to remove roles for {ctx.author.mention}"
                    )
                except discord.HTTPException:
                    return await embed_helper(
                        ctx, "Error when removing roles for {ctx.author.mention}."
                    )

        poke1_role = discord.utils.get(
            ctx.guild.roles,
            name=(pokemontype1.lower().capitalize().split(" ")[0] + " Player"),
        )
        if poke1_role:
            try:
                await ctx.author.add_roles(poke1_role)
            except discord.Forbidden:
                return await embed_helper(
                    ctx, f"No permission to remove roles for {ctx.author.mention}"
                )
            except discord.HTTPException:
                return await embed_helper(
                    ctx, "Error when removing roles for {ctx.author.mention}."
                )

        poke2_role = discord.utils.get(
            ctx.guild.roles,
            name=(pokemontype2.lower().capitalize().split(" ")[0] + " Player"),
        )
        if poke2_role:
            try:
                await ctx.author.add_roles(poke2_role)
            except discord.Forbidden:
                return await embed_helper(
                    ctx, f"No permission to remove roles for {ctx.author.mention}"
                )
            except discord.HTTPException:
                return await embed_helper(
                    ctx, "Error when removing roles for {ctx.author.mention}."
                )

        await ctx.tick()

    # Completed
    @commands.command(name="showtypes")
    async def showtypes(self, ctx, *, pokemon_type=None):
        """Show all cards of specific type if type is mentioned and all types if type is not specified."""
        if pokemon_type:
            cards = None
            for p_type in self.pokemons.keys():
                if p_type.lower().split()[0] == pokemon_type.lower():
                    cards = self.pokemons.get(p_type)
            if not cards:
                return await embed_helper(
                    ctx, f"{pokemon_type} is not recognized as a valid pokemon type."
                )
            else:
                embed = discord.Embed(color=0xFAA61A,)
                embed.set_author(name="Pokemon card index")
                value = ["\u200b\n"]
                for card in cards:
                    emoji = await self.get_card_emoji(card)
                    if emoji:
                        value.append(emoji)
                    else:
                        value.append(f" {card} ")
                if len(value):
                    value = " ".join(value)
                    embed.add_field(
                        name=f"{pokemon_type.lower().capitalize()} cards",
                        value=value,
                        inline=False,
                    )
                return await ctx.send(embed=embed)

        pages = []
        for pokemon_type in self.pokemons.keys():
            cards = self.pokemons[pokemon_type]
            embed = discord.Embed(color=0xFAA61A)
            embed.set_author(name="Pokemon card index")
            value = ["\u200b\n"]
            for card in cards:
                emoji = await self.get_card_emoji(card)
                if emoji:
                    value.append(emoji)
                else:
                    value.append(f" {card} ")
            if len(value):
                value = " ".join(value)
                embed.add_field(
                    name=f"{pokemon_type.lower().capitalize()} cards",
                    value=value,
                    inline=False,
                )
                pages.append(embed)
        return await menu(ctx, pages, DEFAULT_CONTROLS, timeout=120)

    # Completed
    @commands.command(name="showcardtype")
    async def command_showcardtype(self, ctx: commands.Context, *, card_names: str):
        """Show type of card."""
        url = "https://docs.google.com/spreadsheets/d/1TIH9iwTb9UpHYWKIgHpY72wizLSp79ROt4D4lWe8YIM/edit?usp=sharing"
        for card_name in card_names.split(";"):
            card_name = card_name.strip()
            card_type = []
            for pokemon_type in self.pokemons.keys():
                cards = self.pokemons[pokemon_type]
                for card in cards:
                    if card.lower() == card_name.lower():
                        card_name = card
                        card_type.append(pokemon_type.split()[0])
            if len(card_type) > 0:
                await embed_helper(
                    ctx, f"{card_name} belongs to  {humanize_list(card_type)} types."
                )
            else:
                await embed_helper(
                    ctx,
                    "Cannot find card {}. Please use the [spreadsheet]({}).".format(
                        card_name, url
                    ),
                )

    # Completed
    @commands.command(name="checkdeck")
    async def command_checkdeck(
        self, ctx: commands.Context, member: discord.Member, deck_url: str
    ):
        """Check if cards are valid types according to member's pokemons."""
        is_valid = re.search(
            r"(http|ftp|https)://link.clashroyale.com/deck/en\?deck=[0-9;]+", deck_url
        )
        if not is_valid:
            return await embed_helper(ctx, "Deck url is not valid.")
        deck_cards = re.findall("2[0-9]{7}", deck_url)

        user_pokemon_types = await self.config.user(member).pokemons()
        if len(user_pokemon_types) != 2:
            return await embed_helper(
                ctx, f"{member.mention} has not set their pokemon types"
            )
        await embed_helper(
            ctx,
            f"Member {member.mention} has chosen types:\n{humanize_list(user_pokemon_types)}",
        )
        valid_card_names = []
        invalid_card_names = []
        # cog = self.bot.get_cog("ClashRoyaleClans")
        if not self.clash:
            return await embed_helper(ctx, "Not connected to clash royale servers.")
        try:
            all_cards = list(await self.clash.get_all_cards())
        except clashroyale.RequestError:
            return await embed_helper(ctx, "Cannot reach clashroyale servers!")
        for card in all_cards:
            if str(card.id) in deck_cards:
                for pokemon_type in self.pokemons.keys():
                    if card.name in self.pokemons[pokemon_type]:
                        if pokemon_type.split(" ")[0].lower() not in user_pokemon_types:
                            invalid_card_names.append(card.name)
                        else:
                            valid_card_names.append(card.name)
                            break

        # Account for card having two types.
        # If a card is both bug and steel type and user has chosen
        # bug type but not steel, it will be in both valid and invalid card list
        invalid_card_names = list(set(invalid_card_names))
        invalid_card_names = [
            i for i in invalid_card_names if i not in valid_card_names
        ]

        if invalid_card_names:
            return await embed_helper(
                ctx,
                (
                    f"The deck has {len(invalid_card_names)} invalid cards:\n"
                    + humanize_list(
                        [
                            (await self.get_card_emoji(c) or c)
                            for c in invalid_card_names
                        ]
                    )
                ),
            )
        else:
            return await embed_helper(ctx, "All cards are valid.")

    # Completed
    async def get_team_embed(self, ctx: commands.Context, team_id):
        """Prepare embed for team with given team_id."""
        teams = await self.config.guild(ctx.guild).teams()
        url = await self.config.guild(ctx.guild).tournament_url()
        team = teams[team_id]
        captain_id = team["captain_id"]
        players_id = team["players"]
        players_id.remove(captain_id)
        subs_id = team["subs"]
        embed = discord.Embed(colour=0xFAA61A, title=team["name"], url=url)
        captain = ctx.guild.get_member(captain_id)
        embed.add_field(name="Captain", value=captain.mention, inline=False)
        player_list = " ".join(
            [ctx.guild.get_member(player_id).mention for player_id in players_id]
        )
        sub_list = (
            " ".join([ctx.guild.get_member(sub_id).mention for sub_id in subs_id])
            or "None"
        )
        embed.add_field(name="Team Players", value=player_list, inline=False)
        embed.add_field(name="Substitute Players", value=sub_list, inline=False)
        pokemons = humanize_list(team["pokemon_choices"])
        embed.add_field(name="Pokemons", value=pokemons, inline=False)
        return embed

    # Completed
    @commands.command(name="showteam")
    @commands.guild_only()
    async def command_showteam(self, ctx: commands.Context, *, team_name: str):
        """Display data for a team."""
        team_found = False
        url = await self.config.guild(ctx.guild).tournament_url()
        if url is None:
            return await embed_helper(ctx, "No tournaments running!")
        teams = await self.config.guild(ctx.guild).teams()
        for id, team in teams.items():
            if team["name"] == team_name:
                team_found = True
                embed = await self.get_team_embed(ctx, id)
                await ctx.send(embed=embed)
                break
        if not team_found:
            await embed_helper(ctx, "Team not found")

    # Completed
    @commands.command(name="showallteams")
    @commands.guild_only()
    async def command_showallteams(self, ctx: commands.Context, pagify: bool = True):
        """Show all teams as menu if pagify is true and as list of embeds if pagify is false."""
        url = await self.config.guild(ctx.guild).tournament_url()
        if url is None:
            return await embed_helper(ctx, "No tournaments running!")
        teams = await self.config.guild(ctx.guild).teams()
        pages = []
        for id in teams.keys():
            embed = await self.get_team_embed(ctx, id)
            pages.append(embed)
        if not pages:
            return await embed_helper(ctx, "No teams to show")
        if pagify:
            if pages:
                return await menu(ctx, pages, DEFAULT_CONTROLS, timeout=120)
        else:
            for page in pages:
                await ctx.send(embed=page)

    # Completed
    @commands.command(name="removeteam")
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.bot_has_permissions(manage_roles=True)
    async def command_removeteam(self, ctx: commands.Context, *, team_name: str):
        """Remove a team from the tournament. Cannot be done after starting the bracket."""
        url = await self.config.guild(ctx.guild).tournament_url()
        if url is None:
            return await embed_helper(ctx, "No tournaments running!")
        tournament_id = await self.config.guild(ctx.guild).tournament_id()
        try:
            start_time = (
                await self.challonge.tournaments.show(tournament=tournament_id)
            )["started-at"]
        except ChallongeException as e:
            log.exception("Error when getting tournament info: ", exc_info=e)
            return await embed_helper(ctx, "Failed to get tournament info.")
        if start_time is not None:
            return await embed_helper(ctx, "Tournament has already been started!")
        tournament_name = await self.config.guild(ctx.guild).tournament_name()
        team_found = False

        teams = await self.config.guild(ctx.guild).teams()
        for team_id, team_data in teams.items():
            if team_data["name"] == team_name:
                team_found = True
                try:
                    await self.challonge.participants.destroy(tournament_id, team_id)
                except ChallongeException as e:
                    log.exception(
                        f"Error when removing participant from tournament {tournament_name}",
                        exc_info=e,
                    )
                    return await embed_helper(ctx, f"An error has occurred:\n`{e}`")
                async with self.config.guild(ctx.guild).teams() as all_teams:
                    del all_teams[team_id]
                try:
                    role = discord.utils.get(ctx.guild.roles, name=team_name)
                    if role:
                        await role.delete()
                except discord.Forbidden:
                    return await embed_helper(ctx, f"Failed to delete role {team_name}")
                return await embed_helper(
                    ctx,
                    "Team {} has been removed from {}".format(
                        team_name, tournament_name
                    ),
                )
        if not team_found:
            await embed_helper(ctx, "Team {} not found".format(team_name))

    @commands.command(name="substituteplayer")
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.bot_has_permissions(manage_roles=True)
    async def command_substituteplayer(
        self,
        ctx: commands.Context,
        team_name: str,
        team_player: discord.Member,
        substitute_player: discord.Member,
    ):
        """Replace team member with substitute player."""
        url = await self.config.guild(ctx.guild).tournament_url()
        if url is None:
            return await embed_helper(ctx, "No tournaments running!")
        team_found = False
        teams = await self.config.guild(ctx.guild).teams()
        for team_id, team_data in teams.items():
            if team_data["name"] == team_name:
                team_found = True
                if team_player not in team_data["players"]:
                    return await embed_helper(
                        ctx, f"{team_player} is not a member of team {team_name}"
                    )
                if substitute_player not in team_data["subs"]:
                    return await embed_helper(
                        ctx,
                        f"{substitute_player} is not a substitute of team {team_name}",
                    )
                if team_player == team_data["captain_id"]:
                    return await embed_helper(ctx, "You cannot switch out the captain")
                teams[team_id]["subs"] = [
                    i for i in team_data["subs"] if i != substitute_player.id
                ] + [team_player.id]
                teams[team_id]["players"] = [
                    i for i in team_data["players"] if i != team_player.id
                ] + [substitute_player.id]
                break
        if team_found:
            await self.config.guild(ctx.guild).teams.set(teams)
        else:
            await embed_helper(ctx, f"Team {team_name} not found")
        await ctx.tick()

    async def get_card_emoji(self, card_name: str):
        """Return card emote from name or empty string."""
        if not self.constants:
            return ""
        card_key = await self.constants.card_to_key(card_name)
        emoji = ""
        if card_key:
            emoji = self.emoji(card_key)
        if emoji == "":
            emoji = self.emoji(card_name)
        return emoji

    def emoji(self, name: str):
        """Emoji by name."""
        for emoji in self.bot.emojis:
            if emoji.name == name.replace(" ", "").replace("-", "").replace(".", ""):
                return "<:{}:{}>".format(emoji.name, emoji.id)
        return ""

    async def discord_setup(self, ctx: commands.Context):
        """Prepare guild for tournament."""
        teams = await self.config.guild(ctx.guild).teams()
        pokemon_types = [name.split(" ")[0] for name in self.pokemons.keys()]
        number_of_gyms = int(math.floor(math.log(len(teams), 2)))
        # number of people eliminated in first round to make number
        # of teams power of 2 is distance to nearest power of 2
        first_elimination = int(len(teams) - 2 ** number_of_gyms)
        number_of_gyms += 1 if first_elimination > 0 else 0

        log.info("{} gyms required for {} teams.".format(number_of_gyms, len(teams)))

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True
            ),
        }

        everyone_role = ctx.author.roles[0]

        channels_created: Dict[str, int] = {}

        for pokemon_type in pokemon_types:
            role_name = pokemon_type + " Player"
            role = discord.utils.get(
                ctx.guild.roles, name=role_name
            ) or await ctx.guild.create_role(name=role_name)

        last_position = 0
        for c in ctx.guild.categories:
            if c.name not in self.gyms.keys():
                last_position = c.position

        for index, gym in enumerate(self.gyms.values()):
            if index >= number_of_gyms:
                break

            log.info("Checking for {}".format(gym["name"]))

            role = discord.utils.get(
                ctx.guild.roles, name=gym["badge"]
            ) or await ctx.guild.create_role(name=gym["badge"])

            category = discord.utils.get(ctx.guild.categories, name=gym["name"])
            if not category:
                category = await ctx.guild.create_category(
                    gym["name"],
                    position=last_position + 1 + index,
                    overwrites=overwrites,
                )
            else:
                if len(category.channels) > 0:
                    await embed_helper(
                        ctx,
                        (
                            f"There are channels under category {category.mention}. "
                            "This might cause messed up permissions."
                            "Are you sure you want to continue without deleting those channels?"
                        ),
                    )
                    pred = MessagePredicate.yes_or_no(ctx)
                    await self.bot.wait_for("message", check=pred)
                    if pred.result is False:
                        await embed_helper(
                            ctx,
                            "Use {}deletebadgechannels commands to delete all channels.".format(
                                ctx.prefix
                            ),
                        )
                        raise ExistingChannels
            channels_created[category.name] = list()
            await category.set_permissions(
                everyone_role, read_messages=False, send_messages=False
            )
            await category.set_permissions(
                ctx.guild.me, read_messages=True, send_messages=True,
            )

            if first_elimination == 0:
                number_of_channels_required = int(
                    len(teams) / (2 ** (gym["level"] + 1))
                )
            else:
                if index == 0:
                    number_of_channels_required = first_elimination
                else:
                    number_of_channels_required = int(len(teams) / (2 ** gym["level"]))
            log.info(
                "Creating {} channels under {}".format(
                    number_of_channels_required, category.name
                )
            )
            for _ in range(number_of_channels_required):
                new_channel = await category.create_text_channel(
                    name=gym["badge"].replace(" ", "-"), overwrites=overwrites
                )
                if new_channel:
                    channels_created[category.name].append(new_channel.id)
        await self.config.guild(ctx.guild).gym_channels.set(channels_created)
        await ctx.tick()
