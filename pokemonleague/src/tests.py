from __future__ import print_function

import asyncio
import datetime
import os
import random
import string
import unittest

from challonge import Account, ChallongeException

username = None
api_key = None


def _get_random_name():
    return "pychallonge_" + "".join(
        random.choice(string.ascii_lowercase) for _ in range(0, 15)
    )


def async_test(f):
    def wrapper(*args, **kwargs):
        coro = asyncio.coroutine(f)
        future = coro(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)

    return wrapper


class AccountTestCase(unittest.TestCase):
    def test_init(self):
        account = Account(username, api_key)
        self.assertEqual(account._user, username)
        self.assertEqual(account._api_key, api_key)

    @async_test
    def test_is_valid(self):
        account = Account(username, api_key)
        is_valid = yield from account.is_valid
        self.assertTrue(is_valid)

    @async_test
    def test_call(self):
        account = Account(username, api_key)
        t = yield from account.fetch("GET", "tournaments")
        self.assertNotEqual(t, "")


class TournamentsTestCase(unittest.TestCase):
    @async_test
    def setUp(self):
        self._account = Account(username, api_key)
        random_name = _get_random_name()

        self.t = yield from self._account.tournaments.create(random_name, random_name)

    @async_test
    def tearDown(self):
        yield from self._account.tournaments.destroy(self.t["id"])

    @async_test
    def test_index(self):
        ts = yield from self._account.tournaments.index()
        ts = list(filter(lambda x: x["id"] == self.t["id"], ts))
        self.assertEqual(len(ts), 1)
        self.assertEqual(self.t, ts[0])

    @async_test
    def test_index_filter_by_state(self):
        ts = yield from self._account.tournaments.index(state="pending")
        ts = list(filter(lambda x: x["id"] == self.t["id"], ts))
        self.assertEqual(len(ts), 1)
        self.assertEqual(self.t, ts[0])

        ts = yield from self._account.tournaments.index(state="in_progress")
        ts = list(filter(lambda x: x["id"] == self.t["id"], ts))
        self.assertEqual(ts, [])

    @async_test
    def test_index_filter_by_created(self):
        ts = yield from self._account.tournaments.index(
            created_after=datetime.datetime.now().date() - datetime.timedelta(days=1)
        )
        ts = filter(lambda x: x["id"] == self.t["id"], ts)
        self.assertTrue(self.t["id"] in map(lambda x: x["id"], ts))

    @async_test
    def test_show(self):
        t = yield from self._account.tournaments.show(self.t["id"])
        self.assertEqual(t, self.t)

    @async_test
    def test_update_name(self):
        yield from self._account.tournaments.update(self.t["id"], name="Test!")

        t = yield from self._account.tournaments.show(self.t["id"])

        self.assertEqual(t["name"], "Test!")
        t.pop("name")
        self.t.pop("name")

        self.assertTrue(t["updated-at"] >= self.t["updated-at"])
        t.pop("updated-at")
        self.t.pop("updated-at")

        self.assertEqual(t, self.t)

    @async_test
    def test_update_private(self):
        yield from self._account.tournaments.update(self.t["id"], private=True)

        t = yield from self._account.tournaments.show(self.t["id"])

        self.assertEqual(t["private"], True)

    @async_test
    def test_update_type(self):
        yield from self._account.tournaments.update(
            self.t["id"], tournament_type="round robin"
        )

        t = yield from self._account.tournaments.show(self.t["id"])

        self.assertEqual(t["tournament-type"], "round robin")

    @async_test
    def test_start(self):
        # we have to add participants in order to start()
        try:
            yield from self._account.tournaments.start(self.t["id"])
        except ChallongeException:
            self.assertTrue(True)
        else:
            self.fail("Could start tournament without participants")

        self.assertEqual(self.t["started-at"], None)

        yield from self._account.participants.create(self.t["id"], "#1")
        yield from self._account.participants.create(self.t["id"], "#2")

        t = yield from self._account.tournaments.show(
            self.t["id"], include_participants=1, include_matches=1
        )
        self.assertNotEqual(t["participants"], [])

        t = yield from self._account.tournaments.start(self.t["id"])
        self.assertNotEqual(t["started-at"], None)

    @async_test
    def test_finalize(self):
        yield from self._account.participants.create(self.t["id"], "#1")
        yield from self._account.participants.create(self.t["id"], "#2")

        yield from self._account.tournaments.start(self.t["id"])
        ms = yield from self._account.matches.index(self.t["id"])
        self.assertEqual(ms[0]["state"], "open")

        yield from self._account.matches.update(
            self.t["id"],
            ms[0]["id"],
            scores_csv="3-2,4-1,2-2",
            winner_id=ms[0]["player1-id"],
        )

        yield from self._account.tournaments.finalize(self.t["id"])
        t = yield from self._account.tournaments.show(self.t["id"])

        self.assertNotEqual(t["completed-at"], None)

    @async_test
    def test_reset(self):
        # have to add participants in order to start()
        yield from self._account.participants.create(self.t["id"], "#1")
        yield from self._account.participants.create(self.t["id"], "#2")

        yield from self._account.tournaments.start(self.t["id"])

        # we can't add participants to a started tournament...
        try:
            yield from self._account.participants.create(self.t["id"], "#3")
        except ChallongeException:
            self.assertTrue(True)
        else:
            self.assertTrue(False)

        yield from self._account.tournaments.reset(self.t["id"])

        # but we can add participants to a reset tournament
        p = yield from self._account.participants.create(self.t["id"], "name")

        yield from self._account.participants.destroy(self.t["id"], p["id"])


class ParticipantsTestCase(unittest.TestCase):
    @async_test
    def setUp(self):
        self._account = Account(username, api_key)
        self.t_name = _get_random_name()

        self.t = yield from self._account.tournaments.create(self.t_name, self.t_name)
        self.p1_name = _get_random_name()
        self.p1 = yield from self._account.participants.create(
            self.t["id"], self.p1_name
        )
        self.p2_name = _get_random_name()
        self.p2 = yield from self._account.participants.create(
            self.t["id"], self.p2_name
        )

    @async_test
    def tearDown(self):
        yield from self._account.tournaments.destroy(self.t["id"])

    @async_test
    def test_index(self):
        ps = yield from self._account.participants.index(self.t["id"])
        self.assertEqual(len(ps), 2)

        self.assertTrue(self.p1 == ps[0] or self.p1 == ps[1])
        self.assertTrue(self.p2 == ps[0] or self.p2 == ps[1])

    @async_test
    def test_show(self):
        p1 = yield from self._account.participants.show(self.t["id"], self.p1["id"])
        self.assertEqual(p1["id"], self.p1["id"])

    @async_test
    def test_bulk_add(self):
        ps_names = [_get_random_name(), _get_random_name()]
        misc = ["test_bulk1", "test_bulk2"]

        ps = yield from self._account.participants.bulk_add(
            self.t["id"], ps_names, misc=misc
        )
        self.assertEqual(len(ps), 2)

        self.assertTrue(ps_names[0] == ps[0]["name"] or ps_names[0] == ps[1]["name"])
        self.assertTrue(ps_names[1] == ps[0]["name"] or ps_names[1] == ps[1]["name"])

        self.assertTrue(misc[0] == ps[0]["misc"] or misc[0] == ps[1]["misc"])
        self.assertTrue(misc[1] == ps[0]["misc"] or misc[1] == ps[1]["misc"])

    @async_test
    def test_update(self):
        yield from self._account.participants.update(
            self.t["id"], self.p1["id"], misc="Test!"
        )
        p1 = yield from self._account.participants.show(self.t["id"], self.p1["id"])

        self.assertEqual(p1["misc"], "Test!")
        self.p1.pop("misc")
        p1.pop("misc")

        self.assertTrue(p1["updated-at"] >= self.p1["updated-at"])
        self.p1.pop("updated-at")
        p1.pop("updated-at")

        self.assertEqual(self.p1, p1)

    @async_test
    def test_randomize(self):
        # randomize has a 50% chance of actually being different than
        # current seeds, so we're just verifying that the method runs at all
        yield from self._account.participants.randomize(self.t["id"])


class MatchesTestCase(unittest.TestCase):
    @async_test
    def setUp(self):
        self._account = Account(username, api_key)
        self.t_name = _get_random_name()

        self.t = yield from self._account.tournaments.create(self.t_name, self.t_name)
        self.p1_name = _get_random_name()
        self.p1 = yield from self._account.participants.create(
            self.t["id"], self.p1_name
        )
        self.p2_name = _get_random_name()
        self.p2 = yield from self._account.participants.create(
            self.t["id"], self.p2_name
        )
        yield from self._account.tournaments.start(self.t["id"])

    @async_test
    def tearDown(self):
        yield from self._account.tournaments.destroy(self.t["id"])

    @async_test
    def test_index(self):
        ms = yield from self._account.matches.index(self.t["id"])

        self.assertEqual(len(ms), 1)
        m = ms[0]

        ps = set((self.p1["id"], self.p2["id"]))
        self.assertEqual(ps, set((m["player1-id"], m["player2-id"])))
        self.assertEqual(m["state"], "open")

    @async_test
    def test_show(self):
        ms = yield from self._account.matches.index(self.t["id"])
        for m in ms:
            r = yield from self._account.matches.show(self.t["id"], m["id"])
            self.assertEqual(m, r)

    @async_test
    def test_update(self):
        ms = yield from self._account.matches.index(self.t["id"])
        m = ms[0]
        self.assertEqual(m["state"], "open")

        yield from self._account.matches.update(
            self.t["id"],
            m["id"],
            scores_csv="3-2,4-1,2-2",
            winner_id=str(m["player1-id"]),
        )

        m = yield from self._account.matches.show(self.t["id"], m["id"])
        self.assertEqual(m["state"], "complete")


class AttachmentsTestCase(unittest.TestCase):
    @async_test
    def setUp(self):
        self._account = Account(username, api_key)
        self.t_name = _get_random_name()

        p = {"accept_attachments": "true"}
        self.t = yield from self._account.tournaments.create(
            self.t_name, self.t_name, **p
        )
        self.p1_name = _get_random_name()
        self.p1 = yield from self._account.participants.create(
            self.t["id"], self.p1_name
        )
        self.p2_name = _get_random_name()
        self.p2 = yield from self._account.participants.create(
            self.t["id"], self.p2_name
        )
        yield from self._account.tournaments.start(self.t["id"])
        ms = yield from self._account.matches.index(self.t["id"])
        self.m = ms[0]
        self.a1 = yield from self._account.attachments.create(
            self.t["id"], self.m["id"], "test_attachment_desc", "", "http://example.com"
        )

    @async_test
    def tearDown(self):
        yield from self._account.tournaments.destroy(self.t["id"])

    @async_test
    def test_index(self):
        ats = yield from self._account.attachments.index(self.t["id"], self.m["id"])
        self.assertEqual(len(ats), 1)
        self.assertEqual(ats[0]["id"], self.a1["id"])

    @async_test
    def test_show(self):
        ats = yield from self._account.attachments.show(
            self.t["id"], self.m["id"], self.a1["id"]
        )
        self.assertEqual(ats["id"], self.a1["id"])

    @async_test
    def test_update(self):
        yield from self._account.attachments.update(
            self.t["id"],
            self.m["id"],
            self.a1["id"],
            description="new_test_attachment_desc",
        )
        ats = yield from self._account.attachments.show(
            self.t["id"], self.m["id"], self.a1["id"]
        )
        self.assertEqual(ats["description"], "new_test_attachment_desc")


if __name__ == "__main__":
    username = os.environ.get("CHALLONGE_USER") if username is None else username
    api_key = os.environ.get("CHALLONGE_KEY") if api_key is None else api_key
    if not username or not api_key:
        raise RuntimeError(
            "You must add CHALLONGE_USER and CHALLONGE_KEY to your environment variables to run the test suite"
        )

    unittest.main()
