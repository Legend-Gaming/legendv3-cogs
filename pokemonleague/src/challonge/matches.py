class Matches:
    def __init__(self, account):
        self._account = account

    async def index(self, tournament, **params):
        """Retrieve a tournament's match list."""
        return await self._account.fetch_and_parse(
            "GET", "tournaments/%s/matches" % tournament, **params
        )

    async def show(self, tournament, match_id):
        """Retrieve a single match record for a tournament."""
        return await self._account.fetch_and_parse(
            "GET", "tournaments/%s/matches/%s" % (tournament, match_id)
        )

    async def update(self, tournament, match_id, **params):
        """Update/submit the score(s) for a match."""
        await self._account.fetch(
            "PUT",
            "tournaments/%s/matches/%s" % (tournament, match_id),
            "match",
            **params
        )
