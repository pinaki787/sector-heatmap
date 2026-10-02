import hashlib,hmac,json,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from sector_heatmap.delta_india import DeltaIndia,BASE

PRODUCT=dict(id=27,symbol='BTCUSD',state='live',trading_status='operational',contract_type='perpetual_futures',contract_value='0.001',contract_unit_currency='BTC',notional_type='vanilla',is_quanto=False,tick_size='0.5',underlying_asset={'symbol':'BTC'},quoting_asset={'symbol':'USD'},settling_asset={'symbol':'USD'})
class Reply:
 status_code=200
 def __init__(self,result,meta=None):self.data={'success':True,'result':result,'meta':meta or {}}
 def json(self):return self.data
class Requests:
 def __init__(self):self.calls=[];self.now=100000;self.bid=100;self.ask=101;self.product=dict(PRODUCT);self.stale=False;self.pages=False
 def get(self,url,**kw):
  self.calls.append((url,kw));assert url.startswith(BASE+'/v2/');assert kw['allow_redirects'] is False
  if '/products/BTCUSD' in url:return Reply(self.product)
  if '/tickers/BTCUSD' in url:return Reply({'symbol':'BTCUSD','timestamp':(self.now-20 if self.stale else self.now)*1e6,'quotes':{'best_bid':str(self.bid),'best_ask':str(self.ask)}})
  if '/history/candles' in url:return Reply([{'time':self.now-300*(100-i),'open':100+i%2,'high':100+i%2,'low':100+i%2,'close':100+i%2,'volume':10} for i in range(100)]+[{'time':self.now,'open':1,'high':1,'low':1,'close':1}])
  if '/wallet/balances' in url:return Reply([{'balance':'private-balance'}])
  if '/products?' in url:
   if self.pages and 'after=' not in url:return Reply([self.product],{'after':'cursor','total_count':2})
   return Reply([{**self.product,'id':28,'symbol':'ETHUSD'}] if self.pages else [self.product],{'total_count':2 if self.pages else 1})
  raise AssertionError(url)
class Tests(unittest.TestCase):
 def setUp(self):
  thread_patch=patch('threading.Thread');thread_patch.start();self.addCleanup(thread_patch.stop)
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.req=Requests();self.b=DeltaIndia(Path(self.tmp.name)/'paper.json',requester=self.req,clock=lambda:self.req.now)
 def paper_preview(self,payload):
  side=payload.get('side','LONG');self.b.chart=lambda *a,**k:{'last_completed':{'timestamp':self.req.now-310,'cross_direction':'BULLISH' if side=='LONG' else 'BEARISH','rsi_ma':50}}
  return self.b.preview(dict(resolution='5m',rsi_length=14,ma_length=14,ma_type='SMA',signal_close=self.req.now-10)|payload)
 def test_catalog_pagination_and_cache(self):
  self.req.pages=True;c=self.b.catalog();self.assertTrue(c['complete']);self.assertEqual(len(c['instruments']),2);self.assertFalse(c['forex_supported']);calls=len(self.req.calls);self.b.catalog();self.assertEqual(calls,len(self.req.calls))
 def test_status_missing_and_live_fail_closed(self):
  s=self.b.status();self.assertEqual(s['credentials'],'MISSING');self.assertFalse(s['running']);self.assertFalse(s['live_available'])
  with self.assertRaises(PermissionError):self.b.submit({'mode':'LIVE','request_id':'missing-key-test'})
  with self.assertRaises(PermissionError):self.paper_preview({'mode':'LIVE'})
  self.assertFalse(self.req.calls)
 def test_auth_signature_and_private_data_redaction(self):
  self.b.credentials=lambda:{'DELTA_INDIA_API_KEY':'fake-key','DELTA_INDIA_API_SECRET':'fake-secret'}
  s=self.b.verify_auth();headers=self.req.calls[-1][1]['headers'];expected=hmac.new(b'fake-secret',b'GET100000/v2/wallet/balances',hashlib.sha256).hexdigest();self.assertEqual(headers['signature'],expected);self.assertEqual(s['authentication'],'VERIFIED_READ_ONLY');self.assertNotIn('private-balance',json.dumps(s));self.assertNotIn('fake-secret',json.dumps(s))
 def test_completed_rsi_analysis_no_forming_signal(self):
  s=self.b.chart('BTCUSD');self.assertTrue(s['analysis_only']);self.assertEqual(len(s['candles']),101);self.assertLess(s['last_completed']['timestamp'],self.req.now);self.assertNotEqual(s['last_completed']['close'],1)
 def test_stale_crossed_invalid_symbol_blocks(self):
  self.req.stale=True
  with self.assertRaisesRegex(ValueError,'stale'):self.b.ticker('BTCUSD')
  with self.assertRaises(ValueError):self.b.product('../wallet')
  self.req.stale=False;self.req.bid=102
  with self.assertRaisesRegex(ValueError,'crossed'):self.b.ticker('BTCUSD')
 def test_paper_preview_fill_exit_units_and_no_duplicate(self):
  p=self.paper_preview(dict(mode='PAPER',symbol='BTCUSD',side='LONG',contracts=3));self.assertEqual(p['contract_units'],.003);self.assertEqual(p['entry_reference_value'],.303);self.assertIsNone(self.b.paper['position'])
  self.b.record_paper(dict(mode='PAPER',preview_id=p['id']))
  with self.assertRaises(ValueError):self.b.record_paper(dict(mode='PAPER',preview_id=p['id']))
  self.req.bid=110;self.req.ask=111;s=self.b.close_paper({'mode':'PAPER'});self.assertAlmostEqual(s['paper']['trades'][0]['realized_pnl'],.027)
  self.assertIsNone(s['paper']['position']);self.assertEqual(s['paper']['trades'][0]['mode'],'PAPER')
  with self.assertRaises(ValueError):self.b.close_paper({'mode':'PAPER'})
  restarted=DeltaIndia(self.b.path,requester=self.req,clock=lambda:self.req.now);self.assertFalse(restarted.status()['running']);self.assertEqual(len(restarted.paper['trades']),1)
 def test_whole_contracts_expired_preview_inverse_options_writing(self):
  for n in (0,1.5,True):
   with self.assertRaises(ValueError):self.paper_preview(dict(mode='PAPER',symbol='BTCUSD',contracts=n))
  p=self.paper_preview(dict(mode='PAPER',symbol='BTCUSD',contracts=1));self.req.now+=61
  with self.assertRaises(ValueError):self.b.record_paper(dict(mode='PAPER',preview_id=p['id']))
  self.b.cache={};self.req.product['is_quanto']=True
  with self.assertRaisesRegex(ValueError,'linear'):self.paper_preview(dict(mode='PAPER',symbol='BTCUSD',contracts=1))
  self.b.cache={};self.req.product.update(is_quanto=False,contract_type='call_options')
  with self.assertRaisesRegex(ValueError,'writing'):self.paper_preview(dict(mode='PAPER',symbol='BTCUSD',contracts=1,side='SHORT'))
 def test_short_futures_ask_close_and_auth_never_uses_other_host(self):
  p=self.paper_preview(dict(mode='PAPER',symbol='BTCUSD',contracts=2,side='SHORT'));self.b.record_paper(dict(mode='PAPER',preview_id=p['id']));self.req.bid=89;self.req.ask=90;s=self.b.close_paper({'mode':'PAPER'});self.assertEqual(s['paper']['trades'][0]['realized_pnl'],.02)
  self.assertTrue(all(url.startswith(BASE+'/') for url,_ in self.req.calls))

class LiveRequests(Requests):
 def __init__(self):super().__init__();self.orders={};self.posts=0;self.deletes=0;self.position=0;self.reject=False;self.unknown=False;self.fail_auth=False;self.unfilled=0;self.state='closed'
 def get(self,url,**kw):
  if '/wallet/balances' in url:
   if self.fail_auth:
    r=Reply(None);r.status_code=401;r.data={'success':False,'error':{'code':'invalid_api_key'}};return r
   self.calls.append((url,kw));return Reply([{'asset_symbol':'USD','available_balance':'100','balance':'100'}])
  if '/positions/margined' in url:return Reply([])
  if '/positions?' in url:return Reply({'size':self.position,'entry_price':'100'})
  if '/orders/client_order_id/' in url:
   client=url.rsplit('/',1)[1]
   if client not in self.orders:raise ConnectionError('lookup unavailable')
   return Reply(self.orders[client])
  if '/fills?' in url:return Reply([{'id':'fill1','order_id':101,'product_id':27,'size':'1','price':'101','commission':'0.01','settling_asset_symbol':'USD'}])
  return super().get(url,**kw)
 def post(self,url,**kw):
  assert url==BASE+'/v2/orders';assert kw['allow_redirects'] is False;self.posts+=1;self.calls.append((url,kw));body=json.loads(kw['data'])
  if self.reject:
   r=Reply(None);r.status_code=400;r.data={'success':False,'error':{'code':'insufficient_margin'}};return r
  order={**body,'id':101,'unfilled_size':self.unfilled,'state':self.state,'average_fill_price':'101'};self.orders[body['client_order_id']]=order
  filled=body['size']-self.unfilled;self.position+=filled if body['side']=='buy' else -filled
  if self.unknown:raise ConnectionError('connection lost after accepted')
  return Reply(order)
 def delete(self,url,**kw):
  self.deletes+=1;body=json.loads(kw['data']);order=next(o for o in self.orders.values() if o['id']==body['id']);order['state']='cancelled';return Reply(order)
class LiveTests(unittest.TestCase):
 def setUp(self):
  thread_patch=patch('threading.Thread');thread_patch.start();self.addCleanup(thread_patch.stop)
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.req=LiveRequests();self.creds=lambda:{'DELTA_INDIA_API_KEY':'fake-live-key','DELTA_INDIA_API_SECRET':'fake-live-secret'};self.b=DeltaIndia(Path(self.tmp.name)/'paper.json',credentials=self.creds,requester=self.req,clock=lambda:self.req.now)
  self.b.chart=lambda *a,**k:{'last_completed':{'timestamp':self.req.now-310,'cross_direction':'BULLISH','rsi_ma':50}}
  self.payload=dict(resolution='5m',rsi_length=14,ma_length=14,ma_type='SMA',signal_close=99990,mode='LIVE',request_id='request-12345678',symbol='BTCUSD',side='buy',contracts=3,limit_price='101',time_in_force='ioc')
 def test_market_body_fill_reconciliation_and_idempotency(self):
  payload={**self.payload,'order_type':'market_order','limit_price':'invalid'}
  o=self.b.submit(payload);self.assertEqual(o['status'],'closed');self.assertEqual(o['filled_contracts'],3)
  self.assertEqual(o['request']['order_type'],'market_order');self.assertNotIn('limit_price',o['request']);self.assertEqual(o['request']['time_in_force'],'ioc')
  self.assertEqual(o['strategy'],'MANUAL_DELTA_MARKET');self.assertEqual(self.b.reconcile(payload)['status'],'closed')
  self.b.submit(payload);self.assertEqual(self.req.posts,1)
 def test_market_rejects_gtc_and_unknown_types_before_post(self):
  for terms in ({'order_type':'market_order','time_in_force':'gtc'},{'order_type':'stop_order'}):
   with self.assertRaises(ValueError):self.b.submit({**self.payload,**terms})
  self.assertEqual(self.req.posts,0)
 def test_market_partial_ioc_and_unknown_outcome(self):
  self.req.unfilled=2;self.req.state='cancelled';self.req.unknown=True
  payload={**self.payload,'order_type':'market_order'};o=self.b.submit(payload);self.assertEqual(o['status'],'UNKNOWN')
  o=self.b.submit(payload);self.assertEqual(o['status'],'cancelled');self.assertEqual(o['filled_contracts'],1);self.assertEqual(self.req.posts,1)
 def test_exact_body_signature_and_direct_submit(self):
  o=self.b.submit(self.payload);self.assertEqual(o['filled_contracts'],3);self.assertEqual(o['status'],'closed');self.assertEqual(self.req.posts,1)
  url,kw=next((u,k) for u,k in self.req.calls if 'data' in k);expected=hmac.new(b'fake-live-secret',('POST100000/v2/orders'+kw['data']).encode(),hashlib.sha256).hexdigest();self.assertEqual(kw['headers']['signature'],expected);self.assertLessEqual(len(o['client_order_id']),32)
  self.b.submit(self.payload);self.assertEqual(self.req.posts,1)
  with self.assertRaises(ValueError):self.b.submit({**self.payload,'contracts':4})
 def test_failed_auth_and_gate_make_no_order(self):
  self.req.fail_auth=True
  with self.assertRaises(ValueError):self.b.submit(self.payload)
  self.assertEqual(self.req.posts,0);self.assertFalse(self.b.status()['live_available'])
  self.req.fail_auth=False;self.b.credentials=lambda:{**self.creds(),'DELTA_INDIA_ENABLE_LIVE_ORDERS':'0'}
  with self.assertRaises(PermissionError):self.b.submit(self.payload)
  self.assertEqual(self.req.posts,0)
 def test_rejection_and_unknown_never_resubmit_across_restart(self):
  self.req.reject=True;o=self.b.submit(self.payload);self.assertEqual(o['status'],'REJECTED');self.b.submit(self.payload);self.assertEqual(self.req.posts,1)
  self.req.reject=False;self.req.unknown=True;self.req.now+=300;p={**self.payload,'request_id':'unknown-request','signal_close':self.req.now-10};o=self.b.submit(p);self.assertEqual(o['status'],'UNKNOWN')
  b=DeltaIndia(self.b.path,credentials=self.creds,requester=self.req,clock=lambda:self.req.now);o=b.submit(p);self.assertEqual(o['status'],'closed');self.assertEqual(self.req.posts,2);self.assertFalse(b.status()['running'])
 def test_partial_fill_pending_cancel_and_duplicate_guard(self):
  self.req.unfilled=2;self.req.state='open';o=self.b.submit(self.payload);self.assertEqual(o['filled_contracts'],1)
  with self.assertRaises(ValueError):self.b.submit({**self.payload,'request_id':'new-request-123'})
  o=self.b.cancel({'mode':'LIVE','request_id':self.payload['request_id']});self.assertEqual(o['status'],'cancelled');self.assertEqual(o['filled_contracts'],1)
  self.b.cancel({'mode':'LIVE','request_id':self.payload['request_id']});self.assertEqual(self.req.deletes,1)
  self.assertEqual(len(self.b.fills({'request_id':self.payload['request_id']})['fills']),1)
 def test_tick_whole_contract_and_reduce_only_guards(self):
  for field,val in [('contracts',True),('contracts',1.5),('limit_price','101.1'),('order_type','unsupported_order')]:
   with self.assertRaises(ValueError):self.b.submit({**self.payload,field:val})
  with self.assertRaises(ValueError):self.b.submit({**self.payload,'side':'sell','reduce_only':True})
  self.assertEqual(self.req.posts,0)
 def test_saved_credentials_survive_restart_and_blank_update(self):
  self.b.configure({'api_key':'local-fake-key','api_secret':'local-fake-secret'})
  before=self.b.key_path.read_bytes();self.b.configure({'api_key':'','api_secret':''});self.assertEqual(self.b.key_path.read_bytes(),before)
  b=DeltaIndia(self.b.path,requester=self.req,clock=lambda:self.req.now)
  self.assertEqual(b.status()['credentials'],'CONFIGURED');self.assertNotIn('local-fake',json.dumps(b.status()));self.assertEqual(b.key_path.stat().st_mode&0o777,0o600)
 def test_read_funds_position_and_credentials_file_masked(self):
  account=self.b.account();self.assertEqual(account['funds'][0]['asset_symbol'],'USD');self.assertNotIn('user_id',json.dumps(account))
  status=self.b.configure({'api_key':'local-fake-key','api_secret':'local-fake-secret'});self.assertNotIn('local-fake-secret',json.dumps(status));self.assertEqual(self.b.key_path.stat().st_mode&0o777,0o600)
 def arm(self,mode='PAPER',direction='BOTH'):
  # Avoid any background thread in mocks; exercise tick transitions explicitly.
  from unittest.mock import patch
  with patch('threading.Thread'):
   self.b.start_runner(dict(mode=mode,symbol='BTCUSD',contracts=3,resolution='5m',direction=direction))
 def cross(self,direction,advance=300,lag=0):
  prev=self.b.runner['last_candle'];stamp=prev+advance;self.req.now=stamp+300+lag
  self.b.chart=lambda *a,**k:{'last_completed':{'timestamp':stamp,'cross_direction':direction,'rsi_ma':50}}
 def test_runner_fresh_only_duplicate_hold_exit_no_reentry(self):
  self.arm();self.b.runner_tick();self.assertIsNone(self.b.paper['position'])
  self.cross('BULLISH');self.b.runner_tick();self.assertEqual(self.b.paper['position']['side'],'LONG');self.b.runner_tick();self.assertEqual(len(self.b.paper['trades']),1)
  self.cross(None);self.b.runner_tick();self.assertIsNotNone(self.b.paper['position'])
  self.cross('BEARISH');self.b.runner_tick();self.assertIsNone(self.b.paper['position']);self.assertEqual(len(self.b.paper['trades']),1)
  self.cross('BEARISH',lag=60);self.b.runner_tick();self.assertIsNone(self.b.paper['position'])
 def test_live_runner_actual_partial_qty_and_recovered_close(self):
  self.arm('LIVE');self.req.unfilled=2;self.req.state='cancelled';self.cross('BULLISH');self.b.runner_tick();self.assertEqual(self.b.live['runner_position']['contracts'],1)
  self.req.unfilled=0;self.cross('BEARISH');self.b.runner_tick();self.assertIsNone(self.b.live['runner_position']);self.assertEqual(self.req.posts,2);self.assertEqual(self.req.position,0)
 def test_option_both_and_external_position_block_runner(self):
  self.req.product['contract_type']='call_options'
  with self.assertRaises(ValueError):self.arm('LIVE')
  self.req.product['contract_type']='perpetual_futures';self.b.cache={};self.req.position=2
  with self.assertRaises(ValueError):self.arm('LIVE')
  self.assertEqual(self.req.posts,0)
 def test_restart_preserves_owned_position_and_never_starts(self):
  self.arm('LIVE');self.cross('BULLISH');self.b.runner_tick();self.b.stop_runner()
  b=DeltaIndia(self.b.path,credentials=self.creds,requester=self.req,clock=lambda:self.req.now);self.assertFalse(b.status()['running']);self.assertEqual(b.live['runner_position']['contracts'],3);b.close_runner({'mode':'LIVE'});self.assertEqual(self.req.position,0)

 def test_verified_connection_reports_freshness_and_rechecks_before_mutation(self):
  self.b.verify_auth();self.req.now+=61;s=self.b.status();self.assertEqual(s['authentication'],'VERIFIED_READ_ONLY');self.assertFalse(s['authentication_fresh']);self.assertTrue(s['live_available'])
  self.req.fail_auth=True
  with self.assertRaises(ValueError):self.b.submit(self.payload)
  self.assertFalse(self.b.status()['live_available']);self.assertEqual(self.req.posts,0)
