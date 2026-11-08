import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from economy import Economy, ROLES
from activity import Activity


class ProgressionTests(unittest.TestCase):
    def setUp(self):
        self.e = Economy(':memory:')
        self.e.change(1,2,100000,'test')

    def tearDown(self):
        self.e.db.close()

    def test_no_skipping_and_full_progression(self):
        with self.assertRaises(ValueError):
            self.e.purchase(1,2,max(ROLES,key=ROLES.get),'skip-role')
        self.assertEqual(self.e.wallet(1,2)['coins'],100000)
        for role in sorted(ROLES,key=ROLES.get):
            self.e.purchase(1,2,role,'buy-'+role)
            self.assertEqual(self.e.highest_role(1,2),role)
        self.assertIsNone(self.e.next_role(1,2))
        self.assertEqual(self.e.wallet(1,2)['coins'],10000)

    def test_daily_boundary_repeat_and_reset(self):
        t=datetime(2026,11,8,18,59,59,tzinfo=timezone.utc).timestamp()
        self.assertEqual(self.e.daily_reward(1,2,t)['amount'],100)
        self.assertFalse(self.e.daily_reward(1,2,t)['claimed'])
        self.assertEqual(self.e.daily_reward(1,2,t+1)['amount'],200)
        self.assertEqual(self.e.daily_reward(1,2,t+86401)['amount'],300)
        self.assertEqual(self.e.daily_reward(1,2,t+3*86400+1)['amount'],100)
        self.assertEqual(self.e.daily_reward(3,2,t)['amount'],100)

    def test_daily_survives_restart_and_continues_after_day_seven(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,'economy.sqlite3')
            for day in range(10):
                e=Economy(path)
                self.assertEqual(e.daily_reward(1,2,1800000000+86400*day)['amount'],100*(day+1))
                e.db.close()
            e=Economy(path)
            self.assertFalse(e.daily_reward(1,2,1800000000+86400*9)['claimed'])
            self.assertEqual(e.wallet(1,2)['coins'],5500)
            e.db.close()

    def test_cashout_hundredths(self):
        with patch('economy.time.time',return_value=100), patch('economy.secrets.randbelow',return_value=0):
            self.e.crash_start(1,2,1000,'start-001')
        with patch('economy.time.time',return_value=102):
            r=self.e.crash_cashout(1,2,'cashout-001')
        self.assertEqual(r['multiplier'],1.27)
        self.assertEqual(r['payout'],1270)


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_new_role_and_retry_removal(self):
        a=Activity.__new__(Activity)
        a.economy=Economy(':memory:')
        ids=sorted(ROLES,key=ROLES.get)
        old,new=[SimpleNamespace(id=int(r)) for r in ids[:2]]
        unrelated=SimpleNamespace(id=987)
        member=SimpleNamespace(id=2,roles=[old,unrelated],add_roles=AsyncMock(),remove_roles=AsyncMock(side_effect=[ValueError('retry'),None]))
        guild=SimpleNamespace(id=1)
        a.check_role=lambda g,r:new
        for r in ids[:2]:a.economy.grant_role(1,2,r)
        self.assertTrue(await a.deliver(guild,member))
        self.assertEqual(a.economy.db.execute('SELECT sum(delivered) FROM entitlements').fetchone()[0],0)
        member.roles.append(new)
        self.assertFalse(await a.deliver(guild,member))
        member.add_roles.assert_awaited_once_with(new,reason='Фуфлыжник: новая ступень роли')
        self.assertEqual(member.remove_roles.call_args.args,(old,))
        self.assertEqual(a.economy.db.execute('SELECT sum(delivered) FROM entitlements').fetchone()[0],2)
        a.economy.db.close()
