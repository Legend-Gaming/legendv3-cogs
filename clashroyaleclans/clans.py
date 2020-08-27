"""Base class for handling clan data"""

import json

from redbot.core.data_manager import cog_data_path


class Clans:
    async def initialize(self, bot):
        self.bot = bot
        self.crclans = self.bot.get_cog("ClashRoyaleClans")
        self.claninfo_path = str(cog_data_path(self) / "clans.json")
        with open(self.claninfo_path) as file:
            self.family_clans = dict(json.load(file))

    async def getClans(self):
        """Return clan array"""
        return self.family_clans

    async def getClanData(self, clankey, data):
        """Return clan array"""
        return self.family_clans[clankey][data]

    async def getClanMemberData(self, clankey, memberkey, data):
        """Return clan member's dict"""
        return self.clans[clankey]["members"][memberkey][data]

    async def numClans(self):
        """Return the number of clans"""
        return len(self.clans.keys())

    def keysClans(self):
        """Get keys of all the clans"""
        return self.clans.keys()

    def keysClanMembers(self, clankey):
        """Get keys of all the clan members"""
        return self.clans[clankey]["members"].keys()

    async def namesClans(self):
        """Get name of all the clans"""
        return ", ".join(key for key in self.keysClans())

    async def tagsClans(self):
        """Get tags of all the clans"""
        return [self.clans[clan]["tag"] for clan in self.clans]

    async def rolesClans(self):
        """Get roles of all the clans"""
        roles = ["Member"]
        for x in self.clans:
            roles.append(self.clans[x]["role"])
        return roles

    async def verifyMembership(self, clantag):
        """Check if a clan is part of the family"""
        for clankey in self.keysClans():
            if self.clans[clankey]["tag"] == clantag:
                return True
        return False

    async def getClanKey(self, clantag):
        """Get a clan key from a clan tag."""
        for clankey in self.keysClans():
            if self.clans[clankey]["tag"] == clantag:
                return clankey
        return None

    async def numWaiting(self, clankey):
        """Get a clan's wating list length from a clan key."""
        return len(self.clans[clankey]["waiting"])

    async def setWarTrophies(self, clankey, trophies):
        """Set a clan's wartrophies"""
        self.clans[clankey]["warTrophies"] = trophies
        dataIO.save_json(clans_path, self.clans)

    async def setWarstats(self, clankey, tag, trophies, cards):
        """Set a clan member's wins and cards"""
        self.clans[clankey]["members"][tag]["WarDayWins"] = trophies
        self.clans[clankey]["members"][tag]["cardsEarned"] = cards
        dataIO.save_json(clans_path, self.clans)

    async def getMemberWins(self, clankey, tag):
        """Get a member's war day wins from the week"""
        try:
            return self.clans[clankey]["members"][tag]["WarDayWins"]
        except KeyError:
            return 0

    async def getMemberCards(self, clankey, tag):
        """Get a member's cardsEarned from the week"""
        try:
            return self.clans[clankey]["members"][tag]["cardsEarned"]
        except KeyError:
            return 0

    async def getClanCWR(self, clankey, league):
        """Get a clan's CWR"""
        try:
            return self.clans[clankey]["cwr"][league]
        except KeyError:
            return 0

    async def addWaitingMember(self, clankey, memberID):
        """Add a user to a clan's waiting list"""
        if memberID not in self.clans[clankey]["waiting"]:
            self.clans[clankey]["waiting"].append(memberID)
            dataIO.save_json(clans_path, self.clans)
            return True
        else:
            return False

    async def delWaitingMember(self, clankey, memberID):
        """Remove a user to a clan's waiting list"""
        if memberID in self.clans[clankey]["waiting"]:
            self.clans[clankey]["waiting"].remove(memberID)
            dataIO.save_json(clans_path, self.clans)

            return True
        else:
            return False

    async def checkWaitingMember(self, clankey, memberID):
        """check if a user is in a waiting list"""
        return memberID in self.clans[clankey]["waiting"]

    async def getWaitingIndex(self, clankey, memberID):
        """Get the waiting position from a clan's waiting list"""
        return self.clans[clankey]["waiting"].index(memberID)

    async def delClan(self, clankey):
        """delete a clan from the family"""
        if self.clans.pop(clankey, None):
            dataIO.save_json(clans_path, self.clans)
            return True
        return False

    async def setPBTrophies(self, clankey, trophies):
        """Set a clan's PB Trohies"""
        self.clans[clankey]["personalbest"] = trophies
        dataIO.save_json(clans_path, self.clans)

    async def setCWR(self, clankey, league, cwr):
        """Set a clan's CWR"""
        self.clans[clankey]["cwr"][league] = cwr
        dataIO.save_json(clans_path, self.clans)

    async def setBonus(self, clankey, bonus):
        """Set a clan's Bonus Statement"""
        self.clans[clankey]["bonustitle"] = bonus
        dataIO.save_json(clans_path, self.clans)

    async def setLogChannel(self, clankey, channel):
        """Set a clan's log channel"""
        self.clans[clankey]["log_channel"] = channel
        dataIO.save_json(clans_path, self.clans)

    async def setWarLogChannel(self, clankey, channel):
        """Set a clan's warlog channel"""
        self.clans[clankey]["warlog_channel"] = channel
        dataIO.save_json(clans_path, self.clans)

    async def addMember(self, clankey, name, tag):
        """Add a member to the clan"""
        self.clans[clankey]["members"][tag] = {}
        self.clans[clankey]["members"][tag]["tag"] = tag
        self.clans[clankey]["members"][tag]["name"] = name
        self.clans[clankey]["members"][tag]["WarDayWins"] = 0
        self.clans[clankey]["members"][tag]["cardsEarned"] = 0
        dataIO.save_json(clans_path, self.clans)

    async def delMember(self, clankey, tag):
        """Remove a member to the clan"""
        self.clans[clankey]["members"].pop(tag, None)
        dataIO.save_json(clans_path, self.clans)

    async def togglePrivate(self, clankey):
        """oggle Private approval of new recruits"""
        self.clans[clankey]["approval"] = not self.clans[clankey]["approval"]
        dataIO.save_json(clans_path, self.clans)

        return self.clans[clankey]["approval"]
