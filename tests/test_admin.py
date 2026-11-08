import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from aiohttp import web
from activity import Activity, ADMIN_IDS
from economy import Economy


class AdminEconomyTests(unittest.TestCase):
    def setUp(self):
        self.e = Economy(':memory:')

    def tearDown(self):
        self.e.db.close()

    def adjust(self, operation, amount, key='request-0001'):
        return self.e.admin_adjust('guild','actor','target',operation,amount,'Test reason',key)

    def test_add_retry_and_audit(self):
        self.adjust('add',100)
        self.adjust('add',100)
        self.assertEqual(self.e.wallet('guild','target')['coins'],100)
        self.assertEqual(self.e.db.execute('SELECT count(*) FROM admin_audit').fetchone()[0],1)
        self.assertEqual(self.e.wallet('other','target')['coins'],0)

    def test_set_and_remove(self):
        self.adjust('set',100)
        self.adjust('remove',30,'request-0002')
        self.assertEqual(self.e.wallet('guild','target')['coins'],70)
        self.adjust('set',0,'request-0003')
        self.assertEqual(self.e.wallet('guild','target')['coins'],0)

    def test_invalid_values_do_not_change_balance(self):
        for amount in [-1,1.5,True,1000000001]:
            with self.assertRaises(ValueError): self.adjust('add',amount)
        with self.assertRaises(ValueError): self.adjust('remove',100)
        self.assertEqual(self.e.db.execute('SELECT count(*) FROM admin_audit').fetchone()[0],0)


class AdminAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_ordinary_member_cannot_access_admin_endpoint(self):
        a=Activity.__new__(Activity)
        a.identity=AsyncMock(return_value=(SimpleNamespace(id=1),SimpleNamespace(id=123)))
        request=SimpleNamespace(json=AsyncMock())
        with self.assertRaises(web.HTTPForbidden): await a.admin(request)
        request.json.assert_not_called()

    async def test_configured_ids_only(self):
        self.assertEqual(ADMIN_IDS,{1542513699539918979,933727248039698443})

    async def test_admin_can_credit_member_of_current_guild(self):
        import asyncio, json
        from collections import defaultdict
        a=Activity.__new__(Activity)
        a.economy=Economy(':memory:')
        a.locks=defaultdict(asyncio.Lock)
        member=SimpleNamespace(id=123456789012345678,bot=False,display_name='Test')
        guild=SimpleNamespace(id=99,fetch_member=AsyncMock(return_value=member))
        actor=SimpleNamespace(id=1542513699539918979)
        a.identity=AsyncMock(return_value=(guild,actor))
        request=SimpleNamespace(json=AsyncMock(return_value={'target':str(member.id),'operation':'add','amount':500,'reason':'Reward','key':'request-12345'}))
        try:
            response=await a.admin(request)
            self.assertEqual(json.loads(response.text)['balance'],500)
            self.assertEqual(a.economy.wallet(99,member.id)['coins'],500)
            self.assertEqual(a.economy.wallet(100,member.id)['coins'],0)
        finally:
            a.economy.db.close()
