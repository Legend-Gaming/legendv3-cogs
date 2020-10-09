# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2017 SML

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
# force update skeleton dragons 2
import datetime
import datetime as dt
import io
import json
import logging
import os
import random
import re
import string
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import aiohttp
import discord
import yaml
from PIL import Image, ImageDraw, ImageFont
from redbot.core import Config, checks, commands
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils.chat_formatting import pagify
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.predicates import MessagePredicate

credits = "Bot by Legend Gaming"
credits_icon = "https://cdn.discordapp.com/emojis/709796075581735012.gif?v=1"
log = logging.getLogger("red.cogs.deck")

SETTINGS_PATH: str = ""
AKA_PATH: str = ""
CARDS_JSON_PATH: str = ""
max_deck_per_user: int = 10

PAGINATION_TIMEOUT = 120
HELP_URL = "https://github.com/smlbiobot/SML-Cogs/wiki/Deck#usage"
CARDS_JSON_URL = "https://royaleapi.github.io/cr-api-data/json/cards.json"


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


class BotEmoji:
    """Emojis available in bot."""

    def __init__(self, bot):
        self.bot = bot

    def name(self, name: str):
        """Emoji by name."""
        for emoji in self.bot.get_all_emojis():
            if emoji.name == name:
                return "<:{}:{}>".format(emoji.name, emoji.id)
        return ""


class Deck(commands.Cog):
    """Clash Royale Deck Builder."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = Config.get_conf(
            self, identifier=2390872398545, force_registration=True
        )
        default_global = {
            "image_server": dict(guild_id=None, channel_id=None,),
        }
        default_guild = {
            "decklink": "embed",
            "auto_deck_link": False,
            "image_server": dict(channel_id=None,),
        }
        default_member = {"decks": {}}
        self.settings.register_global(**default_global)
        self.settings.register_guild(**default_guild)
        self.settings.register_member(**default_member)

        CARDS_JSON_PATH = str(bundled_data_path(self) / "cards.json")
        with open(CARDS_JSON_PATH) as file:
            self.cards = dict(json.load(file))["card_data"]

        AKA_PATH = str(bundled_data_path(self) / "cards_aka.yaml")
        # init card data
        self.cards_abbrev = {}

        with open(AKA_PATH) as f:
            aka = yaml.safe_load(f)

        for k, v in aka.items():
            for value in v:
                self.cards_abbrev[value] = k
            self.cards_abbrev[k.replace("-", "")] = k

        self.card_w = 302
        self.card_h = 363
        self.card_ratio = self.card_w / self.card_h
        self.card_thumb_scale = 0.5
        self.card_thumb_w = int(self.card_w * self.card_thumb_scale)
        self.card_thumb_h = int(self.card_h * self.card_thumb_scale)

        # deck validation hack
        self.deck_is_valid = False

        # pagination tracking
        self.track_pagination = None

        self._cards_json = None

        # Used for Pillow blocking code
        self.threadex = ThreadPoolExecutor(max_workers=2)

    @property
    def valid_card_keys(self) -> List[str]:
        """Valid card keys."""
        return [card["key"] for card in self.cards]

    async def cards_json(self) -> List[dict]:
        """Load self._cards_json"""
        if self._cards_json is None:
            with open(CARDS_JSON_PATH) as f:
                self._cards_json = dict(json.load(f))["card_data"]
        return self._cards_json

    @commands.group()
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def deckset(self, ctx: commands.Context):
        """Settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @deckset.command(name="decklink")
    @checks.admin_or_permissions()
    async def deckset_decklink(self, ctx: commands.Context, use: str = "embed"):
        """How to display decklinks.

        Possible values are:
        - embed (default): use embeds with link
        - link: use URL with text
        - none
        """
        if use is None:
            await ctx.send_help()
            return
        if use is not None and use.lower() not in ["embed", "link"]:
            await ctx.send(
                "Value of use is not valid. Possible values are embed, link and none."
            )
            return
        await self.settings.guild(ctx.guild).decklink.set(use.lower())
        await simple_embed(ctx, "Settings saved.")

    @deckset.command(name="imageserver")
    @checks.is_owner()
    async def deckset_imageserver(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None
    ):
        """Set where to send images"""
        if channel is None:
            channel = ctx.channel
        image_server = dict(channel_id=channel.id)
        await self.settings.guild(ctx.guild).image_server.set(image_server)
        await simple_embed(
            ctx,
            "Images will be uploaded to:\n"
            "Server: {} ({})\n"
            "Channel: {} ({})".format(
                ctx.guild.name, ctx.guild.id, channel.name, channel.id
            ),
        )

    @deckset.command(name="autodecklink")
    @checks.admin_or_permissions()
    async def deckset_autodecklink(self, ctx: commands.Context):
        """Toggle auto transform on server."""
        guild = ctx.guild
        auto_deck_link = (await self.settings.guild(guild).all()).get(
            "auto_deck_link", False
        )
        auto_deck_link = not auto_deck_link
        await self.settings.guild(guild).auto_deck_link.set(auto_deck_link)
        await simple_embed(ctx, "Auto deck link: {}".format(auto_deck_link))

    async def decklink_settings(self, guild: discord.Guild):
        """embed, link, none. Default: embed"""
        default = "embed"
        decklink = await self.settings.guild(guild).decklink()
        return decklink or default

    async def deck_get_helper(
        self,
        ctx: commands.Context,
        card1=None,
        card2=None,
        card3=None,
        card4=None,
        card5=None,
        card6=None,
        card7=None,
        card8=None,
        deck_name: Optional[str] = None,
        author: Optional[discord.Member] = None,
    ):
        """Abstract command to run deck_get for other modules."""
        params = {}
        for i in range(1, 9):
            key = "card" + str(i)
            params[key] = locals()[key]
        params["deck_name"] = deck_name
        params["author"] = author
        await ctx.invoke(self.bot.get_command("deck get"), **params)

    async def card_id_to_key(self, card_id) -> Optional[str]:
        """Decklink id to card."""
        for card in self.cards:
            if card_id == str(card["id"]):
                return card["key"]
        return None

    async def card_key_to_id(self, key) -> Optional[str]:
        """Card key to decklink id."""
        for card in self.cards:
            if key == card["key"]:
                return str(card["id"])
        return None

    async def decklink_to_cards(self, url) -> Optional[List[str]]:
        """Convert decklink to cards."""
        card_keys = None
        # search for Clash Royale decks
        m_crlink = re.search(
            r"(http|ftp|https)://link.clashroyale.com/deck/..\?deck=[\d\;]+", url
        )

        # search for royaleapi deck stats link
        m_rapilink = re.match(
            r"(https|http)://royaleapi.com/decks/stats/([a-z,-]+)/?", url
        )
        m_rapilink_section = re.match(
            r"(https|http)://royaleapi.com/decks/stats/([a-z,-]+)/.+", url
        )

        if m_crlink:
            url = m_crlink.group()
            decklinks = re.findall(r"2\d{7}", url)
            card_keys = []
            for decklink in decklinks:
                card_key = await self.card_id_to_key(decklink)
                if card_key is not None:
                    card_keys.append(card_key)
        elif m_rapilink and not m_rapilink_section:
            s = m_rapilink.group(2)
            card_keys = s.split(",")
        return card_keys

    @commands.group(name="deck", autohelp=False)
    async def deck(self, ctx: commands.Context):
        """Clash Royale deck builder.

        Example usage:
        !deck add 3m mm ig is fs pump horde eb "3M EBarbs"

        Card list
        !deck cards

        Full help
        !deck help
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @deck.command(name="get")
    async def deck_get(
        self,
        ctx: commands.Context,
        card1=None,
        card2=None,
        card3=None,
        card4=None,
        card5=None,
        card6=None,
        card7=None,
        card8=None,
        deck_name: str = None,
        author: discord.Member = None,
    ):
        """Display a deck with cards.

        Enter 8 cards followed by a name.

        Example:
        !deck get barrel gg is it knight princess rocket log "Log Bait"

        For the full list of acceptable card names, type !deck cards
        """
        if deck_name is None:
            deck_name = "Deck"
        if author is None:
            author = ctx.author

        member_deck = [card1, card2, card3, card4, card5, card6, card7, card8]
        if not all(member_deck):
            await ctx.send("Please enter 8 cards.")
            await ctx.send_help()
            return
        elif len(set(member_deck)) < len(member_deck):
            await ctx.send("Please enter 8 unique cards.")
            return
        else:
            await self.deck_upload(ctx, member_deck, deck_name, author)

    @deck.command(name="getlink", aliases=["gl"])
    async def deck_getlink(self, ctx: commands.Context, *, url):
        """Get a deck using the decklink."""
        card_keys = await self.decklink_to_cards(url)
        if card_keys is None:
            await simple_embed(ctx, "Cannot find a URL.")
            return
        if len(card_keys) != 8:
            await simple_embed(ctx, "Please enter the full url.")
            return
        params = {}
        for i in range(1, 9):
            params["card" + str(i)] = card_keys[i - 1]
        await ctx.invoke(self.bot.get_command("deck get"), **params)
        try:
            await ctx.message.delete()
        except Exception:
            pass

    @deck.command(name="add")
    async def deck_add(
        self,
        ctx: commands.Context,
        card1=None,
        card2=None,
        card3=None,
        card4=None,
        card5=None,
        card6=None,
        card7=None,
        card8=None,
        deck_name=None,
    ):
        """Add a deck to a personal decklist.

        Example:
        !deck add 3M knight log pump miner ig is skeletons "3M Cycle"

        For the full list of acceptable card names, type !deck cards
        """
        author = ctx.message.author

        # convert arguments to deck list and name
        member_deck = [card1, card2, card3, card4, card5, card6, card7, card8]
        member_deck = self.normalize_deck_data(member_deck)

        if not all(member_deck):
            await simple_embed(ctx, "Please enter 8 cards.")
            await ctx.send_help()
        elif len(set(member_deck)) < len(member_deck):
            await simple_embed(ctx, "Please enter 8 unique cards.")
        else:
            await self.deck_upload(ctx, member_deck, deck_name, author)
            if self.deck_is_valid:
                async with self.settings.member(author).decks() as member_decks:
                    if deck_name is None:
                        deck_name = (
                            "Deck "
                            + str(len(member_decks))
                            + str(random.choice(range(1000)))
                        )
                    member_decks[str(datetime.datetime.utcnow())] = {
                        "Deck": member_deck,
                        "DeckName": deck_name,
                    }
                    timestamp = member_decks.keys()
                    timestamp = sorted(timestamp)

                    while len(member_decks) > max_deck_per_user:
                        t = timestamp.pop(0)
                        member_decks.pop(t, None)
                    await simple_embed(ctx, "Deck added.")

    @deck.command(name="addlink", aliases=["al", "import", "i"])
    async def deck_addlink(self, ctx: commands.Context, *, url):
        """Add a deck using the decklink."""
        card_keys = await self.decklink_to_cards(url)
        if card_keys is None:
            await simple_embed(ctx, "Cannot find a URL.")
            return
        if len(card_keys) != 8:
            await simple_embed(ctx, "Please enter the full url.")
            return
        params = {}
        for i in range(1, 9):
            params["card" + str(i)] = card_keys[i - 1]
        await ctx.invoke(self.bot.get_command("deck add"), **params)
        try:
            await ctx.message.delete()
        except Exception:
            pass

    @deck.command(name="list")
    async def deck_list(self, ctx: commands.Context, member: discord.Member = None):
        """List the decks of a user."""
        member_is_author = False
        if member is None:
            member = ctx.author
            member_is_author = True
        decks = await self.settings.member(member).decks()
        deck_id = 1
        for time_stamp, deck in decks.items():
            url = await self.decklink_url(deck["Deck"], war=False)
            await self.upload_deck_image(
                ctx,
                deck["Deck"],
                deck["DeckName"],
                member,
                description="**{}**. {}".format(deck_id, deck["DeckName"]),
                title="Copy deck",
                url=url,
            )
            # await self.decklink(ctx, deck["Deck"])
            deck_id += 1

        if not len(decks):
            if member_is_author:
                await simple_embed(
                    ctx,
                    "You don’t have any decks stored.\n"
                    "Type `!deck add` to add some.",
                )
            else:
                await simple_embed(
                    ctx, "{} hasn’t added any decks yet.".format(member.display_name)
                )

    @deck.command(name="longlist")
    async def deck_longlist(self, ctx: commands.Context, member: discord.Member = None):
        """List the decks of a user."""
        member_is_author = False
        if not member:
            member = ctx.author
            member_is_author = True

        decks = await self.settings.member(member).decks()
        if not len(decks):
            if member_is_author:
                await simple_embed(
                    ctx,
                    "You don’t have any decks stored.\n"
                    "Type `!deck add` to add some.",
                )
            else:
                await simple_embed(
                    ctx, "{} hasn’t added any decks yet.".format(member.display_name)
                )
            return

        deck_id = 1
        results_max = 3
        for k, deck in decks.items():
            await self.upload_deck_image(
                ctx,
                deck["Deck"],
                deck["DeckName"],
                member,
                description="**{}**. {}".format(deck_id, deck["DeckName"]),
            )
            deck_id += 1

            if (deck_id - 1) % results_max == 0:
                if deck_id < len(decks):
                    await ctx.send("Would you like to see the next results?")
                    pred = MessagePredicate.yes_or_no(ctx)
                    await self.bot.wait_for("message", check=pred)
                    answer = pred.result
                    if not answer:
                        await ctx.send("Results aborted.")
                        return

    @deck.command(name="show")
    async def deck_show(
        self,
        ctx: commands.Context,
        deck_id: int,
        member: Optional[discord.Member] = None,
    ):
        """Show the deck of a user by id. With link to copy."""
        if not member:
            member = ctx.author
        deck_id -= 1
        decks = await self.settings.member(member).decks()
        if not decks:
            await simple_embed(ctx, "You have not added any decks.")
            return
        if len(decks) > deck_id + 1:
            await simple_embed(ctx, "This deck does not exist.")
            return
        for i, deck in enumerate(decks.values()):
            if i == deck_id:
                await self.deck_upload(ctx, deck["Deck"], deck["DeckName"], member)
                # generate link
                await self.decklink(ctx, deck["Deck"])

    async def decklink(self, ctx: commands.Context, deck_cards):
        """Show deck link depending on settings."""
        decklink_setting = await self.decklink_settings(ctx.guild)
        if decklink_setting == "embed":
            em = await self.decklink_embed(deck_cards)
            await ctx.send(embed=em)
        elif decklink_setting == "link":
            url = await self.decklink_url(deck_cards)
            await ctx.send("<{}>".format(url))

    async def decklink_embed(self, deck_cards, war=False):
        """Decklink embed."""
        url = await self.decklink_url(deck_cards, war=war)
        if war:
            em = discord.Embed(
                title="Copy deck to war deck", url=url, timestamp=dt.datetime.utcnow(),
            )
        else:
            em = discord.Embed(
                title="Copy deck", url=url, timestamp=dt.datetime.utcnow(),
            )
        em.set_footer(text=credits, icon_url=credits_icon)
        return em

    async def decklink_url(self, deck_cards, war=False):
        """Decklink URL."""
        deck_cards = self.normalize_deck_data(deck_cards)
        ids = []
        for card in deck_cards:
            id = await self.card_key_to_id(card)
            if id is not None:
                ids.append(await self.card_key_to_id(card))
        url = "https://link.clashroyale.com/deck/en?deck=" + ";".join(ids)
        if war:
            url += "&war=1"
        return url

    @deck.command(name="cards")
    async def deck_cards(self, ctx: commands.Context):
        """Display all available cards and acceptable abbreviations."""
        out = []

        for card in sorted(self.cards, key=lambda x: x["name"].lower()):
            key = card["key"]
            names = [key]
            name = card["name"]
            for abbrev_k, abbrev_v in self.cards_abbrev.items():
                if abbrev_v == key:
                    names.append(abbrev_k)
            rarity = card["rarity"]
            elixir = card["elixir"]
            out.append(
                "**{}** ({}, {} elixir): {}".format(
                    name, rarity, elixir, ", ".join(names)
                )
            )
        pages = []
        for page in pagify("\n".join(out), shorten_by=24):
            embed = discord.Embed(description=page, timestamp=dt.datetime.utcnow(),)
            embed.set_footer(text=credits, icon_url=credits_icon)
            pages.append(embed)
        await menu(ctx, pages, DEFAULT_CONTROLS, timeout=PAGINATION_TIMEOUT)

    @deck.command(name="search")
    async def deck_search(self, ctx: commands.Context, *params):
        """Search all decks by cards."""
        if not len(params):
            await simple_embed(ctx, "You must enter at least one card to search.")
            return
        all_members_data = list((await self.settings.all_members()).values())
        # normalize params
        params = self.normalize_deck_data(params)
        found_decks = []
        for member_data in all_members_data:
            for member_id, server_member in member_data.items():
                member_decks = server_member["decks"]
                member_id = member_id
                member = self.bot.get_user(member_id)
                if member:
                    member_display_name = member.getattr("display_name", None)
                else:
                    member = member_id
                    member_display_name = member_id
                for k, member_deck in member_decks.items():
                    cards = member_deck["Deck"]
                    # await self.bot.say(set(params))
                    if set(params) < set(cards):
                        found_decks.append(
                            {
                                "UTC": k,
                                "Deck": member_deck["Deck"],
                                "DeckName": member_deck["DeckName"],
                                "Member": member,
                                "MemberDisplayName": member_display_name,
                            }
                        )
        found_decks = sorted(found_decks, key=lambda x: x["UTC"], reverse=True)

        await ctx.send("Found {} decks".format(len(found_decks)))
        if len(found_decks):
            results_max = 3
            deck_id = 1
            for deck in found_decks:
                timestamp = deck["UTC"][:19]
                description = "**{}. {}** by {} — {}".format(
                    deck_id, deck["DeckName"], deck["MemberDisplayName"], timestamp
                )
                await self.upload_deck_image(
                    ctx,
                    deck["Deck"],
                    deck["DeckName"],
                    deck["Member"],
                    description=description,
                )
                deck_id += 1
                if (deck_id - 1) % results_max == 0:
                    if deck_id < len(found_decks):
                        await ctx.send("Would you like to see the next results?")
                        pred = MessagePredicate.yes_or_no(ctx)
                        await self.bot.wait_for("message", check=pred)
                        answer = pred.result
                        if not answer:
                            await ctx.send("Results aborted.")
                            return

    @deck.command(name="rename")
    async def deck_rename(self, ctx: commands.Context, deck_id: int, *, new_name: str):
        """Rename a deck based on deck id.

        Syntax: !deck rename [deck_id] [new_name]
        where deck_id is the number associated with the deck when you run !deck list
        """
        author = ctx.message.author
        deck_id = int(deck_id) - 1
        async with self.settings.member(author).decks() as member_decks:
            # check member has data
            if not len(member_decks):
                await simple_embed(ctx, "You have not added any decks.")
                return
            if deck_id >= len(member_decks):
                await simple_embed(ctx, "The deck id you have entered is invalid.")
                return
            for i, deck in enumerate(member_decks.values()):
                if deck_id == i:
                    deck["DeckName"] = new_name
            await simple_embed(ctx, "Deck renamed to {}.".format(new_name))
            await self.deck_upload(ctx, deck["Deck"], new_name, author)

    @deck.command(name="remove")
    async def deck_remove(self, ctx: commands.Context, deck_id: int):
        """Remove a deck by deck id."""
        author = ctx.message.author
        async with self.settings.member(author).decks() as member_decks:
            if not len(member_decks):
                await simple_embed(ctx, "You have not added any decks.")
            else:
                deck_id = int(deck_id) - 1
                if deck_id >= len(member_decks):
                    await simple_embed(ctx, "The deck id you have entered is invalid.")
                else:
                    remove_key = ""
                    for i, key in enumerate(member_decks.keys()):
                        if deck_id == i:
                            remove_key = key
                    member_decks.pop(remove_key)
                    await simple_embed(ctx, "Deck {} removed.".format(deck_id + 1))

    @deck.command(name="help")
    async def deck_help(self, ctx: commands.Context):
        """Complete help and tutorial."""
        await simple_embed(
            ctx,
            "Please visit [this link]({}) for an illustrated guide.".format(HELP_URL),
        )

    async def deck_upload(
        self, ctx: commands.Context, member_deck, deck_name: str, member=None
    ):
        """Upload deck to Discord."""
        author = ctx.message.author
        if member is None:
            member = author
        member_deck = self.normalize_deck_data(member_deck)
        deck_is_valid = True
        # Ensure: exactly 8 cards are entered
        if len(member_deck) != 8:
            await ctx.send(
                "You have entered {} card{}. "
                "Please enter exactly 8 cards.".format(
                    len(member_deck), "s" if len(member_deck) > 1 else ""
                )
            )
            await ctx.send_help()
            deck_is_valid = False

        # Ensure: card names are valid
        if not set(member_deck) < set(self.valid_card_keys):
            for card in member_deck:
                if card not in self.valid_card_keys:
                    await ctx.send("**{}** is not a valid card name.".format(card))
            await ctx.send("\nType `{}deck cards` for the full list".format(ctx.prefix))
            deck_is_valid = False

        if deck_is_valid:
            await self.post_deck(
                channel=ctx.message.channel,
                card_keys=member_deck,
                deck_name=deck_name,
                deck_author=member.display_name,
            )
        self.deck_is_valid = deck_is_valid

    async def upload_deck_image(
        self, ctx: commands.Context, deck, deck_name, author, **embed_params
    ):
        """Upload deck image to the server."""

        deck_image = await self.bot.loop.run_in_executor(
            None, self.get_deck_image, deck, deck_name, author
        )

        # construct a filename using first three letters of each card
        filename = "deck-{}.png".format("-".join([card[:3] for card in deck]))

        message = None

        with io.BytesIO() as f:
            deck_image.save(f, "PNG")
            f.seek(0)
            timestamp = embed_params.pop("timestamp", dt.datetime.utcnow())
            embed = discord.Embed(timestamp=timestamp, **embed_params,)
            embed.set_image(url="attachment://{}".format(filename))
            embed.set_footer(text=credits, icon_url=credits_icon)
            message = await ctx.message.channel.send(
                file=discord.File(f, filename=filename), embed=embed
            )

        return message

    async def upload_deck_image_to(
        self, channel, deck, deck_name, author, **embed_params
    ):
        """Upload deck image to destination."""
        deck_image = await self.bot.loop.run_in_executor(
            None, self.get_deck_image, deck, deck_name, author
        )

        # construct a filename using first three letters of each card
        filename = "deck-{}.png".format("-".join([card[:3] for card in deck]))

        message = None

        with io.BytesIO() as f:
            deck_image.save(f, "PNG")
            f.seek(0)
            timestamp = embed_params.pop("timestamp", dt.datetime.utcnow())
            embed = discord.Embed(timestamp=timestamp, **embed_params)
            embed.set_image(url="attachment://{}".format(filename))
            embed.set_footer(text=credits, icon_url=credits_icon)
            message = await channel.send(
                file=discord.File(f, filename=filename), embed=embed
            )
            # message = await self.bot.send_file(
            #     , f,
            #     filename=filename, content=description)

        return message

    def get_deck_elxir(self, card_keys):
        # elixir
        total_elixir = 0
        # total card exclude mirror (0-elixir cards)
        card_count = 0

        for card in self.cards:
            if card["key"] in card_keys:
                total_elixir += card["elixir"]
                if card["elixir"]:
                    card_count += 1

        average_elixir = "{:.3f}".format(total_elixir / card_count)

        return average_elixir

    def get_deck_image(self, deck, deck_name=None, deck_author=None):
        """Construct the deck with Pillow and return image."""
        card_w = 302
        card_h = 363
        card_x = 30
        card_y = 30
        font_size = 50
        txt_y_line1 = 430
        txt_y_line2 = 500
        txt_x_name = 50
        txt_x_cards = 503
        txt_x_elixir = 1872

        bg_image = Image.open(
            str(bundled_data_path(self) / "img" / "deck-bg-b-legend-logo.png")
        )
        size = bg_image.size

        font_file_regular = str(
            bundled_data_path(self) / "fonts" / "OpenSans-Regular.ttf"
        )
        font_file_bold = str(bundled_data_path(self) / "fonts/OpenSans-Bold.ttf")

        image = Image.new("RGBA", size)
        image.paste(bg_image)

        if not deck_name:
            deck_name = "Deck"

        # cards
        for i, card in enumerate(deck):
            card_image_file = str(
                bundled_data_path(self) / "img" / "cards" / "{}.png".format(card)
            )
            card_image = Image.open(card_image_file)
            # size = (card_w, card_h)
            # card_image.thumbnail(size)
            box = (
                card_x + card_w * i,
                card_y,
                card_x + card_w * (i + 1),
                card_h + card_y,
            )
            image.paste(card_image, box, card_image)

        # # elixir
        # total_elixir = 0
        # # total card exclude mirror (0-elixir cards)
        # card_count = 0
        #
        # for card in self.cards:
        #     if card["key"] in deck:
        #         total_elixir += card["elixir"]
        #         if card["elixir"]:
        #             card_count += 1
        #
        # average_elixir = "{:.3f}".format(total_elixir / card_count)

        average_elixir = self.get_deck_elxir(deck)

        # text
        # Take out hyphnens and capitlize the name of each card
        card_names = [string.capwords(c.replace("-", " ")) for c in deck]

        txt = Image.new("RGBA", size)
        txt_name = Image.new("RGBA", (txt_x_cards - 30, size[1]))
        font_regular = ImageFont.truetype(font_file_regular, size=font_size)
        font_bold = ImageFont.truetype(font_file_bold, size=font_size)

        d = ImageDraw.Draw(txt)
        d_name = ImageDraw.Draw(txt_name)

        line1 = ", ".join(card_names[:4])
        line2 = ", ".join(card_names[4:])
        # card_text = '\n'.join([line0, line1])

        if deck_author:
            if isinstance(deck_author, str):
                deck_author_name = deck_author
            elif hasattr(deck_author, "display_name"):
                deck_author_name = deck_author.display_name
            else:
                deck_author_name = ""
        else:
            deck_author_name = ""

        # deck_author_name = deck_author.name if deck_author else ""

        d_name.text(
            (txt_x_name, txt_y_line1),
            deck_name,
            font=font_bold,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )
        d_name.text(
            (txt_x_name, txt_y_line2),
            deck_author_name,
            font=font_regular,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )
        d.text(
            (txt_x_cards, txt_y_line1),
            line1,
            font=font_regular,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )
        d.text(
            (txt_x_cards, txt_y_line2),
            line2,
            font=font_regular,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )
        d.text(
            (txt_x_elixir, txt_y_line1),
            "Avg elixir",
            font=font_bold,
            fill=(0xFF, 0xFF, 0xFF, 200),
        )
        d.text(
            (txt_x_elixir, txt_y_line2),
            average_elixir,
            font=font_bold,
            fill=(0xFF, 0xFF, 0xFF, 255),
        )

        image.paste(txt, (0, 0), txt)
        image.paste(txt_name, (0, 0), txt_name)

        # scale down and return
        scale = 0.5
        scaled_size = tuple([x * scale for x in image.size])
        image.thumbnail(scaled_size)

        return image

    def normalize_deck_data(self, deck):
        """Return a deck list with normalized names."""
        deck = [c.lower() if c is not None else "" for c in deck]
        # replace abbreviations
        for i, card in enumerate(deck):
            if card in self.cards_abbrev.keys():
                deck[i] = self.cards_abbrev[card]
        return deck

    @commands.Cog.listener()
    async def on_message_without_command(self, msg: discord.Message):
        """Listen for decklinks, auto create useful image."""
        if msg.guild is None or msg.author.bot:
            return

        try:
            auto_deck_link = await self.settings.guild(msg.guild).auto_deck_link()
        except KeyError:
            pass
        else:
            if auto_deck_link:
                card_keys = await self.decklink_to_cards(msg.content)
                if card_keys is None:
                    return

                await self.post_deck(
                    channel=msg.channel, card_keys=card_keys, deck_author=msg.author
                )

                try:
                    await msg.delete()
                except discord.DiscordException:
                    pass

    async def post_deck(
        self,
        channel=None,
        title=None,
        description=None,
        timestamp=None,
        card_keys=None,
        deck_name=None,
        deck_author=None,
        color=None,
        player_tag=None,
        link=None,
    ):
        """Post a deck to destination channel.

        If image server is set, post as an embed.
        If not, post as image with associated links.
        """
        msg = None

        # if image server is set, upload as embed
        has_image_server = False
        img_channel_id = (await self.settings.guild(channel.guild).image_server()).get(
            "channel_id", None
        )
        if img_channel_id:
            img_channel = self.bot.get_channel(img_channel_id)
            if img_channel:
                url = await self.decklink_url(card_keys, war=False)
                img_msg = await self.upload_deck_image_to(
                    img_channel,
                    card_keys,
                    deck_name,
                    deck_author or self.bot.name,
                    title="Copy deck",
                    url=url,
                )
                if len(img_msg.attachments) != 0:
                    img_url = img_msg.attachments[0].url
                elif len(img_msg.embeds) != 0:
                    img_url = img_msg.embeds[0].image.url
                else:
                    await channel.send("Cannot get url for deck.")
                    return
                if link is not None:
                    url = link
                else:
                    url = await self.decklink_url(card_keys)
                em = discord.Embed(
                    title=title or "Deck",
                    description=description,
                    color=color or discord.Color.blue(),
                    url=url,
                    timestamp=timestamp or dt.datetime.utcnow(),
                )
                em.set_footer(text=credits, icon_url=credits_icon)

                link_values = [
                    "[Deck Stats]({})".format(
                        "https://royaleapi.com/decks/stats/{}".format(
                            ",".join(card_keys)
                        )
                    ),
                    "[Copy]({})".format(await self.decklink_url(card_keys)),
                ]

                if player_tag is not None:
                    link_values.append(
                        "[Battle Log]({})".format(
                            "https://royaleapi.com/player/{}/battles".format(player_tag)
                        )
                    )

                em.add_field(
                    name="Avg Elixir: {}".format(self.get_deck_elxir(card_keys)),
                    value=" • ".join(link_values),
                )
                em.set_image(url=img_url)
                msg = await channel.send(embed=em)
                has_image_server = True

        if not has_image_server:
            url = await self.decklink_url(card_keys, war=False)
            msg = await self.upload_deck_image_to(
                channel,
                card_keys,
                "Deck",
                deck_author or self.bot.name,
                title="Copy deck",
                url=url,
            )

        return msg
