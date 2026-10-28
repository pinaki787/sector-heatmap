import unittest
from copy import deepcopy
from .signals import Engine,settings
from .runner import analysis,ema_adverse
from .exit_indicators import reason

BASE=dict(strategy_basis='RENKO',brick_mode='Manual',manual_brick=10,atr_length=3,factor=3,supertrend_enabled=True,ema_fast_enabled=True,ema_slow_enabled=False,ema_third_enabled=False,ema_widening_enabled=False,rsi_slope_enabled=False,rsi_level_enabled=False,ema_exit_enabled=True,ema_exit_length=10,renko_brick_exit_enabled=True,session_deadline=None,timeframe='1 minute',underlying='BTCUSD')
def candles(prices):return [dict(timestamp=1793140200+i*60,open=p,high=p+1,low=p-1,close=p) for i,p in enumerate(prices)]
class BrickBasisTests(unittest.TestCase):
 def test_separate_uniform_bricks_two_box_reversal(self):
  e=Engine(BASE);out=[e.update(c) for c in candles([100,135,125,110])]
  self.assertEqual([r['brick_count'] for r in out],[0,3,0,1])
  bricks=[b for r in out for b in r['brick_events']]
  self.assertTrue(all(abs(b['close']-b['open'])==10 for b in bricks))
  self.assertEqual((bricks[-1]['open'],bricks[-1]['close']),(120,110))
 def test_each_brick_ema_matches_hand_calculation(self):
  e=Engine(BASE);out=[e.update(c) for c in candles([100,135,165])]
  value=None
  for b in [b for r in out for b in r['brick_events']]:
   value=b['close'] if value is None else 2/11*b['close']+9/11*value
   self.assertAlmostEqual(b['ema10'],value)
   self.assertAlmostEqual(b['ema_exit'],value)
  self.assertEqual(e.state['brick_indicator_state']['count'],6)
 def test_forming_and_no_brick_never_create_signal_or_exit(self):
  e=Engine(BASE);rows=candles([100,135,136]);e.update(rows[0]);e.update(rows[1]);before=deepcopy(e.state)
  self.assertIsNone(e.update({**rows[2],'is_forming':True}));self.assertEqual(e.state,before)
  r=e.update(rows[2]);self.assertIsNone(r['entry_direction']);self.assertFalse(ema_adverse(r,'BULLISH'));self.assertIsNone(reason(BASE,r,'BULLISH'))
 def test_exit_examines_intermediate_bricks(self):
  r=dict(strategy_basis='RENKO',has_completed_brick=True,brick_exit_events=[dict(close=90,ema_exit=95,brick_direction='BEARISH',raw_supertrend_cross_direction='BEARISH'),dict(close=100,ema_exit=95,brick_direction='BULLISH')],ema_exit_enabled=True)
  self.assertTrue(ema_adverse(r,'BULLISH'));self.assertEqual(reason(BASE,r,'BULLISH'),'RENKO_ST_EXIT')
  self.assertEqual(reason({**BASE,'supertrend_exit_enabled':False},r,'BULLISH'),'OPPOSITE_RENKO_BRICK_CLOSE')
 def test_resume_equals_uninterrupted_and_no_duplicate_host(self):
  rows=candles([100,135,165,185,155,125]);a=analysis(rows,BASE,.05,retain=0)
  b=analysis(rows[:3],BASE,.05,retain=0);b=analysis(rows,BASE,.05,b,retain=0)
  self.assertEqual(a['rows'],b['rows']);self.assertEqual(a['state'],b['state'])
  with self.assertRaises(ValueError):Engine(BASE,state=a['state']).update(rows[-1])
 def test_ema_30_uses_bricks_not_host_closes(self):
  e=Engine({**BASE,'ema_exit_length':30});value=None
  for r in [e.update(c) for c in candles([100,135,165])]:
   for b in r['brick_events']:
    value=b['close'] if value is None else 2/31*b['close']+29/31*value
    self.assertAlmostEqual(b['ema_exit'],value)
 def test_candlestick_uses_actual_ohlc_and_ema(self):
  e=Engine({**BASE,'strategy_basis':'CANDLESTICK'});value=None
  for c in candles([100,135,136]):
   r=e.update(c);value=c['close'] if value is None else 2/11*c['close']+9/11*value
   self.assertEqual(r['synthetic_close'],c['close']);self.assertAlmostEqual(r['ema10'],value)
 def test_auto_size_is_frozen_and_prefix_stable(self):
  cfg={**BASE,'brick_mode':'Auto'};rows=candles([100,110,120,130,140,160,200,300]);out=analysis(rows,cfg,.05,retain=0)
  boxes=[r['box'] for r in out['rows'] if r['box'] is not None];self.assertTrue(all(b==boxes[0] for b in boxes))
  self.assertEqual(analysis(rows[:6],cfg,.05,retain=0)['rows'],out['rows'][:6])
 def test_no_exit_and_reentry_in_one_host(self):
  e=Engine(BASE)
  for r in [e.update(c) for c in candles([100,135,165,195,115,195])]:
   events=[b['lifecycle_event'] for b in r['brick_events'] if b.get('lifecycle_event')]
   exits=[i for i,v in enumerate(events) if v.endswith('EXIT')]
   if exits:self.assertFalse(any(v in ('BUY','SELL') for v in events[exits[0]+1:]))
 def test_invalid_basis_and_intrabar_rejected(self):
  with self.assertRaises(ValueError):settings(dict(strategy_basis='invalid'))
  with self.assertRaises(ValueError):settings({**BASE,'intrabar_entries':True})
 def test_optional_anti_chop_keeps_host_observations(self):
  cfg={**BASE,'anti_chop_enabled':True,'anti_chop_mode':'Manual'};e=Engine(cfg)
  rows=candles([100+i*35 for i in range(60)])
  for c in rows:e.update(c)
  self.assertEqual(e.state['anti_chop']['count'],60)
  self.assertGreater(e.state['brick_indicator_state']['count'],60)
 def test_full_ui_query_parses_optional_false_switches_for_all_native_brokers(self):
  from .delta_service import Service
  from types import SimpleNamespace
  query={k:[str(v).lower() if isinstance(v,bool) else str(v)] for k,v in settings(BASE).items() if isinstance(v,(str,int,float,bool))}
  query.update(symbol=['BTCUSD'],timeframe=['1 minute'],calibrated_enabled=['false'],zone_entry_enabled=['false'],manual_trend_enabled=['false'],renko_brick_exit_enabled=['true'])
  for broker in ('DELTA_INDIA','DHAN','MOTILAL_OSWAL'):
   service=SimpleNamespace(instrument=None,execution=SimpleNamespace(account={'broker':broker}),chart_broker=SimpleNamespace(session_policy=lambda c:{}))
   config=Service.chart_config(service,query)
   self.assertEqual(config['strategy_basis'],'RENKO');self.assertTrue(config['renko_brick_exit_enabled']);self.assertFalse(config['calibrated_enabled'])
 def test_native_chart_bounds_payload_and_reuses_confirmed_history(self):
  from .delta_service import Service
  from types import SimpleNamespace
  from unittest.mock import patch
  import threading
  rows=candles([100+(i%30) for i in range(6000)]);cfg={**BASE,'chart_entry_guards':False}
  broker=SimpleNamespace(candles=lambda c:rows,host_tick_size=lambda s:.5,start=lambda:None,session_policy=lambda c:{},route_availability=lambda c:{})
  service=SimpleNamespace(chart_config=lambda q:dict(cfg),chart_broker=broker,lock=threading.RLock(),context={})
  now=rows[-1]['timestamp']+120
  with patch('strategies.renko_supertrend.delta_service.time.time',return_value=now):
   first=Service.chart(service,{'history_preset':['45']});second=Service.chart(service,{'history_preset':['45']})
  self.assertEqual(len(first['rows']),5000);self.assertEqual(first['rows'],second['rows']);self.assertEqual(second['host_bar_count'],6000)
  self.assertIn('5,000',first['history']['anchor_policy'])
if __name__=='__main__':unittest.main()
