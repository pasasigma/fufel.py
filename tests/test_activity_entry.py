import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from activity import Activity, CLIENT_ID


class EntryPointTests(unittest.IsolatedAsyncioTestCase):
    def activity(self, commands):
        activity = Activity.__new__(Activity)
        activity.commands_registered = True
        activity.bot = SimpleNamespace(application_id=int(CLIENT_ID), http=SimpleNamespace(
            request=AsyncMock(side_effect=[commands, {}])))
        return activity

    async def test_creates_entry_without_overwriting_other_commands(self):
        activity = self.activity([{'id': '7', 'type': 1, 'name': 'balance'}])
        self.assertTrue(await activity.register_entry_point())
        calls = activity.bot.http.request.call_args_list
        self.assertEqual([call.args[0].method for call in calls], ['GET', 'POST'])
        self.assertEqual(calls[1].kwargs['json']['type'], 4)
        self.assertEqual(calls[1].kwargs['json']['handler'], 2)

    async def test_existing_entry_is_not_recreated(self):
        activity = self.activity([{'id': '8', 'type': 4, 'handler': 2, 'contexts': [0]}])
        self.assertTrue(await activity.register_entry_point())
        self.assertEqual(activity.bot.http.request.call_count, 1)

    async def test_repairs_existing_entry(self):
        activity = self.activity([{'id': '8', 'type': 4, 'handler': 1, 'contexts': [1]}])
        self.assertTrue(await activity.register_entry_point())
        call = activity.bot.http.request.call_args
        self.assertEqual(call.args[0].method, 'PATCH')
        self.assertTrue(call.args[0].url.endswith('/commands/8'))
        self.assertEqual(call.kwargs['json'], {'handler': 2, 'contexts': [0, 1]})

    async def test_mismatched_application_is_not_modified(self):
        activity = self.activity([])
        activity.bot.application_id = 1
        with self.assertLogs('activity', level='ERROR'):
            self.assertFalse(await activity.register_entry_point())
        activity.bot.http.request.assert_not_called()
