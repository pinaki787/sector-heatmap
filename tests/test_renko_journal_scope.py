import unittest
from strategies.renko_supertrend.journal_scope import journal_scope
class JournalScopeTests(unittest.TestCase):
 def setUp(self):
  self.rows=[dict(broker='DELTA_INDIA',instance_key='eth',instrument='ETHUSD',trade_history=[dict(trade_id='a',mode='LIVE',entry_time=10)]),
             dict(broker='DELTA_INDIA',instance_key='btc',instrument='BTCUSD',trade_history=[dict(trade_id='b',mode='PAPER',entry_time=5)]),
             dict(broker='FYERS',instance_key='other',trade_history=[dict(trade_id='c',mode='LIVE')])]
 def test_all_stays_in_broker_account_registry(self):
  result=journal_scope(self.rows,'DELTA_INDIA')
  self.assertEqual([r['trade_id'] for r in result['trades']],['b','a'])
  self.assertEqual([r['instance_key'] for r in result['trades']],['btc','eth'])
 def test_selected_and_mode_filter(self):
  self.assertEqual(len(journal_scope(self.rows,'DELTA_INDIA','eth','LIVE')['trades']),1)
  self.assertEqual(journal_scope(self.rows,'DELTA_INDIA','eth','PAPER')['trades'],[])
 def test_unknown_instance_or_mode_cannot_expand_scope(self):
  for instance,mode in [('other','ALL'),('all','INVALID')]:
   with self.assertRaises(ValueError):journal_scope(self.rows,'DELTA_INDIA',instance,mode)
