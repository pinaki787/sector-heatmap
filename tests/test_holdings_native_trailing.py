from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest,threading
from sector_heatmap.holdings_native_trailing import Port,Actions,NativeTrails,normalize
from sector_heatmap.holdings_sessions import window
from tests.test_holdings_analysis import NOW

class Fake:
 def __init__(self,broker):self.broker=broker;self.book=[];self.writes=[];self.bad=False
 def get_profile(self):return {'s':'ok','data':{'fy_id':'ABC'}}
 def gtt_orderbook(self):return {'s':'ok','orderBook':deepcopy(self.book)}
 def orderbook(self):return {'s':'ok','orderBook':[]}
 def positions(self):return {'s':'ok','netPositions':[]}
 def place_gtt_order(self,n):
  self.writes.append(('CREATE',deepcopy(n)))
  leg=n['orderInfo']['leg1']
  self.book=[dict(id='1',client_id='ABC',symbol=n['symbol'],product_type=n['productType'],tran_side=n['side'],gtt_oco_ind=1,ord_status=6,qty=leg['qty'],price_trigger=leg['triggerPrice'],price_limit=leg['price'],orderTag='1:GTT'+n['orderTag'])]
  return {'s':'ok','id':'1'}
 def modify_gtt_order(self,n):
  self.writes.append(('MODIFY',deepcopy(n)));leg=n['orderInfo']['leg1']
  self.book[0].update(qty=leg['qty'],price_trigger=leg['triggerPrice'],price_limit=leg['price'])
  return {'s':'ok','id':'2' if self.bad else '1'}
 def ready(self):pass
 def profile(self):return {'products':['SELLFROMDP']}
 def request(self,operation,n):
  self.writes.append((operation,deepcopy(n)))
  if operation=='place':
   self.book=[dict(n,uniqueorderid='1',clientid='ABC',orderstatus='Confirm',orderqty=n['quantityinlot'],totalqtyremaining=n['quantityinlot'],qtytradedtoday=0,lastmodifiedtime='14-Oct-2026 10:00:00')]
   return {'status':'SUCCESS','uniqueorderid':'1'}
  self.book[0].update(price=n['newprice'],triggerprice=n['newtriggerprice'],orderqty=n['newquantityinlot'],totalqtyremaining=n['newquantityinlot'])
  return {'status':'SUCCESS'}
 def private(self,method,path,params=None,body=None):
  if method=='GET':return {'result':deepcopy(self.book),'meta':{}}
  self.writes.append((method,deepcopy(body)))
  if method=='POST':self.book=[dict(body,id=1,state='pending',unfilled_size=body['size'])]
  else:self.book[0].update(body)
  return {'result':deepcopy(self.book[0])}

class NativeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
 def make(self,b,short=False):
  f=Fake(b);account={'id':'aid','broker':b,'account_ref':'ABC','live_enabled':True}
  service=SimpleNamespace(ready=f.ready,client=f,book=lambda op:{'data':deepcopy(f.book) if op=='orders' else []})
  delta=SimpleNamespace(_private=f.private)
  p=Port(account,Path(self.tmp.name)/b,client=lambda:f,service=service,delta=delta,allowed=lambda:True,clock=lambda:NOW)
  p.folder.mkdir(exist_ok=True)
  store=SimpleNamespace(wake_events={},shutdown=threading.Event(),futures={},list=lambda *a:[])
  t=NativeTrails(p,store,clock=lambda:NOW)
  side='BUY' if short else 'SELL';trigger=105 if short else 95;limit=105.55 if short else 94.5
  native=({'symbol':'NSE:X-EQ','side':-1,'productType':'CNC','orderInfo':{'leg1':{'qty':10,'price':limit,'triggerPrice':trigger}}} if b=='FYERS' else
    dict(exchange='NSE',symboltoken=42,buyorsell='SELL',ordertype='STOPLOSS',producttype='SELLFROMDP',orderduration='GTC',price=limit,triggerprice=trigger,quantityinlot=10,disclosedquantity=0,amoorder='N') if b=='MOTILAL_OSWAL' else
    dict(product_id=42,size=10,side='buy' if short else 'sell',order_type='limit_order',reduce_only=True,time_in_force='gtc',limit_price=str(limit),stop_price=str(trigger),stop_order_type='stop_loss_order',stop_trigger_method='last_traded_price'))
  ticket=dict(quantity=10,transactionType=side,productType='CNC' if b=='FYERS' else 'SELLFROMDP' if b=='MOTILAL_OSWAL' else 'REDUCE_ONLY',price=limit,triggerPrice=trigger,native=native)
  state=dict(monitor_id='TRAIL-'+'A'*16,broker=b,owner='u:aid',account_id='aid',quantity=-10 if short else 10,stop_requested=False,running=True,pending=None,managed_stop=None,security_id='42',exchange_segment='DELTA_24X7' if b=='DELTA_INDIA' else 'NSE_EQ')
  t.save(state)
  return f,p,t,state,{'ticket':ticket}
 def changed(self,plan,trigger):
  plan=deepcopy(plan);t=plan['ticket'];t['triggerPrice']=trigger;t['price']=trigger-.5 if t['transactionType']=='SELL' else trigger+.5;n=t['native']
  if 'orderInfo' in n:n['orderInfo']['leg1'].update(triggerPrice=trigger,price=t['price'])
  elif 'triggerprice' in n:n.update(triggerprice=trigger,price=t['price'])
  else:n.update(stop_price=str(trigger),limit_price=str(t['price']))
  return plan
 def test_each_broker_create_modify_exact_confirm_and_no_loosen(self):
  for b in ('FYERS','MOTILAL_OSWAL','DELTA_INDIA'):
   with self.subTest(broker=b):
    f,p,t,s,plan=self.make(b);self.assertTrue(t.transmit(s,plan,True))
    self.assertEqual(s['managed_stop']['order_id'],'1');self.assertIsNone(s['pending'])
    self.assertFalse(t.transmit(s,self.changed(plan,94)));self.assertEqual(len(f.writes),1)
    self.assertTrue(t.transmit(s,self.changed(plan,96)));self.assertEqual(len(f.writes),2)
    self.assertEqual(s['managed_stop']['ticket']['triggerPrice'],96)
    if b=='MOTILAL_OSWAL':
     self.assertEqual(f.writes[0][1]['orderduration'],'GTC')
     self.assertEqual(f.writes[1][1]['lastmodifiedtime'],'14-Oct-2026 10:00:00')
     self.assertEqual(len(f.writes[0][1]['tag']),10)
 def test_delta_short_tightens_down_and_remains_reduce_only(self):
  f,p,t,s,plan=self.make('DELTA_INDIA',True)
  t.transmit(s,plan,True);self.assertFalse(t.transmit(s,self.changed(plan,106)))
  self.assertTrue(t.transmit(s,self.changed(plan,104)))
  self.assertTrue(f.book[0]['reduce_only']);self.assertEqual(f.book[0]['side'],'buy')
 def test_uncertain_ack_is_persisted_and_never_retried(self):
  f,p,t,s,plan=self.make('FYERS');t.transmit(s,plan,True);f.bad=True
  with self.assertRaises(ValueError):t.transmit(s,self.changed(plan,96))
  self.assertTrue(s['pending']);self.assertTrue(t.load('u:aid',s['monitor_id'])['pending'])
  with self.assertRaises(ValueError):t.transmit(s,self.changed(plan,97))
  self.assertEqual(len(f.writes),2)
 def test_external_stop_edits_block_writes(self):
  for b in ('FYERS','MOTILAL_OSWAL','DELTA_INDIA'):
   f,p,t,s,plan=self.make(b);t.transmit(s,plan,True)
   field={'FYERS':'price_trigger','MOTILAL_OSWAL':'triggerprice','DELTA_INDIA':'stop_price'}[b];f.book[0][field]=1
   with self.assertRaises(ValueError):t.transmit(s,self.changed(plan,96))
   self.assertEqual(len(f.writes),1)
 def test_partial_fill_or_transit_is_not_active_protection(self):
  for b in ('FYERS','MOTILAL_OSWAL','DELTA_INDIA'):
   f,p,t,s,plan=self.make(b);t.transmit(s,plan,True)
   f.book[0].update({'ord_status':4} if b=='FYERS' else {'qtytradedtoday':1} if b=='MOTILAL_OSWAL' else {'state':'open'})
   stop=s['managed_stop']
   with self.assertRaises(ValueError):p.confirmed(stop['ticket'],stop['order_id'],stop['correlation_id'])
 def test_revoked_live_and_stop_signal_never_mutate(self):
  f,p,t,s,plan=self.make('FYERS');p.execution_allowed=lambda:False
  with self.assertRaises(PermissionError):t.transmit(s,plan,True)
  self.assertFalse(f.writes);p.execution_allowed=lambda:True
  t.stop('u:aid',s['monitor_id']);self.assertFalse(t.transmit(s,plan,True));self.assertFalse(f.writes)
 def test_native_identity_normalization_preserves_token(self):
  r=normalize(dict(kind='DELIVERY_EQUITY',symbol='MO:NSE:42',native_identity=dict(token=42,exchange='NSE')),'MOTILAL_OSWAL')
  self.assertEqual(r['native_identity']['securityId'],'42');self.assertEqual(r['native_identity']['token'],42)
 def test_delta_session_includes_weekends_and_future_years(self):
  self.assertTrue(window('DELTA_24X7',datetime(2027,1,2).timestamp())['open'])
 def test_plan_rejects_wrong_scope_stale_and_changed_position(self):
  f,p,t,s,plan=self.make('FYERS');a=t.actions
  row=dict(kind='DELIVERY_EQUITY',action='TRAIL',symbol='NSE:X-EQ',quantity=10,average_price=80,holding_type='HLD',native_identity={'securityId':'NSE:X-EQ','exchangeSegment':'NSE_EQ'})
  report=dict(broker='FYERS',account_id='aid',as_of=datetime.fromtimestamp(NOW).astimezone().isoformat())
  with self.assertRaises(PermissionError):a._plan(dict(report,account_id='other'),row,{})
  with self.assertRaises(ValueError):a._plan(dict(report,as_of='2020-01-01T00:00:00+00:00'),row,{})
  p.inventory=lambda:[dict(row,quantity=11)]
  with self.assertRaisesRegex(ValueError,'quantity'):a._plan(report,row,{})
 def test_other_existing_protection_is_not_adopted(self):
  f,p,t,s,plan=self.make('FYERS')
  row=dict(kind='DELIVERY_EQUITY',action='TRAIL',symbol='NSE:X-EQ',quantity=10,average_price=80,holding_type='HLD',native_identity={'securityId':'NSE:X-EQ','exchangeSegment':'NSE_EQ'})
  report=dict(broker='FYERS',account_id='aid',as_of=datetime.fromtimestamp(NOW).astimezone().isoformat())
  p.inventory=lambda:[row];f.book=[dict(id='foreign',symbol=row['symbol'],ord_status=6)]
  with self.assertRaisesRegex(ValueError,'Another order'):t.actions._plan(report,row,{})

 def test_each_native_plan_builds_the_correct_protection_terms(self):
  for b in ('FYERS','MOTILAL_OSWAL','DELTA_INDIA'):
   with self.subTest(broker=b):
    f,p,t,state,unused=self.make(b,short=b=='DELTA_INDIA')
    meta=dict(securityId='NSE:X-EQ' if b=='FYERS' else '42',exchangeSegment='DELTA_24X7' if b=='DELTA_INDIA' else 'NSE_EQ')
    if b=='MOTILAL_OSWAL':meta.update(token=42,exchange='NSE')
    row=dict(symbol='BTCUSD' if b=='DELTA_INDIA' else 'NSE:X-EQ',kind='LINEAR_FUTURE' if b=='DELTA_INDIA' else 'DELIVERY_EQUITY',
       quantity=-10 if b=='DELTA_INDIA' else 10,average_price=120 if b=='DELTA_INDIA' else 80,holding_type='Linear futures position' if b=='DELTA_INDIA' else 'HLD',
       native_identity=meta,action='TRAIL',candidate_stop=105 if b=='DELTA_INDIA' else 95)
    p.inventory=lambda:[deepcopy(row)]
    report=dict(broker=b,account_id='aid',as_of=datetime.fromtimestamp(NOW).astimezone().isoformat())
    if b=='MOTILAL_OSWAL':
     p.service.master=SimpleNamespace(exact=lambda symbol:dict(token=42,exchange='NSE',tick_size=.05,lot_size=1))
     p.service.quote=lambda symbol:dict(depth=dict(bid=100,received_at=NOW))
     p.service.book=lambda op:dict(data=[dict(nsesymboltoken=42,dpquantity=10,poaquantity=10,collateralquantity=0,blockedquantity=0,tpinquantity=0,nonpoaquantity=0,rmssellingquantity=0,buybackquantity=0,slbmquantity=0,nbfcquantity=0,debitstockquantity=0)] if op=='holdings' else [])
    elif b=='DELTA_INDIA':
     p.delta.product=lambda symbol:dict(id=42,tick_size=.5)
     p.delta.ticker=lambda symbol:dict(bid=99,ask=100)
    master=SimpleNamespace(lookup=lambda symbols:{'NSE:X-EQ':dict(tick_size=.05,lot_size=1)})
    with patch('sector_heatmap.handoff.FyersCmMaster',return_value=master),patch('sector_heatmap.parser_protection_broker.ParserProtectionBroker.fresh_price',return_value=100):
     plan=t.actions._plan(report,row,{},monitor_path=t.path(state['monitor_id']))
    self.assertTrue(plan['live_submission_enabled'])
    self.assertEqual(plan['ticket']['quantity'],10)
    if b=='FYERS':self.assertEqual(plan['ticket']['native']['orderInfo']['leg1']['qty'],10)
    if b=='MOTILAL_OSWAL':self.assertEqual(plan['ticket']['native']['orderduration'],'GTC')
    if b=='DELTA_INDIA':
     self.assertTrue(plan['ticket']['native']['reduce_only'])
     self.assertEqual(plan['ticket']['transactionType'],'BUY')
