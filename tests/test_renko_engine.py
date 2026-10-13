import tempfile,unittest
from pathlib import Path
from datetime import datetime
from strategies.renko_engine.rules import replay,settings,STRATEGY
from strategies.renko_engine.runner import FyersRunner
from strategies.renko_engine.service import Service
from strategies.renko_supertrend.test_runner import FakeBroker

class EngineTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.b=FakeBroker()
  self.r=FyersRunner(self.b,Path(self.tmp.name)/'engine.json',lambda:self.b.now);self.addCleanup(self.r.release)
  anchor=datetime.fromtimestamp(self.b.rows[0]['timestamp']).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).strftime('%Y-%m-%dT%H:%M')
  self.p=dict(account_id='private-account',broker='FYERS',strategy=STRATEGY,underlying='NSE:NIFTY50-INDEX',timeframe='1 minute',lots=1,mode='PAPER',engine_settings=dict(anchorTime=anchor,rule='Renko reversal',mode='Fixed',fixedBox=5,sessionOnly=False))
  self.service=Service(self.r,self.b,'private-account','FYERS')
 def test_direct_start_retains_settings_without_preview_or_revision(self):
  v=self.r.start(self.p,background=False)
  self.assertTrue(v['running']);self.assertEqual(v['config']['strategy'],STRATEGY)
  self.assertEqual(v['config']['engine_settings']['rule'],'Renko reversal')
  self.assertFalse(v['config']['rsi_slope_enabled']);self.assertFalse(v['config']['ema_exit_enabled'])
  self.assertEqual(self.b.sent,[])
 def test_service_start_passes_full_configuration_directly(self):
  from unittest.mock import patch
  original=self.r.start
  with patch.object(self.r,'start',side_effect=lambda p:original(p,background=False)) as start:
   result=self.service.write('start',self.p)
  start.assert_called_once_with(self.p);self.assertTrue(result['running']);self.assertEqual(self.b.sent,[])
 def test_invalid_and_repeated_start_preserve_run_identity(self):
  original=self.r.state.get('run_id')
  with self.assertRaises(ValueError):self.r.start(dict(self.p,lots=0),background=False)
  self.assertEqual(self.r.state.get('run_id'),original);self.assertFalse(self.r.state['running'])
  self.r.start(self.p,background=False);active_id=self.r.state['run_id']
  with self.assertRaises(ValueError):self.r.start(self.p,background=False)
  self.assertEqual(self.r.state['run_id'],active_id);self.assertEqual(self.b.sent,[])
 def test_preview_endpoint_is_removed(self):
  with self.assertRaisesRegex(ValueError,'Unknown Renko Engine action'):self.service.write('preview',self.p)
  self.assertFalse(self.r.state['running'])
 def test_service_rejects_cross_account_before_dispatch(self):
  for action in ['preview','start','stop','backtest','chart']:
   with self.assertRaises(PermissionError):self.service.write(action,dict(self.p,account_id='other'))
  self.assertFalse(self.r.state['running']);self.assertEqual(self.b.sent,[])
 def test_live_gate_blocks_direct_start(self):
  self.b.live_enabled=lambda:False
  with self.assertRaises(ValueError):self.service.write('start',dict(self.p,mode='LIVE'))
  self.assertEqual(self.b.sent,[])
 def test_backtest_never_arms_runner_or_calls_broker_orders(self):
  v=self.service.write('backtest',dict(self.p,history_days=7))
  self.assertEqual(v['mode'],'BACKTEST');self.assertFalse(self.r.state['running']);self.assertEqual(self.b.sent,[])
 def test_delta_backtest_currency_uses_product_not_master_row(self):
  from types import SimpleNamespace
  self.b.delta=SimpleNamespace(product=lambda symbol:dict(quoting_currency='USD'))
  service=Service(self.r,self.b,'private-account','DELTA_INDIA')
  v=service.write('backtest',dict(self.p,broker='DELTA_INDIA',history_days=7))
  self.assertEqual(v['quote_currency'],'USD')
  self.assertFalse(self.r.state['running']);self.assertEqual(self.b.sent,[])
 def test_exit_uses_raw_opposite_signal_even_if_entry_blocked(self):
  self.assertEqual(self.r.exit_reason_for(dict(raw_engine_direction='BEARISH',entry_direction=None),dict(direction='BULLISH')),'RENKO_ENGINE_OPPOSITE_SIGNAL')
 def test_paper_fresh_bearish_entry_uses_put_and_no_live_calls(self):
  self.r.start(self.p,background=False)
  self.b.now+=60
  last=self.b.rows[-1]['timestamp']
  self.b.rows.append(dict(timestamp=last+60,open=110,high=111,low=78,close=80,volume=100))
  self.r.state['eligible_since']=self.b.now-10
  self.r.step()
  self.assertIsNotNone(self.r.state['position'])
  self.assertEqual(self.r.state['position']['symbol'],'NSE:TESTPE')
  self.assertEqual(self.b.sent,[])
 def test_paper_opposite_entry_blocked_direction_still_exits_position(self):
  p=dict(self.p,engine_settings=dict(self.p['engine_settings'],direction='Short only'))
  self.r.start(p,background=False)
  def append(price):
   self.b.now+=60;last=self.b.rows[-1]['timestamp']
   self.b.rows.append(dict(timestamp=last+60,open=price,high=price+1,low=price-1,close=price,volume=100))
  append(80);self.r.state['eligible_since']=self.b.now-10;self.r.step()
  self.assertIsNotNone(self.r.state['position'])
  append(150);self.r.step()
  self.assertIsNone(self.r.state['position'])
  self.assertEqual(self.b.sent,[])
  self.assertEqual(self.r.state['order_history'][-1]['reason'],'RENKO_ENGINE_OPPOSITE_SIGNAL')
 def test_live_uncertain_ack_is_not_duplicated(self):
  p=dict(self.p,mode='LIVE')
  self.r.start(p,background=False)
  self.b.now+=60;last=self.b.rows[-1]['timestamp']
  self.b.rows.append(dict(timestamp=last+60,open=110,high=111,low=78,close=80,volume=100))
  self.r.state['eligible_since']=self.b.now-10;self.b.fail=True
  self.r.step()
  self.assertEqual(self.r.state['status'],'ORDER_STATUS_UNKNOWN')
  self.assertEqual(len(self.b.sent),1)
  try:self.r.step()
  except ValueError:pass
  self.assertEqual(len(self.b.sent),1)
 def test_invalid_settings_and_candles_fail_closed(self):
  with self.assertRaises(ValueError):settings(dict(percent=float('nan')))
  with self.assertRaises(ValueError):settings(dict(rule='Supertrend'))
  with self.assertRaises(ValueError):replay(list(reversed(self.b.rows)),self.p['engine_settings'])
 def test_browser_server_parity_across_independent_rules(self):
  import json,subprocess,math
  rows=[]
  for i in range(400):
   close=1000+70*math.sin(i/9)+30*math.sin(i/3)
   rows.append(dict(timestamp=1788310800+i*300,open=close-1,high=close+4,low=close-5,close=close))
  fixtures=[dict(rule=rule,stepping=step,basis=basis,sessionOnly=session) for rule in ['EMA cross + Renko direction','EMA crossing Renko','Aligned state transition','Renko reversal'] for step in ['Whole bricks','One brick per bar','Price minus brick'] for basis in ['Current close','Previous close','Previous daily close'] for session in [True,False]]
  root=Path(__file__).resolve().parents[1]
  script="const e=require(process.argv[1]);let s='';process.stdin.on('data',b=>s+=b);process.stdin.on('end',()=>{const d=JSON.parse(s);console.log(JSON.stringify(d.fixtures.map(c=>e.simulate(d.rows,c,.05,300))));});"
  values=json.loads(subprocess.check_output([(__import__('shutil').which('node') or str(root/'.private/setup-tools/node/bin/node')),'-e',script,str(root/'renko-engine.js')],input=json.dumps(dict(rows=rows,fixtures=fixtures)).encode()))
  for c,browser in zip(fixtures,values):
   server=replay(rows,c,.05,300)
   self.assertEqual(len(server['events']),len(browser['events']))
   self.assertAlmostEqual(server['equity'],browser['equity'],places=7)
   for a,b in zip(server['events'],browser['events']):
    for key in a:
     if isinstance(a[key],(int,float)):self.assertAlmostEqual(a[key],b[key],places=7)
     else:self.assertEqual(a[key],b[key])
   for a,b in zip(server['rows'],browser['rows']):
    for key in ['level','trend','brick','fast','slow','long','short']:
     if a[key] is not None and b[key] is not None and isinstance(a[key],(int,float)):self.assertAlmostEqual(a[key],b[key],places=7)
     else:self.assertEqual(a[key],b[key])

if __name__=='__main__':unittest.main()
