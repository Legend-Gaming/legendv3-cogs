class Participants:
    def __init__(self, account):
        self._account = account

    async def index(self, tournament):
        """Retrieve a tournament's participant list."""
        return await self._account.fetch_and_parse(
            "GET", "tournaments/%s/participants" % tournament
        )

    async def create(self, tournament, name, **params):
        """Add a participant to a tournament."""
        params.update({"name": name})

        return await self._account.fetch_and_parse(
            "POST", "tournaments/%s/participants" % tournament, "participant", **params
        )

    async def bulk_add(self, tournament, names, **params):
        """Bulk add participants to a tournament (up until it is started).

        :param tournament: the tournament's name or id
        :param names: the names of the participants
        :type tournament: int or string
        :type names: list or tuple
        :return: each participants info
        :rtype: a list of dictionaries

        """
        params.update({"name": names})

        return await self._account.fetch_and_parse(
            "POST",
            "tournaments/%s/participants/bulk_add" % tournament,
            "participants[]",
            **params
        )

    async def show(self, tournament, participant_id):
        """Retrieve a single participant record for a tournament."""
        return await self._account.fetch_and_parse(
            "GET", "tournaments/%s/participants/%s" % (tournament, participant_id)
        )

    async def update(self, tournament, participant_id, **params):
        """Update the attributes of a tournament participant."""
        await self._account.fetch(
            "PUT",
            "tournaments/%s/participants/%s" % (tournament, participant_id),
            "participant",
            **params
        )

    async def check_in(self, tournament, participant_id):
        """Checks a participant in."""
        await self._account.fetch(
            "POST",
            "tournaments/%s/participants/%s/check_in" % (tournament, participant_id),
        )

    async def undo_check_in(self, tournament, participant_id):
        """Marks a participant as having not checked in."""
        await self._account.fetch(
            "POST",
            "tournaments/%s/participants/%s/undo_check_in"
            % (tournament, participant_id),
        )

    async def destroy(self, tournament, participant_id):
        """Destroys or deactivates a participant.

        If tournament has not started, delete a participant, automatically
        filling in the abandoned seed number.

        If tournament is underway, mark a participant inactive, automatically
        forfeiting his/her remaining matches.

        """
        await self._account.fetch(
            "DELETE", "tournaments/%s/participants/%s" % (tournament, participant_id)
        )

    async def randomize(self, tournament):
        """Randomize seeds among participants.

        Only applicable before a tournament has started.

        """
        await self._account.fetch(
            "POST", "tournaments/%s/participants/randomize" % tournament
        )
