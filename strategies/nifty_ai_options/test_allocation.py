import unittest,time,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from strategies.nifty_ai_options.allocation import calculate,policy,apply,from_quote
class AllocationTests(unittest.TestCase):
 def calc(self,amount=20000,price=2514.2,lot=1,multiplier=1,**kw):
  return calculate(amount,price,lot,multiplier,quote_at=100,now=101,**kw)
 def test_stock_rounds_down(self):
  r=self.calc();self.assertEqual(r['quantity'],7);self.assertEqual(r['estimated_cost_inr'],17599.4);self.assertFalse(r['budget_cap'])
 def test_option_premium_lots(self):
  r=self.calc(30000,100,75,kind='OPTION');self.assertEqual(r['quantity'],300);self.assertEqual(r['basis'],'premium')
 def test_future_not_margin(self):
  r=self.calc(30000,100,25,10,kind='FUTURE');self.assertEqual(r['lots'],1);self.assertIn('not margin',r['basis'])
 def test_exact_decimal_boundary(self):
  self.assertEqual(self.calc(0.3,0.1)['quantity'],3)
 def test_minimum_insufficient(self):
  with self.assertRaisesRegex(ValueError,'insufficient'):self.calc(7499,100,75)
 def test_stale_and_future(self):
  for stamp in (0,106,True,None):
   with self.subTest(stamp=stamp),self.assertRaises(ValueError):calculate(1000,10,1,quote_at=stamp,now=100)
 def test_invalid_numeric(self):
  for value in (True,-1,0,float('nan'),float('inf'),None):
   with self.subTest(value=value),self.assertRaises(ValueError):self.calc(value)
 def test_no_unverified_fx(self):
  with self.assertRaisesRegex(ValueError,'conversion'):self.calc(currency='USD')
 def test_modes_exclusive(self):
  self.assertEqual(policy(dict(entry_amount_inr=20000,lots=30)),dict(entry_quantity_mode='QUANTITY'))
  self.assertEqual(policy(dict(entry_quantity_mode='AMOUNT_INR',entry_amount_inr=20000,lots=999))['entry_amount_inr'],20000)
 def test_delta_amount_refused(self):
  with self.assertRaises(ValueError):policy(dict(entry_quantity_mode='AMOUNT_INR',entry_amount_inr=20000,broker='DELTA_INDIA'))
 def executor(self):
  e=SimpleNamespace(runner_config=dict(entry_quantity_mode='AMOUNT_INR',entry_amount_inr=1000,broker='FYERS'),runner_data=Path('/missing'),state={},lots=99,master=lambda s:dict(lot_size=1,product_type='STOCK'),save=Mock())
  return e
 def test_entry_reprices_and_ignores_old_quantity(self):
  e=self.executor();a=dict(action='OPEN_LONG',position=dict(symbol='NSE:ABC-EQ'))
  apply(e,a,({'timestamp':time.time(),'ltp':100},));self.assertEqual(e.lots,10)
  apply(e,a,({'timestamp':time.time(),'ltp':110},));self.assertEqual(e.lots,9)
  self.assertEqual(e.state['entry_allocation']['quantity'],9)
 def test_exit_never_resizes(self):
  e=self.executor();apply(e,dict(action='CLOSE_LONG'),());self.assertEqual(e.lots,99);e.save.assert_not_called()
 def test_quantity_mode_unaffected(self):
  e=self.executor();e.runner_config['entry_quantity_mode']='QUANTITY';apply(e,dict(action='OPEN_LONG'),());self.assertEqual(e.lots,99);e.save.assert_not_called()
 def test_pending_no_reprice(self):
  e=self.executor();e.state['pending']={'id':'uncertain'}
  with self.assertRaisesRegex(ValueError,'Uncertain'):apply(e,dict(action='OPEN_LONG'),())
 def test_unknown_mcx_multiplier_blocked(self):
  with self.assertRaisesRegex(ValueError,'multiplier'):from_quote(dict(entry_amount_inr=10000),'MCX:ABC',dict(lot_size=1),dict(ltp=10,timestamp=time.time()),'/missing')
if __name__=='__main__':unittest.main()

class ExecutionAllocationTests(unittest.TestCase):
 def test_real_paper_executor_entry_and_exit_quantity(self):
  from strategies.nifty_ai_options.direct_execution import DirectExecution
  from strategies.nifty_ai_options.multi_runner import configure_executor
  from pathlib import Path
  with tempfile.TemporaryDirectory() as folder:
   api=Mock();e=DirectExecution(api,'account',folder,lots=99,product='INTRADAY',master=lambda s:dict(symbol=s,product_type='STOCK',lot_size=1,tick_size=.05))
   self.addCleanup(e.close)
   configure_executor(e,dict(account='account',broker='FYERS',underlying='NSE:ABC-EQ',entry_quantity_mode='AMOUNT_INR',entry_amount_inr=20000),Path(folder))
   p=dict(symbol='NSE:ABC-EQ',underlying='NSE:ABC-EQ',execution_route='DIRECT',side='LONG',entry_timestamp=time.time(),spot_brick=1)
   stamp=time.time();opened=e.submit(dict(action='OPEN_LONG',timestamp=stamp,position=p),dict(timestamp=stamp,ltp=2500),now=stamp)
   self.assertEqual(opened['payload']['qty'],8)
   e.runner_config['entry_amount_inr']=1
   stamp=time.time();closed=e.submit(dict(action='CLOSE_LONG',timestamp=stamp,position=p),dict(timestamp=stamp,ltp=2600),now=stamp)
   self.assertEqual(closed['payload']['qty'],8);api.place_order.assert_not_called()
