class Attachments:
    def __init__(self, account):
        self._account = account

    def attachment_url(self, tournament, match):
        return "tournaments/{}/matches/{}/attachments".format(tournament, match)

    async def index(self, tournament, match, **params):
        """Retrieve a set of attachments associated with a match."""
        return await self._account.fetch_and_parse(
            "GET", self.attachment_url(tournament, match), **params
        )

    async def create(
        self, tournament, match, description="", asset="", url="", **params
    ):
        """Create a new attachment."""
        # @TODO: Support a file upload here explicitly. Not sure how
        params.update({"asset": asset, "url": url, "description": description})
        return await self._account.fetch_and_parse(
            "POST", self.attachment_url(tournament, match), "match_attachment", **params
        )

    async def show(self, tournament, match, attachment, **params):
        """Retrieve a single attachment record created with your account."""
        return await self._account.fetch_and_parse(
            "GET", self.attachment_url(tournament, match) + "/%s" % attachment, **params
        )

    async def update(self, tournament, match, attachment, **params):
        """Update a single attachment record created with your account."""
        await self._account.fetch(
            "PUT",
            self.attachment_url(tournament, match) + "/%s" % attachment,
            "match_attachment",
            **params
        )

    async def destroy(self, tournament, match, attachment):
        """Deletes a attachment along with all its associated records.

        There is no undo, so use with care!

        """
        await self._account.fetch(
            "DELETE", self.attachment_url(tournament, match) + "/%s" % attachment
        )
