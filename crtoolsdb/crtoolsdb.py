from json import load

import aiohttp
import clashroyale
import discord
import mysql.connector
from redbot.core import Config, checks, commands
from redbot.core.data_manager import bundled_data_path


class InvalidTag(Exception):
    pass


class TagAlreadySaved(Exception):
    """Note on this:

    This is only called when two tags from the same ID is saved

    Two people can have the same main / alts (Account sharing is a big thing nowadays)
    """

    pass


class MainAlreadySaved(Exception):
    pass


class InvalidArgument(Exception):
    pass


class NoConnection(Exception):
    pass


class Constants:
    """constants Management

    Credit: GR8
    Updated by: Generaleoley
    """

    def __init__(self):
        file_path = bundled_data_path(self)
        file_path = str(file_path) + "/constants.json"
        with open(file_path, "r") as file:
            self.constants = load(file)
        self.images = "https://royaleapi.github.io/cr-api-assets/"

    async def card_to_key(self, name):
        """Card key to decklink id."""
        for card in self.constants["cards"]:
            if name == card["name"]:
                return str(card["id"])
        return None

    async def card_to_rarity(self, name):
        """Card name to rarity."""
        for card in self.constants["cards"]:
            if name == card["name"]:
                return card["rarity"]
        return None

    async def get_new_level(self, card):
        """Convert the old card levels to the new ones"""
        newLevel = card.level
        if card.max_level == 11:
            newLevel = card.level + 2
        elif card.max_level == 8:
            newLevel = card.level + 5
        elif card.max_level == 5:
            newLevel = card.level + 8

        return newLevel

    async def get_region_key(self, num):
        """Get a region's key name."""
        for region in self.constants["regions"]:
            if num == region["id"]:
                return region["key"].lower()
        return None

    async def decklink_url(self, deck, war=False):
        """Decklink URL."""
        ids = []
        for card in deck:
            ids.append(await self.card_to_key(card["name"]))
        url = "https://link.clashroyale.com/deck/en?deck=" + ";".join(ids)
        if war:
            url += "&ID=CRRYRPCC&war=1"
        return url

    async def get_clan_image(self, p):
        """Get clan badge URL from badge ID"""
        try:
            badge_id = p.clan.badge_id
        except AttributeError:
            try:
                badge_id = p.badge_id
            except AttributeError:
                return "https://i.imgur.com/Y3uXsgj.png"

        if badge_id is None:
            return "https://i.imgur.com/Y3uXsgj.png"

        for i in self.constants["alliance_badges"]:
            if i["id"] == badge_id:
                return self.images + "badges/" + i["name"] + ".png"


class Tags:
    """Tag Management with Database

    Upgraded Version of Gr8's crtools by Generaleoley
    """

    def __init__(self, host, user, password, database):
        # hard coding because it's only us using this rn, future can use shared api key
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.setupConnection()

    def setupConnection(self):
        self.db = mysql.connector.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            database=self.database,
            connection_timeout=5,
        )
        if not self.db:
            raise NoConnection
        self.db.autocommit = True

    def setupDB(self):
        cursor = self.getCursor()

        query = f"""CREATE TABLE IF NOT EXISTS `tags` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `user_id` bigint(20) NOT NULL,
            `tag` varchar(15) NOT NULL,
            `account` int(32) NOT NULL,
            PRIMARY KEY (`id`),
            KEY `idx_user_id` (`user_id`),
            KEY `idx_tag` (`tag`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        cursor.execute(query)
        return

    def getCursor(self):
        try:
            self.db.ping(reconnect=True, attempts=3, delay=1)
        except mysql.connector.Error as err:
            self.db.close()
            self.setupConnection()
        return self.db.cursor()

    @staticmethod
    def verifyTag(tag):
        """Check if a player's tag is valid

        Credit: Gr8
        """
        check = ["P", "Y", "L", "Q", "G", "R", "J", "C", "U", "V", "0", "2", "8", "9"]
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
        return tag.strip("#").upper().replace("O", "0")

    def getTag(self, userID, account=1):
        """Get's a user's tag. Account 1 = Main

        If the account does not exist / not saved it returns None
        """
        cursor = self.getCursor()

        if self.accountCount(userID) < account or account < 1:
            return None

        query = f"SELECT tag FROM tags WHERE user_id = {userID} AND account = {account}"
        cursor.execute(query)
        return cursor.fetchone()[0]

    def accountCount(self, userID):
        """Get's the amount of accounts a user has

        Return value: Int

        0 - No accounts saved
        1 - Main Account Saved
        2+ - Main Account Saved + Some amount of alts (-1 to get the amount)
        """
        cursor = self.getCursor()
        query = f"SELECT id from tags WHERE user_id = {userID}"
        cursor.execute(query)
        return len(cursor.fetchall())

    def getTagsForUsers(self, userIDs):
        tagsByUser = {}

        userString = ",".join([str(userID) for userID in userIDs])
        query = f"SELECT user_id, tag FROM tags WHERE user_id IN ({userString})"

        cursor = self.getCursor()
        cursor.execute(query)
        for row in cursor.fetchall():
            tagsByUser.setdefault(row[0], [])
            tagsByUser[row[0]].append(row[1])
        return tagsByUser

    def quickGetAllTags(self, userID):
        tags = []

        query = f"SELECT tag FROM tags WHERE user_id = {userID}"
        cursor = self.getCursor()
        cursor.execute(query)
        for row in cursor.fetchall():
            tags.append(row[0])
        return tags

    def getAllTags(self, userID):
        """Returns a list of all tags from the given userID"""
        tags = []
        for count in range(self.accountCount(userID)):
            tag = self.getTag(userID, count + 1)
            tags.append(tag)
        return tags

    def saveTag(self, userID, tag):
        """Saves a tag to a player.

        Alt's are auto indexed
        """
        cursor = self.getCursor()

        count = self.accountCount(userID)

        tag = self.formatTag(tag=tag)
        if not self.verifyTag(tag):
            raise InvalidTag
        # if not main and count == 0:
        #     raise NoMainSaved
        # if main and count != 0:
        #     raise MainAlreadySaved
        if tag in self.getAllTags(userID):
            raise TagAlreadySaved

        account = count + 1

        query = f"INSERT INTO tags (user_id, tag, account) VALUES ({userID}, '{tag}', {account})"
        cursor.execute(query)

        return account

    def unlinkTag(self, userID, tag=None, account=None):
        """You can choose to use tag or account but not both or none"""
        cursor = self.getCursor()

        if (tag is None and account is None) or (
            tag is not None and account is not None
        ):
            raise TypeError

        if tag is not None:
            tag = self.formatTag(tag=tag)
            if not self.verifyTag(tag):
                raise InvalidTag

            tags = self.getAllTags(userID)

            if tag not in tags:
                raise InvalidArgument
            for item in range(len(tags)):
                if tags[item] == tag:
                    account = item + 1

        if account > self.accountCount(userID):
            raise InvalidArgument

        count = self.accountCount(userID)

        # Removes the tag and shifts the others if needed
        query = f"DELETE FROM tags WHERE user_id = {userID} AND account = {account}"
        cursor.execute(query)

        for item in range(account, count):
            query = f"UPDATE tags SET account = {item} WHERE user_id = {userID} AND account = {item + 1}"
            cursor.execute(query)

    def switchPlace(self, userID, account1, account2):
        """Switch the place of account 1 with 2"""

        cursor = self.getCursor()

        count = self.accountCount(userID)

        if (account1 > count or account1 < 1) or (account2 > count or account2 < 1):
            raise InvalidArgument

        querya = f"UPDATE tags SET account = 0 WHERE user_id = {userID} and account = {account1}"
        queryb = f"UPDATE tags SET account = {account1} WHERE user_id = {userID} and account = {account2}"
        queryc = f"UPDATE tags SET account = {account2} WHERE user_id = {userID} and account = 0"
        cursor.execute(querya)
        cursor.execute(queryb)
        cursor.execute(queryc)

    def getUser(self, tag):
        """Get all users that have this tag, returns dict in list

        [
            (userID, account)
        ]
        """

        cursor = self.getCursor()

        tag = self.formatTag(tag=tag)
        if not self.verifyTag(tag):
            raise InvalidTag

        query = f"SELECT user_id, account FROM tags WHERE tag = '{tag}'"
        cursor.execute(query)

        return cursor.fetchall()

    def moveUserID(self, oldUserID, newUserID):
        """To be used when a person changes accounts"""
        if self.accountCount(newUserID) != 0:
            raise MainAlreadySaved

        cursor = self.getCursor()
        query = f"UPDATE tags SET user_id = {newUserID} WHERE user_id = {oldUserID}"
        cursor.execute(query)


class ClashRoyaleTools(commands.Cog):
    """Assortment of commands for clash royale"""

    def __init__(self, bot):
        self.bot = bot
        self.constants = Constants()
        self.config = Config.get_conf(self, identifier=69420)
        default_global = {"emote_servers": False, "server_with_space": None}
        self.config.register_global(**default_global)

        self.token_task = self.bot.loop.create_task(self.crtoken())

    async def crtoken(self):
        # SQL Server
        database = await self.bot.get_shared_api_tokens("database")
        try:
            self.tags = Tags(
                database["host"],
                database["user"],
                database["password"],
                database["database"],
            )
            self.tags.setupDB()
        except Exception as e:
            print(
                "Database Credentials are not set or something went wrong Exception below. "
                "Set up a mysql server and enter credentials with the command"
                " [p]set api database host,HOST_IP user,USERNAME password,PASSWORD database,DATABASE "
                "replacing HOST_IP, USERNAME, PASSWORD, DATABASE with your credentials"
            )
            print(e)
            raise RuntimeError
        # Clash Royale API
        token = await self.bot.get_shared_api_tokens("clashroyale")
        if token.get("token") is None:
            print(
                "CR Token is not SET. Use !set api clashroyale token,YOUR_TOKEN to set it"
            )
            raise RuntimeError
        self.cr = clashroyale.official_api.Client(
            token=token["token"], is_async=True, url="https://proxy.royaleapi.dev/v1"
        )

    def cog_unload(self):
        print(
            "Unloaded CR-Tools... NOTE MANY DEPENDANCIES WILL BREAK INCLUDING TRADING, CLASHROYALESTATS AND CLASHROYALECLANS"
        )
        if self.token_task:
            self.token_task.cancel()
        if getattr(self, "cr", None):
            self.bot.loop.create_task(self.cr.close())
        if getattr(self, "tags", None):
            self.tags.db.close()

    @commands.group(name="crtools")
    async def _crtools(self, ctx):
        """CR Tools Command Group"""

    @_crtools.command(name="save")
    async def savetagcr(self, ctx, tag: str, user: discord.User = None):
        """Save your CR Tag"""
        tag = self.tags.formatTag(tag)
        if not self.tags.verifyTag(tag):
            return await ctx.send("Invalid Tag. Please try again.")

        # Trying to save tag for someone else
        if user is not None and user != ctx.author:
            if await self.bot.is_mod(ctx.author) is False:
                await ctx.send(
                    "Sorry you cannot save tags for others. You need a mod permission level"
                )
                return

        if user is None:
            user = ctx.author

        try:
            player = await self.cr.get_player(tag)
            name = player.name
        except clashroyale.NotFoundError:
            return await ctx.send("Invalid Tag. Please try again.")
        except clashroyale.RequestError:
            return await ctx.send("Sorry the CR API is down.")

        try:
            self.tags.saveTag(userID=user.id, tag=tag)
            embed = discord.Embed(
                color=discord.Color.green(),
                description="Use !accounts to see all accounts",
            )
            avatar = user.avatar_url if user.avatar else user.default_avatar_url
            embed.set_author(
                name="{} (#{}) has been successfully saved.".format(name, tag),
                icon_url=avatar,
            )
            embed.set_footer(text="Bot by: Generaleoley | Legend Gaming")
            await ctx.send(embed=embed)
        except InvalidTag:
            await ctx.send("Invalid Tag")
            return
        except TagAlreadySaved:
            await ctx.send("That tag has already been saved under this account")
            return
        except Exception as e:
            await ctx.send(
                "Unknown Error Occurred. Please report this bug with : ```{}```".format(
                    str(e)
                )
            )
            return

    @_crtools.command(name="accounts")
    async def listaccounts(self, ctx, user: discord.Member = None):
        """List your account and the account number that they are associated with"""

        if user is None:
            user = ctx.author

        tags = self.tags.getAllTags(user.id)

        embed = discord.Embed(
            title=f"{user.display_name} Clash Royale Accounts: ",
            color=discord.Color.green(),
        )

        accounts = ""
        number = 1

        try:
            for tag in tags:
                name = await self.cr.get_player(tag)
                accounts += f"{number}: {name.name} (#{tag})\n"
                number += 1
            if number == 1:
                accounts = "No CR Accounts saved :( \n\n Use !save <TAG> to save a tag"
        except clashroyale.RequestError:
            return await ctx.send("Sorry the CR API is down.")

        embed.add_field(name="Accounts", value=accounts)
        # todo maybe embed limits for people with 9000 accounts like Labda

        embed.set_footer(text="Bot by: Generaleoley | Legend Gaming")
        await ctx.send(embed=embed)

    @_crtools.command(name="switch")
    async def switchaccountorder(
        self, ctx, accounta: int, accountb: int, user: discord.Member = None
    ):
        """Swap the position of two accounts"""

        # Trying to do this for someone else
        if user is not None and user != ctx.author:
            if await self.bot.is_mod(ctx.author) is False:
                return await ctx.send(
                    "Sorry you cannot swap accounts for others. You need a mod permission level"
                )
        if user is None:
            user = ctx.author

        try:
            self.tags.switchPlace(user.id, accounta, accountb)
            await ctx.send("Done! Your accounts have been swapped!")
            await self.listaccounts(ctx, user=user)
        except InvalidArgument:
            return await ctx.send(
                "You don't have that many accounts."
                " Do `[p]crtools accounts` to see the accounts you have saved"
            )

    @_crtools.command(name="unsave")
    async def unsavetagcr(self, ctx, account: int, user: discord.User = None):
        """Unsave a tag"""

        # Trying to do this for someone else
        if user is not None and user != ctx.author:
            if await self.bot.is_mod(ctx.author) is False:
                return await ctx.send(
                    "Sorry you cannot unsave tags for others. You need a mod permission level"
                )

        if user is None:
            user = ctx.author

        try:
            self.tags.unlinkTag(userID=user.id, account=account)
            await ctx.send("Account Unlinked!")
            await self.listaccounts(ctx, user=user)
        except InvalidArgument:
            return await ctx.send(
                "You don't have that many accounts."
                " Do `[p]crtools accounts` to see the accounts you have saved"
            )

    @checks.mod_or_permissions(manage_roles=True)
    @_crtools.command(name="account_transfer")
    async def admin_account_transfer(
        self, ctx, oldAccount: discord.User, newAccount: discord.User
    ):
        """Administratively Transfer all Tags from one account to another"""
        try:
            self.tags.moveUserID(oldAccount.id, newAccount.id)
        except MainAlreadySaved:
            return await ctx.send(
                f"{newAccount.mention} already has accounts."
                f" Please use `!crtools unsave` to unsave them"
            )
        await ctx.send("Done...")
        await self.listaccounts(ctx, newAccount)

    @_crtools.command(name="accountowners")
    async def get_linked_users(self, ctx, tag):
        """Fetches a list of people that have this account saved"""
        try:
            users = self.tags.getUser(tag)
            if users is None:
                return await ctx.send(
                    "This account isn't linked to any discord account"
                )
            send = "Users with this account: (Discord Account | Account Number) \n"

            for user in users:
                send += f"<@{user[0]}> | {user[1]}\n"

            await ctx.send(send)

        except InvalidTag:
            return await ctx.send("Invalid Tag")
