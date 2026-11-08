import os,unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
os.environ['ECONOMY_DB']=':memory:'
import fufel
from activity import Activity,CLIENT_ID

class CommandTests(unittest.IsolatedAsyncioTestCase):
    def test_commands_have_options_and_no_prefix(self):
        commands={c.name:c.to_dict(fufel.bot.tree) for c in fufel.bot.tree.get_commands()}
        self.assertTrue({'time','untime','ban','unban','backup','troll','untroll','daily','app'}.issubset(commands))
        self.assertEqual(fufel.bot.command_prefix,[])
        self.assertEqual(commands['time']['options'][0]['type'],6)
        self.assertFalse(commands['daily']['dm_permission'])

    async def test_app_launches_without_voice(self):
        interaction=SimpleNamespace(response=SimpleNamespace(launch_activity=AsyncMock()))
        await fufel.cmd_app.callback(interaction)
        interaction.response.launch_activity.assert_awaited_once()

    async def test_upsert_keeps_primary_entry(self):
        a=Activity.__new__(Activity)
        a.commands_registered=False
        request=AsyncMock(side_effect=[[{'id':'9','type':4,'handler':2,'contexts':[0]}]]+[{}]*len(fufel.bot.tree.get_commands()))
        a.bot=SimpleNamespace(application_id=int(CLIENT_ID),http=SimpleNamespace(request=request),tree=fufel.bot.tree)
        self.assertTrue(await a.register_entry_point())
        self.assertTrue(a.commands_registered)
        self.assertTrue(all(c.args[0].method=='POST' for c in request.call_args_list[1:]))

if __name__=='__main__':unittest.main()
