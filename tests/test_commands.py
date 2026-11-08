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

    async def test_global_and_guild_commands_registered_once(self):
        a=Activity.__new__(Activity)
        a.commands_registered=False
        a.command_guilds=set()
        request=AsyncMock(return_value={})
        a.bot=SimpleNamespace(application_id=int(CLIENT_ID),http=SimpleNamespace(request=request),tree=fufel.bot.tree,guilds=[SimpleNamespace(id=42)])
        await a.register_commands()
        count=len(fufel.bot.tree.get_commands())
        self.assertEqual(request.call_count,count*2)
        self.assertEqual(a.command_guilds,{42})
        self.assertTrue(all(c.args[0].method=='POST' for c in request.call_args_list))
        self.assertTrue(all('/guilds/42/' in c.args[0].url for c in request.call_args_list[count:]))
        self.assertTrue(all('contexts' not in c.kwargs['json'] for c in request.call_args_list[count:]))
        await a.register_commands()
        self.assertEqual(request.call_count,count*2)
        a.bot.guilds.append(SimpleNamespace(id=43))
        await a.register_commands()
        self.assertEqual(request.call_count,count*3)

if __name__=='__main__':unittest.main()
