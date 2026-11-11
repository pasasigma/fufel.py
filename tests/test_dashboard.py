import asyncio
import json
import os
import time
import unittest
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from dashboard import Dashboard, DEFAULTS, password_hash, password_matches, digest
from economy import Economy
from moderation import RoleModeration, BANNED_ROLE_ID


class DashboardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env=patch.dict(os.environ,{'DASHBOARD_BRIDGE_KEY':'x'*40,'DASHBOARD_USERS_JSON':''})
        self.env.start()
        self.e=Economy(':memory:')
        self.guild=SimpleNamespace(id=1544006188927156244,owner_id=933727248039698443,fetch_member=AsyncMock())
        bot=SimpleNamespace(get_guild=lambda _:self.guild,is_ready=lambda:True)
        self.a=SimpleNamespace(economy=self.e,bot=bot,locks=defaultdict(asyncio.Lock))
        self.d=Dashboard(self.a)
        self.password='correct-password-123'
        self.e.db.execute('INSERT INTO dash_users VALUES (?,?,?,?,?,1)',('tech',password_hash(self.password),'tech','1542513699539918979',json.dumps(sorted(DEFAULTS['tech']))))
        app=web.Application(client_max_size=8192)
        self.d.routes(app)
        self.client=TestClient(TestServer(app));await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close();self.e.db.close();self.env.stop()

    async def login(self):
        response=await self.client.post('/dashboard-api/login',json={'login':'tech','password':self.password},headers={'X-Dashboard-Key':'x'*40})
        data=await response.json()
        return {'X-Dashboard-Key':'x'*40,'Cookie':'__Host-dashboard='+response.cookies['__Host-dashboard'].value,'X-CSRF-Token':data['csrf']}

    async def test_bridge_required(self):
        response=await self.client.get('/dashboard-api/me')
        self.assertEqual(response.status,403)

    async def test_session_secure_csrf_and_logout(self):
        headers=await self.login()
        response=await self.client.get('/dashboard-api/me',headers=headers)
        self.assertEqual(response.status,200)
        self.assertNotIn('password',(await response.json())['user'])
        without={k:v for k,v in headers.items() if k!='X-CSRF-Token'}
        response=await self.client.post('/dashboard-api/logout',json={},headers=without)
        self.assertEqual(response.status,403)
        response=await self.client.post('/dashboard-api/logout',json={},headers=headers)
        self.assertEqual(response.status,200)
        response=await self.client.get('/dashboard-api/me',headers=headers)
        self.assertEqual(response.status,401)

    async def test_wrong_password_and_rate_limit(self):
        for i in range(11):
            response=await self.client.post('/dashboard-api/login',json={'login':'missing','password':'wrong-password-long'},headers={'X-Dashboard-Key':'x'*40})
            self.assertEqual(response.status,429 if i==10 else 401)

    async def test_expired_and_disabled_session(self):
        headers=await self.login()
        self.e.db.execute("UPDATE dash_users SET enabled=0 WHERE login='tech'")
        response=await self.client.get('/dashboard-api/me',headers=headers)
        self.assertEqual(response.status,401)

    async def test_permissions_enforced_without_ui(self):
        self.e.db.execute("UPDATE dash_users SET role='support',permissions=?",(json.dumps(sorted(DEFAULTS['support'])),))
        headers=await self.login()
        response=await self.client.post('/dashboard-api/action',json={'action':'coins','target':'123456789012345678','amount':10000,'operation':'add','reason':'test','key':'test-000001'},headers=headers)
        self.assertEqual(response.status,403)
        self.guild.fetch_member.assert_not_awaited()

    async def test_balance_idempotent_and_audited(self):
        self.guild.fetch_member.return_value=SimpleNamespace(id=123456789012345678,bot=False)
        headers=await self.login()
        body={'action':'coins','target':'123456789012345678','amount':1000,'operation':'add','reason':'test','key':'test-000001'}
        for _ in range(2):
            response=await self.client.post('/dashboard-api/action',json=body,headers=headers)
            self.assertEqual(response.status,200,await response.text())
        self.assertEqual(self.e.wallet(self.guild.id,123456789012345678)['coins'],1000)
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM dash_audit WHERE action='coins'").fetchone()[0],1)

    async def test_message_exact_text_once(self):
        target=SimpleNamespace(id=123456789012345678,send=AsyncMock(return_value=SimpleNamespace(id=99)))
        self.guild.fetch_member.return_value=target
        headers=await self.login()
        body={'action':'send_dm','target':str(target.id),'text':'Привет\n**Текст** @everyone','reason':'test','key':'send-000001'}
        for _ in range(2):
            response=await self.client.post('/dashboard-api/action',json=body,headers=headers)
            self.assertEqual(response.status,200,await response.text())
        target.send.assert_awaited_once()
        self.assertEqual(target.send.call_args.args[0],body['text'])
        self.assertFalse(target.send.call_args.kwargs['allowed_mentions'].everyone)

    async def test_tech_cannot_be_replaced(self):
        user=dict(self.e.db.execute("SELECT * FROM dash_users WHERE login='tech'").fetchone())
        with self.assertRaises(ValueError):await self.d.account(user,{'login':'tech','role':'support'})

    def test_password_hash(self):
        hashed=password_hash(self.password)
        self.assertNotIn(self.password,hashed)
        self.assertTrue(password_matches(self.password,hashed))
        self.assertFalse(password_matches('different-password',hashed))


class Role:
    def __init__(self,id,position,managed=False):self.id,self.position,self.managed=id,position,managed
    def is_default(self):return self.id==0
    def __ge__(self,other):return self.position>=other.position


class RestoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.e=Economy(':memory:')
        self.default=Role(0,0);self.old=Role(10,2);self.ban=Role(BANNED_ROLE_ID,3);self.managed=Role(20,1,True)
        self.roles={r.id:r for r in [self.default,self.old,self.ban,self.managed]}
        self.guild=SimpleNamespace(id=1,owner_id=100,get_role=self.roles.get,me=SimpleNamespace(guild_permissions=SimpleNamespace(manage_roles=True),top_role=Role(99,10)))
        self.member=SimpleNamespace(id=2,bot=False,top_role=self.old,roles=[self.default,self.old,self.managed])
        async def edit(**kwargs):
            self.member.roles=[self.default]+kwargs['roles']
            self.member.top_role=max(self.member.roles,key=lambda r:r.position)
        self.member.edit=AsyncMock(side_effect=edit)
        self.m=RoleModeration(self.e.db,defaultdict(asyncio.Lock))

    async def asyncTearDown(self):self.e.db.close()

    async def test_ban_restart_unban_restores_roles(self):
        await self.m.ban(self.guild,self.member,'test')
        self.assertNotIn(self.old,self.member.roles)
        self.m=RoleModeration(self.e.db,defaultdict(asyncio.Lock))
        await self.m.unban(self.guild,self.member,'test')
        self.assertIn(self.old,self.member.roles)
        self.assertIn(self.managed,self.member.roles)
        self.assertNotIn(self.ban,self.member.roles)

    async def test_repeated_ban_preserves_snapshot(self):
        await self.m.ban(self.guild,self.member,'test');await self.m.ban(self.guild,self.member,'test')
        await self.m.unban(self.guild,self.member,'test')
        self.assertIn(self.old,self.member.roles)

    async def test_unassignable_role_retained_for_retry(self):
        await self.m.ban(self.guild,self.member,'test');self.old.position=12
        result=await self.m.unban(self.guild,self.member,'test')
        self.assertEqual(result['blocked'],[10])
        self.old.position=2
        result=await self.m.unban(self.guild,self.member,'test')
        self.assertEqual(result['restored'],1)

    async def test_failed_ban_does_not_lose_snapshot(self):
        self.member.edit.side_effect=RuntimeError('offline')
        with self.assertRaises(RuntimeError):await self.m.ban(self.guild,self.member,'test')
        self.assertEqual(json.loads(self.e.db.execute('SELECT roles FROM role_bans').fetchone()[0]),[10])

    async def test_old_ban_without_snapshot(self):
        self.member.roles=[self.default,self.ban]
        result=await self.m.unban(self.guild,self.member,'test')
        self.assertIn('отсутствует',result['message'])
        self.assertNotIn(self.ban,self.member.roles)
