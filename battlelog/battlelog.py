import asyncio
import contextlib
import datetime
import datetime as dt
import functools
import io
import itertools
import json
import logging
import os
import random
import re
import string
from concurrent.futures import ThreadPoolExecutor
from logging import debug
from typing import Dict, List, Optional, Union, Literal

import aiohttp
import clashroyale
import discord
import psutil
import yaml
from discord import team
from discord.ext.commands import Converter
from discord.ext.commands.errors import BadArgument
from PIL import Image, ImageDraw, ImageFont
from pympler import asizeof
from redbot.core import Config, checks, commands
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import pagify
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu, start_adding_reactions
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

credits = "Bot by Legend Gaming"
credits_icon = "https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1"
log = logging.getLogger("red.cogs.battlelog")

update_files = True
DEBUG = True

CARDS_JSON_PATH: str = ""

log.setLevel(logging.DEBUG)


class NoToken(Exception):
    pass


class IncompleteDeck(Exception):
    pass


class PlayerTag(discord.ext.commands.Converter):
    async def convert(self, ctx, tag: str):
        tag = tag.strip("#").upper().replace("O", "0")
        allowed = "0289PYLQGRJCUV"
        if len(tag[3:]) < 3:
            raise discord.CommandError(
                f"Member {tag} not found.\n{tag} is not a valid tag."
            )
        for c in tag[3:]:
            if c not in allowed:
                raise discord.CommandError(
                    f"Member {tag} not found.\n{tag} is not a valid tag."
                )
        return tag


class BotEmoji:
    """Emojis available in bot."""

    def __init__(self, bot):
        self.bot = bot

    def name(self, name: str):
        """Emoji by name."""
        for emoji in self.bot.emojis:
            if emoji.name == name:
                return "<:{}:{}>".format(emoji.name, emoji.id)
        return ""


async def simple_embed(
    ctx: commands.Context,
    message: str,
    success: Optional[bool] = None,
    mentions: Dict[str, bool] = dict({"users": True, "roles": True}),
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


class BattleLog(commands.Cog):
    """Clash Royale Deck Builder."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        CARDS_JSON_PATH = str(bundled_data_path(self) / "cards.json")
        with open(CARDS_JSON_PATH) as file:
            self.cards = dict(json.load(file))["card_data"]

        crtools_cog = self.bot.get_cog("ClashRoyaleTools")
        self.tags = getattr(crtools_cog, "tags", None)

        self.config = Config.get_conf(
            self, identifier=58877888797878787, force_registration=True
        )
        default_global = {
            "merged_duel_image": False,
            "paging": True,
            "dumpster": None,
        }
        self.config.register_global(**default_global)
        self.card_info = dict(
            # card width and height
            card_w=604,
            card_h=726,
            # default minimum offset for cards
            card_x=30,
            card_y=30,
            font_size=160,
            font_size_large=170,
            # height of battle logo
            battle_logo_displacement=500,
            # height of score image
            score_displacement=250,
            # offset for line1: elixir and line2: minimum elixir for 4 card cycle
            txt_x_avg_elixir=400,
            txt_x_4card_elixir=400,
            line_height=250,
            card_thumb_scale=0.5,
        )
        # offset of player2's deck
        # first deck has 2 card_x displacements and 4 cards
        self.card_info["column2_offset"] = (
            self.card_info["card_x"] * 2 + self.card_info["card_w"] * 4 + 20
        )

        # Used for Pillow blocking code
        self.threadex = ThreadPoolExecutor(max_workers=4)

        self.emoji = BotEmoji(self.bot)
        self.single_duel_image = False
        self.token_task = self.bot.loop.create_task(self.crtoken())
        self.clash = None

    async def crtoken(self):
        """Connect to clashroyale API"""
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token.get("token") is None:
            log.error(
                "CR Token is not SET. "
                "Use [p]set api clashroyale token,YOUR_TOKEN to set it"
            )
            raise NoToken
        self.clash = clashroyale.official_api.Client(
            token=token["token"], is_async=True, url="https://proxy.royaleapi.dev/v1"
        )

    def cog_unload(self):
        if self.token_task:
            self.token_task.cancel()
        if self.clash:
            self.bot.loop.create_task(self.clash.close())

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    @commands.command(name="battlelog")
    @checks.is_owner()
    async def command_battlelog(
        self,
        ctx: commands.Context,
        member: Union[discord.Member, PlayerTag, None],
        battle: int = 1,
        account: int = 1,
    ):
        """Show clashroyale battlelog"""
        log.debug(
            "start of command battlelog: "
            + str(psutil.virtual_memory()[4] / 1024 / 1024)
        )
        if type(member) is type(None) or member is None:
            member = ctx.author
        if isinstance(member, discord.member.Member) or isinstance(
            member, discord.Member
        ):
            player_tag = self.tags.getTag(member.id, account)
        elif isinstance(member, str):
            player_tag = member

        if player_tag is None:
            await ctx.send(
                "Account {} is not saved. Use {} crtools accounts to see your accounts.".format(
                    account, ctx.prefix
                )
            )
            return
        log.debug("after getting tag: " + str(psutil.virtual_memory()[4] / 1024 / 1024))
        try:
            battles = await self.get_battle_logs(ctx, player_tag)
        except clashroyale.NotFoundError:
            await ctx.send("Player tag is invalid.")
            return
        except clashroyale.RequestError:
            await ctx.send(
                "Error: cannot reach Clash Royale Servers. " "Please try again later."
            )
            return
        log.debug(
            "after getting battle log from clash: "
            + str(psutil.virtual_memory()[4] / 1024 / 1024)
        )
        required_battle = battles[battle - 1]
        msg = await self.send_battlelog_embed(
            ctx, required_battle, requestor=player_tag
        )

    @commands.group(name="battlelogset")
    @checks.is_owner()
    async def battlelogset(self, ctx):
        """Configure battlelog"""
        pass

    @battlelogset.command(name="merge_duel")
    @checks.is_owner()
    async def battlelogset_merge_duel(self, ctx):
        """Toggle whether to merge all duel images as one or keep them separate"""
        await self.config.merged_duel_image.set(
            not await self.config.merged_duel_image()
        )
        await ctx.send(
            "Merging duel image: " + str(await self.config.merged_duel_image())
        )

    @battlelogset.command(name="paging")
    @checks.is_owner()
    async def battlelogset_paging(self, ctx):
        """Toggle whether to use reaction menu for logs"""
        current_value = await self.config.paging()
        if not current_value and await self.config.dumpster() is None:
            return await ctx.send("Cannot enable paging without setting dumpster.")
        await self.config.paging.set(not current_value)
        await ctx.send("Using menu for images: " + str(await self.config.paging()))

    @battlelogset.command(name="dumpster")
    @checks.is_owner()
    async def battlelogset_dumpster(self, ctx, channel: discord.TextChannel = None):
        """Set channel to dump images for paging"""
        if channel is not None:
            await self.config.dumpster.set(channel.id)
            await ctx.send(f"Using {channel.mention} as dumpster.")
        else:
            await self.config.dumpster.set(None)
            await self.config.paging.set(False)

    async def send_battlelog_embed(self, ctx: commands.Context, battle, requestor):
        """Upload deck image to destination."""
        battle_type = self.get_battle_type(battle)
        log.debug(
            "before calling send_<type>_battlelog: "
            + str(psutil.virtual_memory()[4] / 1024 / 1024)
        )
        if battle_type == "CW_Duel":
            return await self.send_duel_battlelog(ctx, battle)
        elif battle_type == "2v2":
            return await self.send_2v2_battlelog(ctx, battle, requestor)
        else:
            return await self.send_1v1_battlelog(ctx, battle)

    async def get_battle_logs(self, ctx: commands.Context, tag, number: int = None):
        all_battles = await self.clash.get_player_battles(tag)
        return all_battles if number is None else all_battles[number]

    def get_filename(self, deck1, deck2):
        return "deck-{}.png".format("-".join([card[:3] for card in (deck1 + deck2)]))

    def get_battle_type(self, battle):
        if battle.type in ["boatBattle", "riverRacePvP"]:
            return "CW_Battle"
        elif battle.type in ["riverRaceDuel"]:
            return "CW_Duel"
        elif len(list(battle.team)) == 2:
            return "2v2"
        else:
            return "1v1"

    def get_1v1_battle_cards(self, battle):
        team_cards = [(self.card_id_to_key(str(c.id))) for c in battle.team[0].cards]
        opponent_cards = [
            (self.card_id_to_key(str(c.id))) for c in battle.opponent[0].cards
        ]
        return team_cards, opponent_cards

    def get_duel_battle_cards(self, battle):
        deck1, deck2 = self.get_1v1_battle_cards(battle)
        player1_decks = self.grouper(8, deck1)
        player2_decks = self.grouper(8, deck2)
        return (
            player1_decks,
            player2_decks,
        )

    def get_2v2_battle_cards(self, battle):
        team_cards = (
            [(self.card_id_to_key(str(c.id))) for c in battle.team[0].cards],
            [(self.card_id_to_key(str(c.id))) for c in battle.team[1].cards],
        )
        opponent_cards = (
            [(self.card_id_to_key(str(c.id))) for c in battle.opponent[0].cards],
            [(self.card_id_to_key(str(c.id))) for c in battle.opponent[0].cards],
        )
        return team_cards, opponent_cards

    def get_battle_score(self, battle):
        team_score = battle.team[0].crowns
        opponent_score = battle.opponent[0].crowns
        score = "{}-{}".format(team_score, opponent_score)
        return score

    def get_battle_result(self, battle):
        battle_type = self.get_battle_type(battle)
        score = self.get_battle_score(battle)
        if battle.team[0].crowns > battle.opponent[0].crowns:
            battle_result = f"VICTORY | {self.emoji.name('blueCrown')} {score} {self.emoji.name('redCrown')} {battle_type}"
        elif battle.team[0].crowns < battle.opponent[0].crowns:
            battle_result = f"DEFEAT | {self.emoji.name('blueCrown')} {score} {self.emoji.name('redCrown')} | {battle_type}"
        else:
            battle_result = f"DRAW | {self.emoji.name('blueCrown')} {score} {self.emoji.name('redCrown')} | {battle_type}"
        return battle_result

    def card_id_to_key(self, card_id) -> Optional[str]:
        """Decklink id to card."""
        for card in self.cards:
            if card_id == str(card["id"]):
                return card["key"]
        log.error("Cannot find card " + card_id)
        return None

    def card_key_to_id(self, key) -> Optional[str]:
        """Card key to decklink id."""
        for card in self.cards:
            if key == card["key"]:
                return str(card["id"])
        return None

    def grouper(self, n, iterable, fillvalue=None):
        """Group iterable into groups of n"""
        args = [iter(iterable)] * n
        return list(itertools.zip_longest(*args, fillvalue=fillvalue))

    def get_deck_elxir(self, card_keys):
        """Get average for a deck"""
        total_elixir = 0
        card_count = 0
        for card in self.cards:
            if card["key"] in card_keys:
                total_elixir += card["elixir"]
                if card["elixir"]:
                    card_count += 1

        average_elixir = "{:.3f}".format(total_elixir / card_count)

        return average_elixir

    def get_cycle_elixir(self, card_keys):
        """Get minimum elixir required to cycle 4 cards"""
        card_elixirs = {}
        cycle_elixir = 0
        for card in self.cards:
            if card["key"] in card_keys:
                card_elixirs[card["key"]] = card["elixir"]
        required = sorted(card_elixirs.items(), key=lambda item: item[1])[:4]
        for card, elixir in required:
            cycle_elixir += elixir
        return cycle_elixir

    def decklink_url(self, deck_cards):
        """Get url to copy deck"""
        ids = []
        for card in deck_cards:
            id = self.card_key_to_id(card)
            if id is not None:
                ids.append(self.card_key_to_id(card))
        url = "https://link.clashroyale.com/deck/en?deck=" + ";".join(ids)
        return url

    def get_1v1_deck_image(
        self, player1, player2, battle_score, battle_type="1v1", **kwargs
    ):
        """Construct the deck with Pillow and return image."""
        # TODO: Get everything from self.card_info instead of kwargs
        # card width and height
        card_w = kwargs.get("card_w", self.card_info.get("card_w"))
        card_h = kwargs.get("card_h", self.card_info.get("card_h"))
        # default minimum offset for cards
        card_x = kwargs.get("card_x", self.card_info.get("card_x"))
        card_y = kwargs.get("card_y", self.card_info.get("card_y"))
        font_size = kwargs.get("font_size", self.card_info.get("font_size"))
        font_size_large = kwargs.get(
            "font_size_large", self.card_info.get("font_size_large")
        )
        # height of battle logo
        battle_logo_displacement = kwargs.get(
            "battle_logo_displacement", self.card_info.get("battle_logo_displacement")
        )
        # height of score image
        score_displacement = kwargs.get(
            "score_displacement", self.card_info.get("score_displacement")
        )
        # offset of player2's deck
        column2_offset = kwargs.get(
            "column2_offset", self.card_info.get("column2_offset")
        )
        # offset for line1: elixir and line2: minimum elixir for 4 card cycle
        txt_x_avg_elixir = kwargs.get(
            "txt_x_avg_elixir", self.card_info.get("txt_x_avg_elixir")
        )
        txt_y_line1 = (
            score_displacement + battle_logo_displacement + card_y + card_h * 2
        )
        txt_x_4card_elixir = kwargs.get(
            "txt_x_4card_elixir", self.card_info.get("txt_x_4card_elixir")
        )
        line_height = kwargs.get("line_height", self.card_info.get("line_height"))
        txt_y_line2 = txt_y_line1 + line_height

        deck1 = player1["deck"]
        deck2 = player2["deck"]

        font_file_regular = str(
            bundled_data_path(self) / "fonts" / "OpenSans-Regular.ttf"
        )
        font_file_bold = str(bundled_data_path(self) / "fonts/OpenSans-Bold.ttf")

        size = (
            column2_offset * 2,
            int(
                score_displacement
                + battle_logo_displacement
                + card_y
                + card_h * 2
                + line_height * 2
            ),
        )
        print(size)
        image = Image.new("RGBA", size)

        bg_image_file = str(bundled_data_path(self) / "img" / "double_size_no_logo.png")
        bg_image = Image.open(bg_image_file)
        bg_image = bg_image.resize(size)
        if update_files and size != bg_image.size:
            bg_image = bg_image.resize(size)
            bg_image.save(bg_image_file)
        image.paste(bg_image)
        bg_image.close()

        # battle logo is centred and y offset is height of score image
        battle_logo_map = {
            "1v1": "1v1_battle.png",
            "CW_Battle": "cw_battle_1v1.png",
            "CW_Duel": "cw_battle_duel.png",
            "2v2": "2v2_battle.png",
        }
        battle_logo_file = str(
            bundled_data_path(self)
            / "img"
            / battle_logo_map.get(battle_type, "1v1_battle.png")
        )
        battle_logo = Image.open(battle_logo_file)
        resize_factor = battle_logo_displacement / battle_logo.height
        battle_logo_size = (
            int(battle_logo.width * resize_factor),
            int(battle_logo.height * resize_factor),
        )
        if update_files and battle_logo_size != battle_logo.size:
            battle_logo = battle_logo.resize(battle_logo_size)
            battle_logo.save(battle_logo_file)
        box = (
            int(column2_offset - battle_logo.width / 2),
            score_displacement,
        )
        image.paste(battle_logo, box)
        battle_logo.close()

        # score image is centred and y offset is 0. height of image is
        score_image_file = str(
            bundled_data_path(self) / "img" / "score" / "{}.png".format(battle_score)
        )
        score_image = Image.open(score_image_file)
        resize_factor = score_displacement / score_image.height
        score_image_size = (
            int(score_image.width * resize_factor),
            int(score_image.height * resize_factor),
        )
        if update_files and score_image_size != score_image.size:
            score_image = score_image.resize(score_image_size)
            score_image.save(score_image_file)
        box = (
            int(column2_offset - score_image.width / 2),
            0,
        )
        image.paste(score_image, box)

        deck1_image = self.get_single_deck_image(deck1)
        deck1_image_size = deck1_image.size
        deck1_box = (
            0,
            score_displacement + battle_logo_displacement,
            0 + deck1_image_size[0],
            score_displacement + battle_logo_displacement + deck1_image_size[1],
        )
        image.paste(deck1_image, deck1_box, deck1_image)
        deck1_image.close()

        # draw vertical line at center
        font_regular = ImageFont.truetype(font_file_regular, size=font_size)
        font_large = ImageFont.truetype(font_file_regular, size=font_size_large)
        font_bold = ImageFont.truetype(font_file_bold, size=font_size)
        font_large_bold = ImageFont.truetype(font_file_bold, size=font_size_large)
        d = ImageDraw.Draw(image)
        d.line(
            (
                column2_offset,
                battle_logo_displacement + score_displacement,
                column2_offset,
                image.size[1],
            ),
            fill=0xFF0000,
            width=5,
        )

        average_elixir = self.get_deck_elxir(deck1)
        min_cycle_elixir = self.get_cycle_elixir(deck1)
        d.text(
            (txt_x_avg_elixir, txt_y_line1),
            str(average_elixir),
            font=font_bold,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )
        d.text(
            (txt_x_4card_elixir, txt_y_line2,),
            str(min_cycle_elixir),
            font=font_bold,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )
        line1 = f"{player1['name']} ({player1['tag']})"
        maximum_line_length = column2_offset - (battle_logo_size[0] / 2)
        if font_large_bold.getsize(line1)[0] > maximum_line_length:
            line1 = f"{player1['name']}"
        while font_large_bold.getsize(line1)[0] > maximum_line_length:
            line1 = line1[:-2]
        d.text(
            (card_x, card_y), line1, font=font_large_bold, fill=(0xFF, 0xFF, 0xFF, 255),
        )
        if player1.get("clan", None):
            d.text(
                (card_x, card_y + 20 + font_large_bold.getsize(line1)[1]),
                player1["clan"]["name"],
                font=font_regular,
                fill=(0xFF, 0xFF, 0xFF, 255),
            )
        elixir_image = Image.open(str(bundled_data_path(self) / "img" / "elixir.png"))
        resize_factor = line_height / elixir_image.height
        elixir_image = elixir_image.resize(
            (
                int(elixir_image.width * resize_factor),
                int(elixir_image.height * resize_factor),
            )
        )
        box = (
            card_x,
            txt_y_line1,
        )
        image.paste(elixir_image, box)

        cycle_elixir_image = Image.open(
            str(bundled_data_path(self) / "img" / "elixir-cycle.png")
        )
        resize_factor = line_height / cycle_elixir_image.height
        cycle_elixir_image = cycle_elixir_image.resize(
            (
                int(cycle_elixir_image.width * resize_factor),
                int(cycle_elixir_image.height * resize_factor),
            )
        )
        box = (
            card_x,
            txt_y_line2,
        )
        image.paste(cycle_elixir_image, box)

        deck2_image = self.get_single_deck_image(deck2)
        deck2_box = (
            column2_offset,
            score_displacement + battle_logo_displacement,
            column2_offset + deck2_image.size[0],
            score_displacement + battle_logo_displacement + deck2_image.size[1],
        )
        image.paste(deck2_image, deck2_box, deck2_image)
        deck2_image.close()

        average_elixir = self.get_deck_elxir(deck2)
        min_cycle_elixir = self.get_cycle_elixir(deck2)
        d.text(
            (column2_offset + txt_x_avg_elixir, txt_y_line1),
            str(average_elixir),
            font=font_bold,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )
        d.text(
            (column2_offset + txt_x_4card_elixir, txt_y_line2,),
            str(min_cycle_elixir),
            font=font_bold,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )
        line1 = f"{player2['name']} ({player2['tag']})"
        line2 = player2["clan"]["name"]
        maximum_line_length = column2_offset - (battle_logo_size[0] / 2)
        if font_large_bold.getsize(line1)[0] > maximum_line_length:
            line1 = f"{player2['name']}"
        while font_large_bold.getsize(line1)[0] > maximum_line_length:
            line1 = line1[:-2]
        d.text(
            (image.width - font_large_bold.getsize(line1)[0] - 20, card_y),
            line1,
            font=font_large_bold,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )
        if player1.get("clan", None):
            d.text(
                (
                    image.width - font_large_bold.getsize(line2)[0] - 20,
                    card_y + 20 + font_large_bold.getsize(line1)[1],
                ),
                line2,
                font=font_regular,
                fill=(0xFF, 0xFF, 0xFF, 255),
            )
        box = (
            column2_offset + card_x,
            txt_y_line1,
        )
        image.paste(elixir_image, box)

        box = (
            column2_offset + card_x,
            txt_y_line2,
        )
        image.paste(cycle_elixir_image, box)

        log.debug(
            "before calling thumbnail: "
            + str(psutil.virtual_memory()[4] / 1024 / 1024)
            + str(asizeof.asizeof(image))
        )

        if kwargs.get("thumbnail", True):
            # scale down and return
            scale = kwargs.get(
                "card_thumb_scale", self.card_info.get("card_thumb_scale")
            )
            scaled_size = tuple([x * scale for x in image.size])
            image.thumbnail(scaled_size)
            log.debug(
                "after calling thumbnail: "
                + str(psutil.virtual_memory()[4] / 1024 / 1024)
                + str(asizeof.asizeof(image))
            )
        return image

    def get_single_deck_image(self, deck1, single_line: bool = False):
        card_x = self.card_info["card_x"]
        card_y = self.card_info["card_y"]
        card_w = self.card_info["card_w"]
        card_h = self.card_info["card_h"]
        image_width = int(
            card_w * len(deck1) if single_line else card_w * len(deck1) / 2
        )
        image_height = int(card_h if single_line else card_h * 2)
        size = (
            image_width,
            image_height,
        )
        image = Image.new("RGBA", size)
        for i, card in enumerate(deck1):
            card_image_file = str(
                bundled_data_path(self) / "img" / "cards" / "{}.png".format(card)
            )
            card_image = Image.open(card_image_file)
            card_image_size = (
                card_w,
                card_h,
            )
            if update_files and card_image_size != card_image.size:
                card_image = card_image.resize(card_image_size)
                card_image.save(card_image_file)
            top_left_corner = (
                card_x + card_w * (i) if single_line else card_w * (i % 4),
                card_y + card_h if single_line else card_h * int(i / 4),
            )
            box = (
                top_left_corner[0],
                top_left_corner[1],
                top_left_corner[0] + card_w,
                top_left_corner[1] + card_h,
            )
            image.paste(card_image, box, card_image)
            card_image.close()
        image.thumbnail(size)
        return image

    def get_duel_deck_image(self, player1, player2, battle_score):
        """Construct the deck with Pillow and return image."""
        # card width and height
        card_w = self.card_info.get("card_w")
        card_h = self.card_info.get("card_h")
        # default minimum offset for cards
        card_x = self.card_info.get("card_x")
        card_y = self.card_info.get("card_y")
        # offset of player2's deck
        column2_offset = self.card_info.get("column2_offset")

        # deck1 and deck2 might contain 2 or 3 decks
        deck1 = player1["deck"]
        deck2 = player2["deck"]
        if len(deck1) != len(deck2):
            raise IncompleteDeck

        number_of_decks = len(deck1)

        # Get image using first deck of each player
        player1["deck"] = deck1[0]
        player2["deck"] = deck2[0]
        first_deck_image = self.get_1v1_deck_image(
            player1, player2, battle_score, thumbnail=False, **self.card_info
        )

        # Each deck after first one adds 2 rows of cards so height increases by card_height*2
        # So each deck increases height by (card_height*2)
        # New_deck_image is the image to be appended to deck_image
        first_deck_image_size = first_deck_image.size
        extra_deck_image_height = card_h * 2 + card_y
        new_deck_image_height = extra_deck_image_height * (
            number_of_decks - 1
        )  # First deck is already accounted for

        # Total size of image afer adding all decks
        full_image_size = (
            first_deck_image_size[0],
            first_deck_image_size[1] + new_deck_image_height,
        )

        image = Image.new("RGBA", full_image_size)
        image.paste(first_deck_image, (0, 0))
        first_deck_image.close()

        for j in range(1, len(deck1)):
            player1["deck"] = deck1[j]
            player2["deck"] = deck2[j]
            deck1_image = self.get_single_deck_image(deck1[j])
            image.paste(
                deck1_image,
                (0, first_deck_image_size[1] + extra_deck_image_height * (j - 1)),
            )
            deck1_image.close()
            deck2_image = self.get_single_deck_image(deck2[j])
            image.paste(
                deck2_image,
                (
                    column2_offset,
                    first_deck_image_size[1] + extra_deck_image_height * (j - 1),
                ),
            )
            deck2_image.close()

        # scale down and return
        scale = 0.5
        scaled_size = tuple([x * scale for x in image.size])
        image.thumbnail(scaled_size)
        log.debug(
            "end of get_duel_deck_image: "
            + str(psutil.virtual_memory()[4] / 1024 / 1024)
        )
        return image

    def get_duel_deck_images(self, player1, player2, battle_score):
        """Construct the deck with Pillow and return image."""
        deck1, deck2 = player1["deck"], player2["deck"]
        if len(deck1) != len(deck2):
            raise IncompleteDeck
        images = []
        for j in range(0, len(deck1)):
            log.debug(
                f"start of get_duel_deck_image {j}: "
                + str(psutil.virtual_memory()[4] / 1024 / 1024)
            )
            player1["deck"] = deck1[j]
            player2["deck"] = deck2[j]
            deck_image = self.get_1v1_deck_image(
                player1, player2, battle_score, thumbnail=False, **self.card_info
            )
            # scale down and store
            scale = 0.5
            scaled_size = tuple([x * scale for x in deck_image.size])
            deck_image.thumbnail(scaled_size)
            log.debug(
                f"end of get_duel_deck_image {j}: "
                + str(psutil.virtual_memory()[4] / 1024 / 1024)
            )
            yield deck_image

    def get_2v2_deck_images(self, battle, battle_score):
        """Construct the deck with Pillow and return image."""
        log.debug(
            f"start of get_2v2_deck_image: "
            + str(psutil.virtual_memory()[4] / 1024 / 1024)
        )
        team_cards, opponent_cards = self.get_2v2_battle_cards(battle)
        if len(team_cards) != len(opponent_cards):
            raise IncompleteDeck
        images = []
        for j in range(0, len(team_cards)):
            log.debug(
                f"preparing image {j+1} of {len(team_cards)}: "
                + str(psutil.virtual_memory()[4] / 1024 / 1024)
            )
            player1 = {
                "name": battle.team[j].name,
                "tag": battle.team[j].tag,
                "deck": team_cards[j],
                "score": battle.team[0].crowns,
                "clan": dict(
                    getattr(battle.team[j], "clan", {"tag": "", "name": "None",})
                ),
                "startingTrophies": getattr(battle.team[j], "startingTrophies", 0),
            }
            player2 = {
                "name": battle.opponent[j].name,
                "tag": battle.opponent[j].tag,
                "deck": opponent_cards[j],
                "score": battle.opponent[j].crowns,
                "clan": dict(
                    getattr(battle.opponent[j], "clan", {"tag": "", "name": "None",})
                ),
                "startingTrophies": getattr(battle.opponent[j], "startingTrophies", 0),
            }
            deck_image = self.get_1v1_deck_image(
                player1, player2, battle_score, thumbnail=False, **self.card_info
            )
            # scale down and store
            scale = 0.5
            scaled_size = tuple([x * scale for x in deck_image.size])
            deck_image.thumbnail(scaled_size)
            log.debug(
                f"end of get_duel_deck_image {j+1}: "
                + str(psutil.virtual_memory()[4] / 1024 / 1024)
            )
            yield deck_image

    def get_single_battle_embed(self, player1, player2, battle_result):
        # construct a filename using first three letters of each card
        deck1 = player1["deck"]
        deck2 = player2["deck"]
        filename = self.get_filename(deck1, deck2)
        message = None
        description = battle_result
        embed = discord.Embed(
            title=f"{player1['name']} ({player1['tag']})",
            description=description,
            url=f"https://royaleapi.com/player/{player1['tag'].strip('#')}",
            timestamp=dt.datetime.utcnow(),
        )
        embed.add_field(
            name="{} | `{}`".format(player1["name"], player1["tag"],),
            value="{} `{}` {} `{}` [Copy deck]({})".format(
                self.emoji.name("crtrophy"),
                player1.get("startingTrophies", 0),
                self.emoji.name("elixir"),
                self.get_deck_elxir(deck1),
                self.decklink_url(deck1),
            ),
            inline=True,
        )
        embed.add_field(
            name="{} | `{}`".format(player2["name"], player2["tag"],),
            value="{} `{}` {} `{}` [Copy deck]({})".format(
                self.emoji.name("crtrophy"),
                player2.get("startingTrophies", 0),
                self.emoji.name("elixir"),
                self.get_deck_elxir(deck2),
                self.decklink_url(deck2),
            ),
            inline=True,
        )
        embed.set_image(url="attachment://{}".format(filename))
        embed.set_footer(text=credits, icon_url=credits_icon)
        return embed

    def get_2v2_battle_embed(self, battle, battle_result, requestor):
        # construct a filename using first three letters of each card
        team_cards, opponent_cards = self.get_2v2_battle_cards(battle)
        filename = self.get_filename(team_cards[0], opponent_cards[0])
        message = None
        description = battle_result
        team_player = None
        requestor_index = 0
        team_player_index = 1
        if battle.team[0].tag.strip("#") == requestor.strip("#"):
            requestor = battle.team[0]
            team_player = battle.team[1]
            requestor_index = 0
            team_player_index = 1
        elif battle.team[1].tag.strip("#") == requestor.strip("#"):
            requestor = battle.team[1]
            team_player = battle.team[0]
            requestor_index = 1
            team_player_index = 0
        else:
            raise BadArgument("Cannot find requestor in battle.team. ")
        embed = discord.Embed(
            title=f"{requestor.name} ({requestor.tag})",
            description=description,
            url=f"https://royaleapi.com/player/{requestor.tag.strip('#')}",
            timestamp=dt.datetime.utcnow(),
        )
        embed.add_field(
            name="{} | `{}`".format(requestor.name, requestor.tag,),
            value="{} `{}` {} `{}` [Copy deck]({})".format(
                self.emoji.name("crtrophy"),
                getattr(requestor, "startingTrophies", 0),
                self.emoji.name("elixir"),
                self.get_deck_elxir(team_cards[requestor_index]),
                self.decklink_url(team_cards[requestor_index]),
            ),
            inline=True,
        )
        embed.add_field(
            name="{} | `{}`".format(battle.opponent[0].name, battle.opponent[0].tag,),
            value="{} `{}` {} `{}` [Copy deck]({})".format(
                self.emoji.name("crtrophy"),
                getattr(battle.opponent[0], "startingTrophies", 0),
                self.emoji.name("elixir"),
                self.get_deck_elxir(opponent_cards[0]),
                self.decklink_url(opponent_cards[0]),
            ),
            inline=True,
        )
        embed.add_field(
            name="{} | `{}`".format(team_player.name, team_player.tag,),
            value="{} `{}` {} `{}` [Copy deck]({})".format(
                self.emoji.name("crtrophy"),
                getattr(team_player, "startingTrophies", 0),
                self.emoji.name("elixir"),
                self.get_deck_elxir(team_cards[team_player_index]),
                self.decklink_url(team_cards[team_player_index]),
            ),
            inline=False,
        )
        embed.add_field(
            name="{} | `{}`".format(battle.opponent[1].name, battle.opponent[1].tag,),
            value="{} `{}` {} `{}` [Copy deck]({})".format(
                self.emoji.name("crtrophy"),
                getattr(battle.opponent[1], "startingTrophies", 0),
                self.emoji.name("elixir"),
                self.get_deck_elxir(opponent_cards[1]),
                self.decklink_url(opponent_cards[1]),
            ),
            inline=True,
        )
        embed.set_footer(text=credits, icon_url=credits_icon)
        return embed

    async def send_1v1_battlelog(self, ctx, battle):
        deck1, deck2 = self.get_1v1_battle_cards(battle)
        score = self.get_battle_score(battle)
        player1 = {
            "name": battle.team[0].name,
            "tag": battle.team[0].tag,
            "deck": deck1,
            "score": battle.team[0].crowns,
            "clan": dict(getattr(battle.team[0], "clan", {"tag": "", "name": "None",})),
            "startingTrophies": getattr(battle.team[0], "startingTrophies", 0),
        }
        player2 = {
            "name": battle.opponent[0].name,
            "tag": battle.opponent[0].tag,
            "deck": deck2,
            "score": battle.opponent[0].crowns,
            "clan": dict(
                getattr(battle.opponent[0], "clan", {"tag": "", "name": "None",})
            ),
            "startingTrophies": getattr(battle.opponent[0], "startingTrophies", 0),
        }
        log.debug(
            "before getting image: " + str(psutil.virtual_memory()[4] / 1024 / 1024)
        )

        deck_image = await self.bot.loop.run_in_executor(
            None, self.get_1v1_deck_image, player1, player2, score,
        )
        log.debug(
            "after getting image: " + str(psutil.virtual_memory()[4] / 1024 / 1024)
        )
        # construct a filename using first three letters of each card
        filename = self.get_filename(deck1, deck2)
        embed = self.get_single_battle_embed(
            player1, player2, self.get_battle_result(battle)
        )

        with io.BytesIO() as f:
            deck_image.save(f, "PNG")
            f.seek(0)
            message = await ctx.send(
                file=discord.File(f, filename=filename), embed=embed
            )
        deck_image.close()
        return message

    async def send_2v2_battlelog(self, ctx: commands.Context, battle, requestor):
        """Upload deck image to destination."""
        team_cards, opponent_cards = self.get_2v2_battle_cards(battle)
        score = self.get_battle_score(battle)
        team_players = [
            {
                "name": player.name,
                "tag": player.tag,
                "deck": team_cards,
                "score": player.crowns,
                "clan": dict(getattr(player, "clan", {"tag": "", "name": "None",})),
                "startingTrophies": getattr(player, "startingTrophies", 0),
            }
            for player in battle.team
        ]
        opponent_players = [
            {
                "name": player.name,
                "tag": player.tag,
                "deck": team_cards,
                "score": player.crowns,
                "clan": dict(getattr(player, "clan", {"tag": "", "name": "None",})),
                "startingTrophies": getattr(player, "startingTrophies", 0),
            }
            for player in battle.opponent
        ]

        log.debug(
            "before getting 2v2 image: " + str(psutil.virtual_memory()[4] / 1024 / 1024)
        )
        message = None
        paging = await self.config.paging()

        deck1, deck2 = team_cards, opponent_cards
        urls = []
        pages = []
        for j, deck_image in enumerate(
            await self.bot.loop.run_in_executor(
                None, self.get_2v2_deck_images, battle, score
            )
        ):
            log.debug(
                f"after getting 2v2 image {j}: "
                + str(psutil.virtual_memory()[4] / 1024 / 1024)
            )
            # construct a filename using first three letters of each card
            filename = self.get_filename(deck1[j], deck2[j])
            team_players[j]["deck"] = team_cards[j]
            opponent_players[j]["deck"] = opponent_cards[j]
            embed = self.get_2v2_battle_embed(
                battle, self.get_battle_result(battle), requestor
            )
            f = io.BytesIO()
            deck_image.save(f, "PNG")
            f.seek(0)
            file = discord.File(f, filename=filename)
            embed.set_image(url="attachment://{}".format(filename))
            pages.append(embed)
            if not paging:
                channel_to_send = ctx.channel
            else:
                channel_to_send = self.bot.get_channel(await self.config.dumpster())
            if not channel_to_send:
                await self.config.paging.set(False)
                paging = False
                channel_to_send = ctx.channel
            message = await channel_to_send.send(file=file, embed=embed)
            if paging:
                url = None
                if message.embeds:
                    url = str(message.embeds[0].image.url)
                elif message.attachments:
                    url = message.attachements[0].url
                else:
                    url = "https://imgur.com/pU0V5oX"
                embed.set_image(url=url)
                pages.append(embed)
                urls.append(url)
            f.close()
            deck_image.close()
            log.debug(
                f"after closing 2v2 image {j}: "
                + str(psutil.virtual_memory()[4] / 1024 / 1024)
            )
        if paging:
            await menu(ctx, pages, DEFAULT_CONTROLS)
        return message

    async def send_duel_battlelog(self, ctx: commands.Context, battle):
        """Upload deck image to destination."""
        deck1, deck2 = self.get_duel_battle_cards(battle)
        score = self.get_battle_score(battle)
        player1 = {
            "name": battle.team[0].name,
            "tag": battle.team[0].tag,
            "deck": deck1,
            "score": battle.team[0].crowns,
            "clan": dict(getattr(battle.team[0], "clan", {"tag": "", "name": "None",})),
            "startingTrophies": getattr(battle.team[0], "startingTrophies", 0),
        }
        player2 = {
            "name": battle.opponent[0].name,
            "tag": battle.opponent[0].tag,
            "deck": deck2,
            "score": battle.opponent[0].crowns,
            "clan": dict(
                getattr(battle.opponent[0], "clan", {"tag": "", "name": "None",})
            ),
            "startingTrophies": getattr(battle.opponent[0], "startingTrophies", 0),
        }
        log.debug(
            "before getting duel image: "
            + str(psutil.virtual_memory()[4] / 1024 / 1024)
        )
        message = None
        merged = await self.config.merged_duel_image()
        paging = await self.config.paging()
        if merged:
            deck_image = await self.bot.loop.run_in_executor(
                None, self.get_duel_deck_image, player1, player2, score
            )
            log.debug(
                "after getting duel image: "
                + str(psutil.virtual_memory()[4] / 1024 / 1024)
            )
            # construct a filename using first three letters of each card
            filename = self.get_filename(deck1[0], deck2[0])
            embed = self.get_single_battle_embed(
                player1, player2, self.get_battle_result(battle)
            )
            embed.set_image(url="attachment://{}".format(filename))
            with io.BytesIO() as f:
                deck_image.save(f, "PNG")
                f.seek(0)
                message = await ctx.send(
                    file=discord.File(f, filename=filename), embed=embed
                )
            deck_image.close()
            log.debug(
                "after closing duel image: "
                + str(psutil.virtual_memory()[4] / 1024 / 1024)
            )
            return message
        else:
            urls = []
            pages = []
            for j, deck_image in enumerate(
                await self.bot.loop.run_in_executor(
                    None, self.get_duel_deck_images, player1, player2, score
                )
            ):
                log.debug(
                    f"after getting duel image {j}: "
                    + str(psutil.virtual_memory()[4] / 1024 / 1024)
                )
                # construct a filename using first three letters of each card
                player1["deck"] = deck1[j]
                player2["deck"] = deck2[j]
                filename = self.get_filename(deck1[j], deck2[j])
                embed = self.get_single_battle_embed(
                    player1, player2, self.get_battle_result(battle)
                )
                f = io.BytesIO()
                deck_image.save(f, "PNG")
                f.seek(0)
                file = discord.File(f, filename=filename)
                pages.append(embed)
                if not paging:
                    channel_to_send = ctx.channel
                else:
                    channel_to_send = self.bot.get_channel(await self.config.dumpster())
                if not channel_to_send:
                    await self.config.paging.set(False)
                    paging = False
                    channel_to_send = ctx.channel
                message = await channel_to_send.send(file=file, embed=embed)
                if paging:
                    urls.append(str(message.embeds[0].image.url))
                f.close()
                deck_image.close()
                log.debug(
                    f"after closing duel image {j}: "
                    + str(psutil.virtual_memory()[4] / 1024 / 1024)
                )
            if paging:
                await embed_menu(ctx, pages, DEFAULT_CONTROLS, urls=urls)
            return message


"""Modified from Redbot(https://github.com/Cog-Creators/Red-DiscordBot) to set image instead of modifying embed"""
# TODO: use controls to control pages instead of copying redbot.core.utils.menus
async def embed_menu(
    ctx: commands.Context,
    pages: List[discord.Embed],
    controls: dict,
    message: discord.Message = None,
    page: int = 0,
    timeout: float = 30.0,
    urls=None,
):
    controls = {
        "\N{LEFTWARDS BLACK ARROW}\N{VARIATION SELECTOR-16}": prev_page1,
        "\N{CROSS MARK}": close_menu1,
        "\N{BLACK RIGHTWARDS ARROW}\N{VARIATION SELECTOR-16}": next_page1,
    }
    if urls is None:
        urls = []
    if not isinstance(pages[0], discord.Embed):
        raise RuntimeError
    current_page = pages[page]

    if not message:
        if page >= len(urls):
            log.error(f"Got {len(urls)} urls but tried accessing {page}.")
        else:
            current_page.set_image(url=urls[page])
        message = await ctx.send(embed=current_page)
        start_adding_reactions(message, controls.keys())
    else:
        try:
            if page >= len(urls):
                log.error(f"Got {len(urls)} urls but tried accessing {page}.")
            else:
                current_page.set_image(url=urls[page])
            await message.edit(embed=current_page)
        except discord.NotFound:
            return

    try:
        react, user = await ctx.bot.wait_for(
            "reaction_add",
            check=ReactionPredicate.with_emojis(
                tuple(controls.keys()), message, ctx.author
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        try:
            if message.channel.permissions_for(ctx.me).manage_messages:
                await message.clear_reactions()
            else:
                raise RuntimeError
        except (discord.Forbidden, RuntimeError):  # cannot remove all reactions
            for key in controls.keys():
                try:
                    await message.remove_reaction(key, ctx.bot.user)
                except discord.Forbidden:
                    return
                except discord.HTTPException:
                    pass
        except discord.NotFound:
            return
    else:
        return await controls[react.emoji](
            ctx, pages, controls, message, page, timeout, react.emoji, urls=urls
        )


async def next_page1(
    ctx: commands.Context,
    pages: list,
    controls: dict,
    message: discord.Message,
    page: int,
    timeout: float,
    emoji: str,
    urls: List[str],
):
    perms = message.channel.permissions_for(ctx.me)
    if perms.manage_messages:  # Can manage messages, so remove react
        with contextlib.suppress(discord.NotFound):
            await message.remove_reaction(emoji, ctx.author)
    if page == len(pages) - 1:
        page = 0  # Loop around to the first item
    else:
        page = page + 1
    return await embed_menu(
        ctx, pages, controls, message=message, page=page, timeout=timeout, urls=urls
    )


async def prev_page1(
    ctx: commands.Context,
    pages: list,
    controls: dict,
    message: discord.Message,
    page: int,
    timeout: float,
    emoji: str,
    urls: List[str],
):
    perms = message.channel.permissions_for(ctx.me)
    if perms.manage_messages:  # Can manage messages, so remove react
        with contextlib.suppress(discord.NotFound):
            await message.remove_reaction(emoji, ctx.author)
    if page == 0:
        page = len(pages) - 1  # Loop around to the last item
    else:
        page = page - 1
    return await embed_menu(
        ctx, pages, controls, message=message, page=page, timeout=timeout, urls=urls
    )


async def close_menu1(
    ctx: commands.Context,
    pages: list,
    controls: dict,
    message: discord.Message,
    page: int,
    timeout: float,
    emoji: str,
    urls: List[str],
):
    with contextlib.suppress(discord.NotFound):
        await message.delete()
