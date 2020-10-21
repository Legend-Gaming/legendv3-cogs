import datetime
import datetime as dt
import io
import itertools
import json
import logging
from logging import debug
import os
import random
import re
import string
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Union

import aiohttp
import clashroyale
import discord
from discord.ext.commands import Converter
from discord.ext.commands.errors import BadArgument
import psutil
import yaml
from PIL import Image, ImageDraw, ImageFont
from pympler import asizeof
from redbot.core.utils import AsyncIter
from redbot.core import Config, checks, commands
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils.chat_formatting import pagify
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.predicates import MessagePredicate

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
        tag = tag.strip('#').upper().replace('O', '0')
        allowed = '0289PYLQGRJCUV'
        if len(tag[3:]) < 3:
            raise discord.CommandError(f"Member {tag} not found.\n{tag} is not a valid tag.")
        for c in tag[3:]:
            if c not in allowed:
                raise discord.CommandError(f"Member {tag} not found.\n{tag} is not a valid tag.")
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

        self.card_info = dict(
            # card width and height
            card_w = 604,
            card_h = 726,
            # default minimum offset for cards
            card_x = 30,
            card_y  = 30,
            font_size = 160,
            font_size_large = 170,
            # height of battle logo
            battle_logo_displacement = 500,
            # height of score image
            score_displacement = 250,
            # offset of player2's deck
            column2_offset = 2500,
            # offset for line1: elixir and line2: minimum elixir for 4 card cycle
            txt_x_avg_elixir = 400,
            txt_x_4card_elixir = 400,
            line_height = 250,
            card_thumb_scale = 0.5,
        )

        # Used for Pillow blocking code
        self.threadex = ThreadPoolExecutor(max_workers=4)

        self.emoji = BotEmoji(self.bot)

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

    @commands.command(name="battlelog")
    async def command_battlelog(self, ctx: commands.Context, member: Union[discord.Member, PlayerTag, None], battle: int = 1, account: int = 1):
        log.debug("start of command battlelog: " + str(psutil.virtual_memory()[4]/1024/1024))
        if type(member) is type(None) or member is None:
            member = ctx.author
        if isinstance(member, discord.member.Member) or isinstance(member, discord.Member):
            player_tag = self.tags.getTag(member.id, account)
        elif isinstance(member, str):
            player_tag = member

        if player_tag is None:
            await ctx.send("Account {} is not saved. Use {} crtools accounts to see your accounts.".format(account, ctx.prefix))
            return
        log.debug("after getting tag: " + str(psutil.virtual_memory()[4]/1024/1024))
        try:
            battles = await self.get_battle_logs(ctx, player_tag)
        except clashroyale.NotFoundError:
            await ctx.send("Player tag is invalid.")
            return
        except clashroyale.RequestError:
            await ctx.send(
                "Error: cannot reach Clash Royale Servers. "
                "Please try again later."
            )
            return
        log.debug("after getting battle log from clash: " + str(psutil.virtual_memory()[4]/1024/1024))
        required_battle = battles[battle - 1]
        msg = await self.send_battlelog_embed(
            ctx,
            required_battle,
        )

    async def send_battlelog_embed(
        self, ctx, battle
    ):
        """Upload deck image to destination."""
        deck1, deck2 = self.get_1v1_battle_cards(battle)
        score = self.get_battle_score(battle)
        player1 = {
            'name': battle.team[0].name,
            'tag': battle.team[0].tag,
            'deck': deck1,
            'score': battle.team[0].crowns,
            'clan': dict(getattr(battle.team[0], 'clan', {"tag": "","name": "None",}))
        }
        player2 = {
            'name': battle.opponent[0].name,
            'tag': battle.opponent[0].tag,
            'deck': deck2,
            'score': battle.opponent[0].crowns,
            'clan': dict(getattr(battle.opponent[0], 'clan', {"tag": "","name": "None",}))
        }
        battle_type = self.get_battle_type(battle)
        log.debug("before getting image: "+ str(psutil.virtual_memory()[4]/1024/1024))
        if battle_type == "CW_Duel":
            deck_image = await self.bot.loop.run_in_executor(
                None, self.get_duel_deck_image, player1, player2, score
            )
        elif battle_type == "2v2":
            deck_image = await self.bot.loop.run_in_executor(
                None, self.get_2v2_deck_image, battle, score
            )
        else:
            deck_image = await self.bot.loop.run_in_executor(
                None, self.get_1v1_deck_image, player1, player2, score
            )
        log.debug("after getting image: " + str(psutil.virtual_memory()[4]/1024/1024))
        # construct a filename using first three letters of each card
        filename = "deck-{}.png".format("-".join([card[:3] for card in (deck1 + deck2)]))
        message = None
        battle_score = f"`{battle['team'][0]['crowns']} - {battle['opponent'][0]['crowns']}`"
        battle_type = self.get_battle_type(battle).replace("-", " ")
        battle_result = self.get_battle_result(battle)
        # description = """
            # {}
            # {} | `{}`          {} | `{}`
            # {} `{}` {} `{}` [Copy deck]({})          {} `{}` {} `{}` [Copy deck]({})
        # """.format(
            # battle_result,
            # player1['name'], player1['tag'], player2['name'], player2['tag'],
            # self.emoji.name('crtrophy'), battle.team[0].startingTrophies, self.emoji.name('elixir'), self.get_deck_elxir(deck1), self.decklink_url(deck1),
            # self.emoji.name('crtrophy'), battle.opponent[0].startingTrophies, self.emoji.name('elixir'), self.get_deck_elxir(deck2), self.decklink_url(deck2),
        # )
        description = battle_result
        embed = discord.Embed(
            title=f"{battle['team'][0]['name']} ({battle['team'][0]['tag']})",
            description=description,
            url=f"https://royaleapi.com/player/{battle['team'][0]['tag'].strip('#')}",
            timestamp=dt.datetime.utcnow(),
        )
        embed.add_field(
            name="{} | `{}`".format(
                player1['name'],
                player1['tag'],
            ),
            value="{} `{}` {} `{}` [Copy deck]({})".format(
                self.emoji.name('crtrophy'),
                getattr(battle.team[0], "startingTrophies", 0),
                self.emoji.name('elixir'),
                self.get_deck_elxir(deck1),
                self.decklink_url(deck1),
            ),
            inline=True
        )
        embed.add_field(
            name="{} | `{}`".format(
                player2['name'],
                player2['tag'],
            ),
            value="{} `{}` {} `{}` [Copy deck]({})".format(
                self.emoji.name('crtrophy'),
                getattr(battle.opponent[0], "startingTrophies", 0),
                self.emoji.name('elixir'),
                self.get_deck_elxir(deck2),
                self.decklink_url(deck2),
            ),
            inline=True
        )

        with io.BytesIO() as f:
            deck_image.save(f, "PNG")
            f.seek(0)
            embed.set_image(url="attachment://{}".format(filename))
            embed.set_footer(text=credits, icon_url=credits_icon)
            message = await ctx.send(
                file=discord.File(f, filename=filename), embed=embed
            )
        deck_image.close()
        return message

    async def get_battle_logs(self, ctx:commands.Context, tag, number:int = None):
        all_battles = await self.clash.get_player_battles(tag)
        return all_battles if number is None else all_battles[number]

    def get_battle_type(self, battle):
        if battle.type in ['boatBattle', 'riverRacePvP']:
            return "CW_Battle"
        elif battle.type in ['riverRaceDuel']:
            return "CW_Duel"
        elif len(list(battle.team)) == 2:
            return "2v2"
        else:
            return "1v1"

    def get_1v1_battle_cards(self, battle):
        team_cards = [(self.card_id_to_key(str(c.id))) for c in battle.team[0].cards]
        opponent_cards = [(self.card_id_to_key(str(c.id))) for c in battle.opponent[0].cards]
        return team_cards, opponent_cards

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

    def get_1v1_deck_image(self, player1, player2, battle_score, battle_type="1v1", **kwargs):
        """Construct the deck with Pillow and return image."""
        # card width and height
        card_w = kwargs.get('card_w', 604)
        card_h = kwargs.get('card_h', 726)
        # default minimum offset for cards
        card_x = kwargs.get('card_x', 30)
        card_y = kwargs.get('card_y', 30)
        font_size = kwargs.get('font_size', 160)
        font_size_large = kwargs.get('font_size_large', 170)
        # height of battle logo
        battle_logo_displacement = kwargs.get('battle_logo_displacement', 500)
        # height of score image
        score_displacement = kwargs.get('score_displacement', 250)
        # offset of player2's deck
        column2_offset = kwargs.get('column2_offset', 2500)
        # offset for line1: elixir and line2: minimum elixir for 4 card cycle
        txt_x_avg_elixir = kwargs.get('txt_x_avg_elixir', 400)
        txt_y_line1 = score_displacement + battle_logo_displacement + card_y + card_h * 2
        txt_x_4card_elixir = kwargs.get('txt_x_4card_elixir', 400)
        line_height = kwargs.get('line_height', 250)
        txt_y_line2 = txt_y_line1 + line_height

        deck1 = player1['deck']
        deck2 = player2['deck']

        font_file_regular = str(
            bundled_data_path(self) / "fonts" / "OpenSans-Regular.ttf"
        )
        font_file_bold = str(bundled_data_path(self) / "fonts/OpenSans-Bold.ttf")

        size = (column2_offset * 2, score_displacement + battle_logo_displacement + card_y + card_h * 2 + line_height * 2,)
        image = Image.new("RGBA", size)

        bg_image = Image.open(str(bundled_data_path(self) / "img" / "double_size_no_logo.png"))
        bg_image = bg_image.resize(size)
        image.paste(bg_image)
        bg_image.close()

        # battle logo is centred and y offset is height of score image
        battle_logo_map = {
            "1v1": "1v1_battle.png",
            "CW_Battle": "cw_battle_1v1.png",
            "CW_Duel": "cw_battle_duel.png",
            "2v2": "2v2_battle.png",
        }
        battle_logo_file = str(bundled_data_path(self) / "img" / battle_logo_map.get(battle_type, "1v1_battle.png"))
        battle_logo = Image.open(battle_logo_file)
        resize_factor = battle_logo_displacement / battle_logo.height
        battle_logo_size = (int(battle_logo.width * resize_factor), int(battle_logo.height * resize_factor), )
        if update_files and battle_logo_size != battle_logo.size:
            battle_logo = battle_logo.resize(battle_logo_size)
            battle_logo.save(battle_logo_file)
        box = (int(column2_offset - battle_logo.width/2), score_displacement,)
        image.paste(battle_logo, box)
        battle_logo.close()

        # score image is centred and y offset is 0. height of image is
        score_image_file = str(bundled_data_path(self) / "img" / "score" / "{}.png".format(battle_score))
        score_image = Image.open(score_image_file)
        resize_factor = score_displacement / score_image.height
        score_image_size = (int(score_image.width * resize_factor), int(score_image.height * resize_factor),)
        if update_files and score_image_size != score_image.size:
            score_image = score_image.resize(score_image_size)
            score_image.save(score_image_file)
        box = (int(column2_offset - score_image.width/2), 0,)
        image.paste(score_image, box)

        for i, card in enumerate(deck1):
            card_image_file = str(
                bundled_data_path(self) / "img" / "cards" / "{}.png".format(card)
            )
            card_image = Image.open(card_image_file)
            card_image_size = (card_w, card_h,)
            if update_files and card_image_size != card_image.size:
                card_image = card_image.resize(card_image_size)
                card_image.save(card_image_file)
            box = (
                card_x + card_w * (i%4),
                card_y + score_displacement + battle_logo_displacement + card_h * int(i/4),
                card_x + card_w * ((i%4) + 1),
                card_y + score_displacement + battle_logo_displacement + card_h * int((i/4) + 1),
            )
            image.paste(card_image, box, card_image)
            card_image.close()

        # draw vertical line at center
        font_regular = ImageFont.truetype(font_file_regular, size=font_size)
        font_large = ImageFont.truetype(font_file_regular, size=font_size_large)
        font_bold = ImageFont.truetype(font_file_bold, size=font_size)
        font_large_bold = ImageFont.truetype(font_file_bold, size=font_size_large)
        d = ImageDraw.Draw(image)
        d.line((column2_offset, battle_logo_displacement + score_displacement, column2_offset, image.size[1],), fill=0xFF0000, width=5)

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
            (card_x, card_y),
            line1,
            font = font_large_bold,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )
        if player1.get('clan', None):
            d.text(
                (card_x, card_y + 20 + font_large_bold.getsize(line1)[1]),
                player1['clan']['name'],
                font = font_regular,
                fill=(0xFF, 0xFF, 0xFF, 255),
            )
        elixir_image = Image.open(str(bundled_data_path(self) / "img" / "elixir.png"))
        resize_factor = line_height / elixir_image.height
        elixir_image = elixir_image.resize((int(elixir_image.width * resize_factor), int(elixir_image.height * resize_factor),))
        box = (card_x, txt_y_line1,)
        image.paste(elixir_image, box)

        cycle_elixir_image = Image.open(str(bundled_data_path(self) / "img" / "elixir-cycle.png"))
        resize_factor = line_height / cycle_elixir_image.height
        cycle_elixir_image = cycle_elixir_image.resize((int(cycle_elixir_image.width * resize_factor), int(cycle_elixir_image.height * resize_factor),))
        box = (card_x, txt_y_line2,)
        image.paste(cycle_elixir_image, box)

        for i, card in enumerate(deck2):
            card_image_file = str(
                bundled_data_path(self) / "img" / "cards" / "{}.png".format(card)
            )
            card_image = Image.open(card_image_file)
            card_image = card_image.resize((card_w, card_h,))
            box = (
                column2_offset + card_x + card_w * (i%4),
                card_y + score_displacement + battle_logo_displacement + card_h * int(i/4),
                column2_offset + card_x + card_w * ((i%4) + 1),
                card_y + score_displacement + battle_logo_displacement + card_h * int((i/4) + 1),
            )
            image.paste(card_image, box, card_image)
            card_image.close()

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
        line2 = player2['clan']['name']
        maximum_line_length = column2_offset - (battle_logo_size[0] / 2)
        if font_large_bold.getsize(line1)[0] > maximum_line_length:
            line1 = f"{player2['name']}"
        while font_large_bold.getsize(line1)[0] > maximum_line_length:
            line1 = line1[:-2]
        d.text(
            (image.width - font_large_bold.getsize(line1)[0] - 20, card_y),
            line1,
            font = font_large_bold,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )
        if player1.get('clan', None):
            d.text(
                (image.width - font_large_bold.getsize(line2)[0] - 20, card_y + 20 + font_large_bold.getsize(line1)[1]),
                line2,
                font = font_regular,
                fill=(0xFF, 0xFF, 0xFF, 255),
            )
        box = (column2_offset + card_x, txt_y_line1,)
        image.paste(elixir_image, box)

        box = (column2_offset + card_x, txt_y_line2,)
        image.paste(cycle_elixir_image, box)

        log.debug("before calling thumbnail: "
            + str(psutil.virtual_memory()[4]/1024/1024)
            + str(asizeof.asizeof(image))
        )

        if kwargs.get("thumbnail", True):
            # scale down and return
            scale = kwargs.get('card_thumb_scale', 0.5)
            scaled_size = tuple([x * scale for x in image.size])
            image.thumbnail(scaled_size)
            log.debug("after calling thumbnail: "
                + str(psutil.virtual_memory()[4]/1024/1024)
                + str(asizeof.asizeof(image))
            )
        return image

    def get_duel_deck_image(self, player1, player2, battle_score):
        """Construct the deck with Pillow and return image."""
        # card width and height
        card_w = 604
        card_h = 726
        # default minimum offset for cards
        card_x = 30
        card_y = 30
        # offset of player2's deck
        column2_offset = 2500
        # for 2 lines of text; average elixir and 4-cycle elixir
        txt_x_avg_elixir = 400
        txt_y_line1 = card_y + card_h * 2
        txt_x_4card_elixir = txt_x_avg_elixir
        line_height = 250
        txt_y_line2 = txt_y_line1 + line_height
        # deck1 and deck2 might contain 2 or 3 decks
        deck1 = player1['deck']
        deck2 = player2['deck']
        if len(deck1) != len(deck2):
            raise IncompleteDeck
        # separate into groups of 8 cards each group representing a single deck
        player1_decks = self.grouper(8, deck1)
        player2_decks = self.grouper(8, deck2)

        number_of_decks = len(player1_decks)

        # Get image using first deck of each player
        player1['deck'] = player1_decks[0]
        player2['deck'] = player2_decks[0]
        deck_image = self.get_1v1_deck_image(player1, player2, battle_score, thumbnail=False)

        # Each deck after first one adds 2 rows of cards so height increases by card_height*2
        # Each deck after first one adds 2 lines; one for average elixir and one for minimum cycle
        # So each deck increases height by (card_height*2 + line_height*2)
        # New_deck_image is the image to be appended to deck_image
        size = deck_image.size
        single_deck_image_height = (card_h * 2 + line_height * 2)
        single_deck_image_size = (size[0], single_deck_image_height,)
        new_deck_image_height = (single_deck_image_height * (number_of_decks - 1))
        new_deck_image_size = (size[0], new_deck_image_height,)

        # Total size of image afer adding all decks
        new_size = (size[0], size[1] + new_deck_image_height, )

        image = Image.new("RGBA", new_size)
        image.paste(deck_image, (0, 0))
        deck_image.close()
        # For each deck after first deck
        for j in range(1, len(player1_decks)):
            for i, card in enumerate(player1_decks[j]):
                card_image_file = str(
                    bundled_data_path(self) / "img" / "cards" / "{}.png".format(card)
                )
                card_image = Image.open(card_image_file)
                card_image_size = (card_w, card_h,)
                if update_files and card_image_size != card_image.size:
                    card_image = card_image.resize(card_image_size)
                    card_image.save(card_image_file)
                box = (
                    card_x + card_w * (i%4),
                    size[1] + single_deck_image_height * (j-1) + card_h * int((i/4)),
                    card_x + card_w * ((i%4) + 1),
                    size[1] + single_deck_image_height * (j-1) + card_h * int((i/4) + 1),
                )
                image.paste(card_image, box, card_image)
                card_image.close()

        for j in range(1, len(player2_decks)):
            for i, card in enumerate(player2_decks[j]):
                card_image_file = str(
                    bundled_data_path(self) / "img" / "cards" / "{}.png".format(card)
                )
                card_image = Image.open(card_image_file)
                card_image_size = (card_w, card_h,)
                if update_files and card_image_size != card_image.size:
                    card_image = card_image.resize(card_image_size)
                    card_image.save(card_image_file)
                box = (
                    column2_offset + card_x + card_w * (i%4),
                    size[1] + single_deck_image_height * (j-1) + card_h * int((i/4)),
                    column2_offset + card_x + card_w * ((i%4) + 1),
                    size[1] + single_deck_image_height * (j-1) + card_h * int((i/4) + 1),
                )
                image.paste(card_image, box, card_image)
                card_image.close()

        # scale down and return
        scale = 0.5
        scaled_size = tuple([x * scale for x in image.size])
        image.thumbnail(scaled_size)
        log.debug("end of get_duel_deck_image: " + str(psutil.virtual_memory()[4]/1024/1024))
        return image

    def get_2v2_deck_image(self, battle, battle_score):
        log.debug("start of get_2v2_deck_image: " + str(psutil.virtual_memory()[4]/1024/1024))
        team_decks, opponent_decks = self.get_2v2_battle_cards(battle)
        player1 = {
            'name': battle.team[0].name,
            'tag': battle.team[0].tag,
            'deck': team_decks[0],
            'score': battle.team[0].crowns,
            'clan': dict(getattr(battle.team[0], 'clan', {"tag": "","name": "None",}))
        }
        player2 = {
            'name': battle.opponent[0].name,
            'tag': battle.opponent[0].tag,
            'deck': opponent_decks[0],
            'score': battle.opponent[0].crowns,
            'clan': dict(getattr(battle.opponent[0], 'clan', {"tag": "","name": "None",}))
        }
        deck_image1 = self.get_1v1_deck_image(player1, player2, battle_score)
        return deck_image1
        player1 = {
            'name': battle.team[1].name,
            'tag': battle.team[1].tag,
            'deck': team_decks[1],
            'score': battle.team[1].crowns,
            'clan': dict(getattr(battle.team[1], 'clan', {"tag": "","name": "None",}))
        }
        player2 = {
            'name': battle.opponent[1].name,
            'tag': battle.opponent[1].tag,
            'deck': opponent_decks[1],
            'score': battle.opponent[1].crowns,
            'clan': dict(getattr(battle.opponent[1], 'clan', {"tag": "","name": "None",}))
        }
        deck_image2 = self.get_1v1_deck_image(player1, player2, battle_score)

        # Total size of image afer adding all decks
        new_size = (deck_image1.size[0] + deck_image2.size[0], deck_image1.size[1] + deck_image2.size[1],)

        image = Image.new("RGBA", new_size)
        image.paste(deck_image1, (0, 0))
        deck_image1.close()
        image.paste(deck_image2, (0, deck_image1.height,))
        deck_image2.close()
        log.debug("after merging images: "
            + str(psutil.virtual_memory()[4]/1024/1024)
            + + str(asizeof.asizeof(image))
        )

        scale = 0.5
        scaled_size = tuple([int(x * scale) for x in image.size])
        image.thumbnail(scaled_size)
        log.debug("end of get_2v2_deck_image: "
            + str(psutil.virtual_memory()[4]/1024/1024)
            + str(asizeof.asizeof(image))
        )
        return image
