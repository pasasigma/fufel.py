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

    async def test_guild_registration_removes_only_known_global_duplicates(self):
        a=Activity.__new__(Activity)
        a.commands_registered=False
        a.command_guilds=set()
        async def api(route, **kwargs):
            if route.method == 'GET':
                return [{'id':'1','type':1,'name':'daily'}, {'id':'2','type':4,'name':'launch'}, {'id':'3','type':1,'name':'other'}]
            return {}
        request=AsyncMock(side_effect=api)
        a.bot=SimpleNamespace(application_id=int(CLIENT_ID),http=SimpleNamespace(request=request),tree=fufel.bot.tree,guilds=[SimpleNamespace(id=42)])
        await a.register_commands()
        count=len(fufel.bot.tree.get_commands())
        self.assertEqual(request.call_count,count+2)
        posts=[c for c in request.call_args_list if c.args[0].method=='POST']
        self.assertTrue(all('/guilds/42/' in c.args[0].url for c in posts))
        deletes=[c for c in request.call_args_list if c.args[0].method=='DELETE']
        self.assertEqual(len(deletes),1)
        self.assertTrue(deletes[0].args[0].url.endswith('/commands/1'))
        await a.register_commands()
        self.assertEqual(request.call_count,count+2)
        a.bot.guilds.append(SimpleNamespace(id=43))
        await a.register_commands()
        self.assertEqual(request.call_count,count*2+2)

if __name__=='__main__':unittest.main()
