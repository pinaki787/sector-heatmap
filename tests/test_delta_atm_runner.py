import unittest
from unittest.mock import patch
from tests import test_delta_chart_options as chart_fixture
from tests import test_delta_india as fixture
from datetime import datetime,timezone

class AtmOptionRunner(unittest.TestCase):
 def setUp(self):
  chart_fixture.ChartOptions.setUp(self)
  for row in self.rows:
   if row.get('settlement_time'):
    row['settlement_time']=datetime.fromtimestamp(self.req.now+7200,timezone.utc).isoformat()
  self.signal(None)
 def signal(self,cross=None,touch=None):
  self.b.chart=lambda *a,**k:dict(last_completed=dict(timestamp=self.req.now-310,rsi_ma=50,cross_direction=cross,entry_direction=touch or cross,entry_reason='CANDLE_EXTREME_EMA_TOUCH' if touch else 'CROSSOVER'))
 def config(self,mode='PAPER'):
  return dict(mode=mode,symbol='BTCUSD',resolution='5m',rsi_length=14,ma_length=14,ma_type='EMA',contracts=10,direction='BOTH',strategy_mode='ATM_OPTIONS')
 def test_one_minute_runner_enters_and_exits_on_new_completed_underlying_candles(self):
  self.req.now=int(self.req.now//60)*60+10
  calls=[]
  cross=[None]
  def chart(symbol,resolution,*args):
   calls.append((symbol,resolution))
   return dict(last_completed=dict(timestamp=int(self.req.now//60)*60-60,rsi_ma=50,cross_direction=cross[0],entry_direction=cross[0],entry_reason='CROSSOVER'))
  self.b.chart=chart
  self.b.start_runner(self.config()|dict(resolution='1m'))
  self.assertEqual(self.b.runner['config']['resolution'],'1m')
  self.req.now+=60;cross[0]='BULLISH';self.b.runner_tick()
  self.assertTrue(self.b.paper['position']['symbol'].startswith('C-'))
  self.assertEqual(self.b.paper['position']['entry_timeframe'],'1m')
  entries=len(self.b.paper['trades'])
  self.b.runner_tick();self.assertEqual(len(self.b.paper['trades']),entries)
  self.req.now+=60;cross[0]='BEARISH';self.b.runner_tick()
  self.assertIsNone(self.b.paper['position'])
  self.assertEqual(len(self.b.paper['trades']),1)
  self.assertEqual(self.b.paper['trades'][0]['entry_timeframe'],'1m')
  self.assertTrue(any(symbol=='BTCUSD' for symbol,resolution in calls))
  self.assertTrue(all(resolution=='1m' for symbol,resolution in calls))
 def test_explicit_futures_long_short_and_opposite_exit(self):
  for direction,side,opposite in [('BULLISH','LONG','BEARISH'),('BEARISH','SHORT','BULLISH')]:
   self.setUp();cfg=self.config();cfg['strategy_mode']='FUTURES';self.b.start_runner(cfg);self.req.now+=300;self.signal(direction);self.b.runner_tick()
   p=self.b.paper['position'];self.assertEqual(p['symbol'],'BTCUSD');self.assertEqual(p['side'],side);self.assertEqual(self.b.runner['config']['strategy_mode'],'FUTURES')
   self.req.now+=300;self.signal(opposite);self.b.runner_tick();self.assertIsNone(self.b.paper['position']);self.assertEqual(len(self.b.paper['trades']),1)
 def test_futures_mode_rejects_option_before_activation(self):
  cfg=self.config();cfg.update(strategy_mode='FUTURES',symbol=next(r['symbol'] for r in self.rows if r['contract_type']=='call_options'))
  with self.assertRaisesRegex(ValueError,'perpetual futures'):self.b.start_runner(cfg)
  self.assertFalse(self.b.runner['running']);self.assertEqual(self.b.paper['trades'],[])
 def test_bullish_call_and_bearish_put_are_both_long_with_underlying_opposite_exits(self):
  for direction,prefix,opposite in [('BULLISH','C','BEARISH'),('BEARISH','P','BULLISH')]:
   self.setUp();self.b.start_runner(self.config());self.req.now+=300;self.signal(direction);self.b.runner_tick();p=self.b.paper['position']
   self.assertTrue(p['symbol'].startswith(prefix+'-'));self.assertEqual(p['side'],'LONG');self.assertEqual(p['contracts'],10);self.assertEqual(p['signal_symbol'],'BTCUSD');self.assertEqual(p['signal_direction'],direction);self.assertEqual(p['entry_reason'],'CROSSOVER');self.assertEqual(p['entry_price'],101)
   self.req.now+=300;self.signal(None,touch=opposite);self.b.runner_tick();self.assertIsNotNone(self.b.paper['position'])
   self.req.now+=300;self.signal(opposite);self.b.runner_tick();self.assertIsNone(self.b.paper['position']);self.assertTrue(self.b.runner['running']);self.assertEqual(len(self.b.paper['trades']),1);self.assertEqual(self.b.paper['trades'][0]['exit_fills'][0]['reason'],'OPPOSITE_CROSSOVER')
 def test_live_partial_put_buy_and_reduce_only_sell_never_posts_future(self):
  self.b.credentials=lambda:dict(DELTA_INDIA_API_KEY='fake-key',DELTA_INDIA_API_SECRET='fake-secret',DELTA_INDIA_ENABLE_LIVE_ORDERS='1');self.b.requester=fixture.LiveRequests()
  self.b.start_runner(self.config('LIVE'));self.req.now+=300;self.signal(None,touch='BEARISH');self.b.requester.unfilled=2;self.b.requester.state='cancelled';self.b.runner_tick()
  p=self.b.live['runner_position'];self.assertEqual(p['side'],'buy');self.assertTrue(p['symbol'].startswith('P-'));self.assertEqual(p['contracts'],8);self.assertEqual(p['signal_direction'],'BEARISH')
  self.req.now+=300;self.signal('BULLISH');self.b.requester.unfilled=0;self.b.requester.state='closed';self.b.runner_tick();self.assertIsNone(self.b.live['runner_position'])
  orders=list(self.b.live['orders'].values());self.assertEqual(len(orders),2);self.assertTrue(all(o['symbol'].startswith('P-') for o in orders));self.assertEqual(orders[0]['request']['side'],'buy');self.assertEqual(orders[1]['request']['side'],'sell');self.assertTrue(orders[1]['request']['reduce_only']);self.assertEqual(orders[1]['request']['size'],8)
 def test_partial_paper_close_uses_only_remaining_owned_option_quantity(self):
  self.b.start_runner(self.config());self.req.now+=300;self.signal('BEARISH');self.b.runner_tick();self.b._paper_reduce(3,'EXPLICIT_REDUCE_ONLY');self.req.now+=300;self.signal('BULLISH');self.b.runner_tick()
  trade=self.b.paper['trades'][0];self.assertEqual([f['contracts'] for f in trade['exit_fills']],[3,7]);self.assertEqual(trade['remaining_contracts'],0)
 def test_put_trailing_uses_rising_option_bid_and_latched_stop(self):
  self.b.start_runner(self.config()|dict(trailing_enabled=True,trailing_mode='PERCENTAGE',trailing_step=5));self.req.now+=300;self.signal('BEARISH');self.b.runner_tick();symbol=self.b.paper['position']['symbol'];self.req.now+=300;self.signal(None)
  with patch.object(self.b,'ticker',side_effect=lambda s:dict(symbol=s,bid=107,ask=108,spot_price='100.4',exchange_at=self.req.now,received_at=self.req.now)):
   self.b.runner_tick()
  self.assertEqual(self.b.paper['position']['contracts'],7);self.assertEqual(float(self.b.paper['position']['trailing']['stop']),101)
  self.req.now+=1
  with patch.object(self.b,'ticker',side_effect=lambda s:dict(symbol=s,bid=100,ask=101,spot_price='100.4',exchange_at=self.req.now,received_at=self.req.now)):
   self.b.runner_tick()
  self.assertIsNone(self.b.paper['position']);fills=self.b.paper['trades'][0]['exit_fills'];self.assertEqual([f['contracts'] for f in fills],[3,7]);self.assertEqual(fills[-1]['reason'],'TRAILING_STOP')
 def test_missing_put_route_and_expired_entry_signal_fail_without_futures_fallback(self):
  self.rows[:]=[r for r in self.rows if r['contract_type']!='put_options']
  with self.assertRaisesRegex(ValueError,'No still-unexpired'):self.b.start_runner(self.config())
  self.assertFalse(self.b.runner['running']);self.assertFalse(self.b.paper['trades'])
  self.setUp();self.b.start_runner(self.config());self.req.now+=300;self.signal('BULLISH');route=self.b.chart_option
  def slow(*args):
   result=route(*args);self.req.now+=31;return result
  with patch.object(self.b,'chart_option',side_effect=slow):
   with self.assertRaisesRegex(ValueError,'expired'):self.b.runner_tick()
  self.assertFalse(self.b.paper['trades'])
 def test_put_submit_monitor_uses_underlying_rsi_and_closes_only_on_bullish_cross(self):
  self.req.now=99910
  payload=dict(mode='PAPER',symbol='P-100-100100',side='LONG',contracts=10,chart_symbol='BTCUSD',chart_direction='SELL',chart_resolution='5m',chart_rsi_length=14,chart_ma_length=14,chart_ma_type='EMA',chart_signal_close=self.req.now-10)
  self.signal('BEARISH');preview=self.b.preview(payload);self.b.record_paper(dict(mode='PAPER',preview_id=preview['id']));self.assertTrue(self.b.runner['config']['one_shot']);self.assertEqual(self.b.runner['config']['symbol'],'BTCUSD')
  self.req.now+=300;self.signal('BEARISH');self.b.runner_tick();self.assertIsNotNone(self.b.paper['position'])
  self.req.now+=300;self.signal('BULLISH');self.b.runner_tick();self.assertIsNone(self.b.paper['position']);self.assertFalse(self.b.runner['running'])
