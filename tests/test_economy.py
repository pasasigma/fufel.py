import unittest
from unittest.mock import patch
from economy import Economy, PRIZES, ROLES, crash_multiplier


class EconomyTests(unittest.TestCase):
    def setUp(self):
        self.e = Economy(':memory:')
        with self.e.transaction():
            self.e.change('g','u',100000,'test')

    def tearDown(self):
        self.e.db.close()

    def test_message_and_voice(self):
        self.assertTrue(self.e.message_reward('g','u',100))
        self.assertFalse(self.e.message_reward('g','u',110))
        self.e.voice_reward('g','u',2)
        self.assertEqual(self.e.wallet('g','u')['coins'],100011)

    def test_prize_intervals(self):
        self.assertEqual(sum(p[2] for p in PRIZES),10000)
        start=0
        for i,(kind,value,weight) in enumerate(PRIZES):
            with patch('economy.secrets.randbelow',return_value=start):
                self.e.change('g',f'prize-{i}',1000,'test')
                r=self.e.roulette('g',f'prize-{i}',f'spin-key-{i}')
            self.assertEqual((r['kind'],r['value']),(kind,value))
            self.assertEqual(r['prize_index'],i)
            start+=weight

    def test_retry_purchase(self):
        role=min(ROLES,key=ROLES.get)
        self.e.purchase('g','u',role,'purchase-key')
        self.e.purchase('g','u',role,'purchase-key')
        self.assertEqual(self.e.wallet('g','u')['coins'],95000)
        with self.assertRaises(ValueError):
            self.e.purchase('g','u',role,'another-key')

    def test_insufficient_balance_rolls_back(self):
        with self.assertRaises(ValueError):
            self.e.roulette('g','empty','request-key')
        self.assertEqual(self.e.wallet('g','empty')['coins'],0)

    def test_crash_cashout_once(self):
        with patch('economy.secrets.randbelow',return_value=10000), patch('economy.time.time',return_value=100):
            self.e.crash_start('g','u',1000,'start-key')
        with patch('economy.time.time',return_value=105):
            result=self.e.crash_cashout('g','u','cashout-key')
            again=self.e.crash_cashout('g','u','cashout-key')
            self.assertEqual(result,again)
        with patch('economy.time.time',return_value=10000):
            self.assertEqual(self.e.crash_status('g','u')['multiplier'],result['multiplier'])
        self.assertEqual(self.e.wallet('g','u')['coins'],99000+result['payout'])

    def test_crash_after_end(self):
        with patch('economy.secrets.randbelow',return_value=999999):
            self.e.crash_start('g','u',1000,'start-key')
        self.assertIn('error',self.e.crash_cashout('g','u','cashout-key'))
        self.assertEqual(self.e.wallet('g','u')['coins'],99000)

    def test_crash_distribution_and_limit(self):
        values=[crash_multiplier(i) for i in range(0,1000000,10)]
        self.assertTrue(all(1 <= v <= 10 for v in values))
        self.assertAlmostEqual(sum(values)/len(values),1.918,delta=.01)
        self.assertEqual(crash_multiplier(0),10)
        self.assertEqual(crash_multiplier(999999),1)

    def test_role_compensation_keeps_wheel_sector(self):
        role=next(iter(ROLES))
        self.e.grant_role('g','u',role)
        with patch('economy.secrets.randbelow',return_value=0):
            result=self.e.roulette('g','u','duplicate-role')
        self.assertEqual(result['kind'],'coins')
        self.assertEqual(result['value'],35000)
        self.assertEqual(result['prize_index'],0)

    def test_guild_isolation(self):
        self.assertEqual(self.e.wallet('other','u')['coins'],0)


if __name__=='__main__':
    unittest.main()
