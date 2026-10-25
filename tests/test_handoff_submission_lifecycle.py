import unittest,tempfile,json
from pathlib import Path
from datetime import datetime,timedelta,timezone
from copy import deepcopy
from unittest.mock import patch
from sector_heatmap.fyers_execution import FyersExecutionService,DailyRiskLedger
class Broker:
 def __init__(self,reason='This instrument is allowed only for intraday trading.'):self.orders=[];self.calls=[];self.reason=reason;self.timeout=False
 def place_order(self,data):
  self.calls.append(deepcopy(data))
  if self.timeout:raise TimeoutError()
  ident=str(len(self.calls));status=5 if len(self.calls)==1 else 6
  self.orders.append(dict(data,id=ident,status=status,filledQty=0,remainingQuantity=0 if status==5 else data['qty'],message=self.reason,tradedPrice=0));return dict(s='ok',id=ident)
 def orderbook(self):return dict(s='ok',orderBook=deepcopy(self.orders))
 def positions(self):return dict(s='ok',netPositions=[])
class Service(FyersExecutionService):
 def _preflight(self,payload,read_client=None,reviewed=None):
  return dict(broker='FYERS',underlying='NSE:T-EQ',direction='BULLISH',instrument=dict(kind='EQUITY',contracts=[dict(symbol='NSE:T-EQ',action='BUY',quantity=10,limit_price=100,tick_size=.05)],worst_case_risk=100),order_policy=dict(product_type='INTRADAY' if payload.get('handoff_product_attempt')==2 else 'CNC'),protection=dict(stop_loss_price=90,target_price=110),submission_eligible=True,expires_at=(self.now()+timedelta(seconds=120)).isoformat(),entry_order=dict(type=4,stopPrice=100) if payload.get('execution_entry_order',{}).get('type')=='STOP_LIMIT' else dict(type=1,stopPrice=0))
class SubmissionLifecycleTests(unittest.TestCase):
 def make(self,b):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.halts=[]
  return Service(ledger=DailyRiskLedger(Path(tmp.name)/'risk.json'),now=lambda:datetime.now(timezone.utc),live_gate=lambda:True,execution_halt=lambda *a:self.halts.append(a))
 @patch('sector_heatmap.handoff_broker_read.read',return_value={'daily_loss':0})
 def test_one_verified_product_correction_preserves_order_and_audit(self,_):
  b=Broker();s=self.make(b);p=s.prepare(dict(handoff_auto=True));original=p['preview_id']
  with patch('sector_heatmap.fyers_execution._current_client',return_value=b):r=s.submit(original,p['confirmation_phrase'])
  self.assertEqual([x['productType'] for x in b.calls],['CNC','INTRADAY']);self.assertEqual([x['type'] for x in b.calls],[1,1]);self.assertEqual([x['limitPrice'] for x in b.calls],[100,100]);self.assertEqual([x['stopLoss'] for x in b.calls],[10,10]);self.assertEqual(r['actual_product'],'INTRADAY');self.assertEqual(len(r['product_attempts']),2);self.assertEqual(self.halts,[])
  with self.assertRaises(ValueError):s.submit(original,p['confirmation_phrase'])
  self.assertEqual(len(b.calls),2)
  saved=json.loads((s.ledger.path.parent/'entry-evidence'/(original+'-result.json')).read_text())['result'];self.assertEqual(saved['order_ids'],['2'])
 @patch('sector_heatmap.handoff_broker_read.read',return_value={'daily_loss':0})
 def test_stop_limit_keeps_trigger_limit_and_native_protection(self,_):
  b=Broker();s=self.make(b);p=s.prepare(dict(handoff_auto=True,execution_entry_order={'type':'STOP_LIMIT'}))
  with patch('sector_heatmap.fyers_execution._current_client',return_value=b):s.submit(p['preview_id'],p['confirmation_phrase'])
  self.assertTrue(all(x['type']==4 and x['stopPrice']==100 and x['limitPrice']==100 for x in b.calls))
 def test_unrelated_rejection_and_timeout_never_retry(self):
  for reason in ('Insufficient funds','Authentication expired','Maybe intraday only'):
   b=Broker(reason);s=self.make(b);p=s.prepare(dict(handoff_auto=True))
   with patch('sector_heatmap.fyers_execution._current_client',return_value=b):s.submit(p['preview_id'],p['confirmation_phrase'])
   self.assertEqual(len(b.calls),1);self.assertTrue(self.halts)
  b=Broker();b.timeout=True;s=self.make(b);p=s.prepare(dict(handoff_auto=True))
  with patch('sector_heatmap.fyers_execution._current_client',return_value=b),self.assertRaises(TimeoutError):s.submit(p['preview_id'],p['confirmation_phrase'])
  self.assertEqual(len(b.calls),1)
