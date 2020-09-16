class Tournaments:
    def __init__(self, account):
        self._account = account

    async def index(self, **params):
        """Retrieve a set of tournaments created with your account."""
        return await self._account.fetch_and_parse("GET", "tournaments", **params)

    async def create(self, name, url, tournament_type="single elimination", **params):
        """Create a new tournament."""
        params.update(
            {"name": name, "url": url, "tournament_type": tournament_type,}
        )

        return await self._account.fetch_and_parse(
            "POST", "tournaments", "tournament", **params
        )

    async def show(self, tournament, **params):
        """Retrieve a single tournament record created with your account."""
        return await self._account.fetch_and_parse(
            "GET", "tournaments/%s" % tournament, **params
        )

    async def update(self, tournament, **params):
        """Update a tournament's attributes."""
        await self._account.fetch(
            "PUT", "tournaments/%s" % tournament, "tournament", **params
        )

    async def destroy(self, tournament):
        """Deletes a tournament along with all its associated records.

        There is no undo, so use with care!

        """
        await self._account.fetch("DELETE", "tournaments/%s" % tournament)

    async def process_check_ins(self, tournament):
        """This should be invoked after a tournament's
        check-in window closes before the tournament is started.

        1) Marks participants who have not checked in as inactive.
        2) Moves inactive participants to bottom seeds (ordered by original seed).
        3) Transitions the tournament state from 'checking_in' to 'checked_in'

        """
        await self._account.fetch("POST", "tournaments/%s/process_check_ins")

    async def abort_check_in(self, tournament):
        """When your tournament is in a 'checking_in' or 'checked_in' state,
        there's no way to edit the tournament's start time (start_at)
        or check-in duration (check_in_duration).
        You must first abort check-in, then you may edit those attributes.

        1) Makes all participants active and clears their checked_in_at times.
        2) Transitions the tournament state from 'checking_in' or 'checked_in' to 'pending'

        """
        await self._account.fetch("POST", "tournaments/%s/abort_check_in")

    async def start(self, tournament):
        """Start a tournament, opening up matches for score reporting.

        The tournament must have at least 2 participants.

        """
        return await self._account.fetch_and_parse(
            "POST", "tournaments/%s/start" % tournament
        )

    async def finalize(self, tournament, **params):
        """Finalize a tournament that has had all match scores submitted,
        rendering its results permanent.

        """
        return await self._account.fetch_and_parse(
            "POST", "tournaments/%s/finalize" % tournament, **params
        )

    async def reset(self, tournament):
        """Reset a tournament, clearing all of its scores and attachments.

        You can then add/remove/edit participants before starting the
        tournament again.

        """
        await self._account.fetch("POST", "tournaments/%s/reset" % tournament)
