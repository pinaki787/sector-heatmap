import copy,json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from strategies.nifty_ai_options.fyers_external_exit import evidence
from strategies.nifty_ai_options.option_legs import OptionLegBook
NOW=1795759000
OWN=dict(symbol='NSE:NIFTY26D0125350PE',quantity=65,side='PE',order_id='entry',fill_price=38.55,entry_timestamp=1795757331)
ENTRY=dict(id='entry',symbol=OWN['symbol'],qty=65,filledQty=65,side=1,status=2,productType='INTRADAY',tradedPrice=38.55,orderDateTime='27-Nov-2026 10:58:53')
EXIT=dict(ENTRY,id='manual-exit',side=-1,tradedPrice=42.5,orderDateTime='27-Nov-2026 11:02:14')
class ExternalExitTests(unittest.TestCase):
 def check(self,positions=None,orders=None,owned=None):
  return evidence(owned or OWN,'INTRADAY',positions if positions is not None else [dict(symbol=OWN['symbol'],productType='INTRADAY',netQty=0)],orders if orders is not None else [ENTRY,EXIT],now=NOW)
 def test_exact_manual_close_proven(self):
  r=self.check();self.assertEqual(r['exit_order'],'manual-exit');self.assertEqual(r['quantity'],65);self.assertEqual(r['fill_price'],42.5);self.assertEqual(r['orders_submitted'],0)
 def test_existing_exposure_not_cleared(self):
  self.assertIsNone(self.check(positions=[dict(symbol=OWN['symbol'],productType='INTRADAY',netQty=65)]))
 def test_partial_and_missing_inventory_retained(self):
  for pos in ([],[dict(symbol=OWN['symbol'],productType='INTRADAY',netQty=5)]):
   with self.assertRaises(ValueError):self.check(positions=pos)
 def test_pending_or_unknown_exit_retained(self):
  for row in (dict(EXIT,status=6),dict(EXIT,status=3),dict(EXIT,filledQty=20),dict(EXIT,side=1)):
   with self.subTest(row=row),self.assertRaises(ValueError):self.check(orders=[ENTRY,row])
 def test_wrong_contract_product_entry_or_price_retained(self):
  for row in (dict(EXIT,symbol='NSE:OTHER'),dict(EXIT,productType='MARGIN'),dict(EXIT,tradedPrice=0)):
   with self.assertRaises(ValueError):self.check(orders=[ENTRY,row])
  with self.assertRaises(ValueError):self.check(owned=dict(OWN,order_id='wrong'))
 def test_multiple_complete_closes_have_exact_weighted_price(self):
  a=dict(EXIT,id='a',qty=30,filledQty=30,tradedPrice=40)
  b=dict(EXIT,id='b',qty=35,filledQty=35,tradedPrice=42)
  r=self.check(orders=[ENTRY,a,b]);self.assertAlmostEqual(r['fill_price'],(30*40+35*42)/65)
 def test_duplicate_orders_rejected(self):
  with self.assertRaises(ValueError):self.check(orders=[ENTRY,EXIT,EXIT])
 def test_new_entry_after_exit_cannot_be_misattributed(self):
  with self.assertRaises(ValueError):self.check(orders=[ENTRY,EXIT,dict(ENTRY,id='new',orderDateTime='27-Nov-2026 11:03:00')])
 def test_stop_cleans_retired_external_leg_without_quote_or_order(self):
  with tempfile.TemporaryDirectory() as d:
   directory=Path(d)/'runs'/'run';directory.mkdir(parents=True)
   original=Mock();api=Mock();proof=self.check()
   base=SimpleNamespace(state=dict(position=copy.deepcopy(OWN),pending=None,seen=[]),save=original,close=Mock(),live=True,reconcile_external_close=Mock(return_value=proof),submit=api)
   book=OptionLegBook(base,directory,dict(account='owner',execution_route='OPTIONS',execution_mode='LIVE'),quote=Mock(side_effect=AssertionError('No quote required')),clock=lambda:NOW)
   result=book.stop_all('stop',force=True)
   self.assertTrue(result['flat']);self.assertFalse(book.state['closing_legs']);api.assert_not_called()
   events=[json.loads(s) for s in (directory/'events.jsonl').read_text().splitlines()]
   self.assertEqual(len(events),1);self.assertEqual(events[0]['result']['order_id'],'manual-exit');self.assertTrue(events[0]['result']['external_exit'])
   book.stop_all('stop',force=True)
   self.assertEqual(len((directory/'events.jsonl').read_text().splitlines()),1)
 def test_pending_intent_is_never_external_cleared(self):
  with tempfile.TemporaryDirectory() as d:
   base=SimpleNamespace(state=dict(position=None,pending=None,seen=[],closing_legs={'x':dict(position=copy.deepcopy(OWN),pending={'uncertain':True},origin=str(Path(d)/'run'),exit_intent=dict(action='SELL',position=copy.deepcopy(OWN)),delivered=[])}),save=Mock(),close=Mock(),live=True,reconcile_external_close=Mock(),reconcile_pending=Mock(side_effect=ValueError('Unknown order')))
   book=OptionLegBook(base,Path(d)/'run',dict(execution_mode='LIVE'),quote=Mock(),clock=lambda:NOW)
   book.poll(force=True);self.assertTrue(book.state['closing_legs']['x']['pending']);base.reconcile_external_close.assert_not_called()

class TradeEvidenceTests(unittest.TestCase):
 def test_tradebook_must_match_full_exit(self):
  from strategies.nifty_ai_options.fyers_external_exit import trades
  proof=ExternalExitTests().check()
  row=dict(symbol=OWN['symbol'],productType='INTRADAY',orderNumber='manual-exit',tradeNumber='fill1',tradedQty=65,tradePrice=42.5,side=-1,orderDateTime=EXIT['orderDateTime'])
  self.assertEqual(trades(proof,[row])['broker_trade_at'],proof['broker_order_at'])
  for rows in ([],[row,row],[dict(row,tradedQty=64)],[dict(row,tradePrice=43)],[dict(row,side=1)]):
   with self.subTest(rows=rows),self.assertRaises(ValueError):trades(proof,rows)

class StopReceiptTests(unittest.TestCase):
 def test_success_clears_historical_failure_message(self):
  from strategies.nifty_ai_options.position_control import PositionManager
  with tempfile.TemporaryDirectory() as d:
   manager=object.__new__(PositionManager);manager.directory=Path(d);manager.clock=lambda:NOW
   manager.request=dict(request_id='a'*32,error='old failure',retained_position=OWN,phase='RECOVERY_REQUIRED',notice='still closing')
   manager.update('STOPPED',broker_flat_confirmed=True)
   self.assertIsNone(manager.request['error']);self.assertIsNone(manager.request['retained_position']);self.assertEqual(manager.request['notice'],'Stopped · broker exposure reconciled')
