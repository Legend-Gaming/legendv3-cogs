"""Legend Gaming Cog

Originally Coded by: GR8
Ported to V3 by: ThePeaceKeeper, Generaleoley

"""


import discord
from redbot.core import Config, checks, commands

# I'm not doing a seperate tags class it's not needed because there isn't SQL 
class BSTools(commands.Cog):
  """Tools for BrawlStars. Does not contain commands as of currently"""
  def __init__(self, bot):
    self.bot = bot;
    self.config = Config.get_conf(self, identifier=9034283423)
    default_user = { # todo feel free to do multiple tags, I really don't have the time rn @TPK
      'tag': None
    }
    self.config.register_user(**default_user) # User becauser it doesn't matter what server they are in
    
  async def getTag(self, user: discord.User):
    """Returns tag (str) without # , raises KeyError if not saved"""
    tag = await self.config.user(user).tag()
    if tag is None:
      raise KeyError
    return tag
    
  async def saveTag(self, user: discord.User, tag: str):
    """Saves user tag. Doesn't return anything. Throws ValueError if the tag is invalid"""
    tag = self.formatTag(tag)
    if(not self.verifyTag(tag)):
      raise ValueError
    await self.config.user(user).tag.set(tag)

    def emoji(self, name):
        """Emoji by name."""
        name = str(name)
        for emote in self.bot.emojis:
            if emote.name == name.replace(" ", "").replace("-", "").replace(".", ""):
                return '<:{}:{}>'.format(emote.name, emote.id)
        return ''

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

  async def getClanEmoji(self, tag):
      """Check if emoji exists for the clan"""
      clankey = await self.clubs.getBandKey(tag.strip("#"))
      if clankey is not None:
          return await self.clubs.getBandData(clankey, 'emoji')
      return self.emoji("clan")

  def getLeagueEmoji(self, trophies):
      """Get clan war League Emoji"""
      mapLeagues = {
          "starLeague": [10000, 90000],
          "masterLeague": [8000, 9999],
          "crystalLeague": [6000, 7999],
          "diamondLeague": [4000, 5999],
          "goldLeague": [3000, 3999],
          "silverLeague": [2000, 2999],
          "bronzeLeague": [1000, 1999],
          "woodLeague": [0, 999]
      }
      for league in mapLeagues.keys():
          if mapLeagues[league][0] <= trophies <= mapLeagues[league][1]:
              return self.emoji(league)

  async def getClanLeader(self, members):
      """Return clan leader from a list of members"""
      for member in members:
          if member.role == "president":
              return "{} {}".format(self.getLeagueEmoji(member.trophies), member.name)

  async def getCreaterName(self, tag, members: list):
      """Return clan leader from a list of members"""
      for member in members:
          if member.tag == tag:
              return member.name
      return ""
  
    
