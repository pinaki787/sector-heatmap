import unittest,tempfile,json,time
from pathlib import Path
from runtime_control import enqueue,RuntimeControl
class RenkoExitModeControlTests(unittest.TestCase):
 def config(self):
  return dict(account='a'*32,broker='FYERS',runtime_session='scope',underlying='EXACT',timeframe=1,calculation_mode='HYBRID',supertrend_basis='COMPLETED_RENKO',display_mode='CANDLES')
 def test_chart_mode_ack_updates_exit_policy_without_rebuilding_geometry(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.config();calls=[];engine={}
   payload=dict(account_id=c['account'],broker=c['broker'],run_id=Path(d).name,runtime_session=c['runtime_session'],underlying='EXACT',timeframe=1,display_mode='RENKO')
   command=enqueue(d,c,payload)
   control=RuntimeControl(c,d,apply=lambda frame:calls.append(frame),apply_mode=lambda mode:engine.update(mode=mode))
   control.poll(busy=True,position=True)
   self.assertEqual(c['display_mode'],'CANDLES')
   control.poll(busy=False,position=True)
   self.assertEqual(c['exit_confirmation_mode'],'RENKO_BRICKS_ONLY');self.assertEqual(engine['mode'],'RENKO')
   self.assertEqual(calls,[])
   self.assertEqual(json.loads((Path(d)/'reconfigure.json').read_text())['phase'],'APPLIED')
 def test_legacy_candle_worker_cannot_claim_brick_exit_capability(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.config();c['supertrend_basis']='BROKER_CANDLES'
   p=dict(account_id=c['account'],broker=c['broker'],run_id=Path(d).name,runtime_session='scope',underlying='EXACT',timeframe=1,display_mode='RENKO')
   with self.assertRaisesRegex(ValueError,'Restart'):enqueue(d,c,p)
if __name__=='__main__':unittest.main()
