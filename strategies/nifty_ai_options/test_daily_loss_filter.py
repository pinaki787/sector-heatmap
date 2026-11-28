import tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from strategies.nifty_ai_options.daily_loss_filter import evaluate,optional_amount
from strategies.nifty_ai_options.position_control import entry_guard,EntryBlocked
class DailyLossTests(unittest.TestCase):
 def setUp(self):
  self.now=time.time();self.c=dict(account='a'*32,broker='DELTA_INDIA',execution_mode='LIVE',daily_max_loss=10)
 def row(self,profit=-10,**kw):
  return dict(account=self.c['account'],broker='DELTA_INDIA',mode='LIVE',status='CLOSED',exit_time=self.now,side='LONG',quantity=1,multiplier=1,entry_premium=100,exit_premium=100+profit,currency='USD',**kw)
 def test_default_off_does_not_require_evidence(self):
  self.assertFalse(evaluate(dict(daily_max_loss=None),None)['blocked'])
 def test_exact_limit_blocks_and_preserves_exit_policy(self):
  r=evaluate(self.c,[self.row()],now=self.now)
  self.assertTrue(r['blocked']);self.assertTrue(r['exits_continue']);self.assertFalse(r['fees_included'])
 def test_daily_account_strategy_combines_symbols_and_runs(self):
  self.assertTrue(evaluate(self.c,[self.row(-6,underlying='BTCUSD'),self.row(-4,underlying='PAXGUSD')],now=self.now)['blocked'])
 def test_other_account_broker_paper_and_old_day_excluded(self):
  rows=[]
  for key,val in [('account','b'*32),('broker','FYERS'),('mode','PAPER'),('status','OPEN'),('exit_time',self.now-86400)]:
   r=self.row(-100);r[key]=val;rows.append(r)
  self.assertFalse(evaluate(self.c,rows,now=self.now)['blocked'])
 def test_unknown_multiplier_blocks(self):
  r=self.row();r['multiplier']=None
  self.assertEqual(evaluate(self.c,[r],now=self.now)['reason'],'DAILY_LOSS_EVIDENCE_UNAVAILABLE')
 def test_latch_does_not_rearm_after_profit_or_restart(self):
  self.assertTrue(evaluate(self.c,[self.row(100)],now=self.now,latched=True)['blocked'])
 def test_positive_finite_optional_value(self):
  for v in [True,0,-1,float('nan'),float('inf'),'10']:
   with self.assertRaises(ValueError):optional_amount(v)
 def test_disabled_admission_has_no_journal_work(self):
  with tempfile.TemporaryDirectory() as p:
   executor=SimpleNamespace(state={},runner_config={})
   with entry_guard(Path(p),executor):pass
if __name__=='__main__':unittest.main()
