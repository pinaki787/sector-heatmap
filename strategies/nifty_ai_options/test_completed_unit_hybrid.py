import unittest,copy
from unittest.mock import patch
from direct import DirectStrategy
from core import Strategy
from hybrid_basis import seed,price,confirmed,store
from indicator import AIRenko
BASE=1700000040

def config(**extra):
 c=dict(underlying='NSE:TEST-EQ',market='NSE',timeframe=1,reference_value=12,product='INTRADAY',calculation_mode='HYBRID',signal_source='UNDERLYING',entry_gate='underlying_flip',exit_supertrend='underlying',indicator_length=5,indicator_factor=3)
 c.update(extra);return c
def candle(at,o=100,c=100,h=None,l=None,**kw):
 return dict(kind='underlying',timestamp=at,open=o,high=max(o,c)+.1 if h is None else h,low=min(o,c)-.1 if l is None else l,close=c,closed=True,closed_at=at+60,available_at=at+61,body_available=True,source_basis='PROVIDER_CONFIRMED_CLOSE',**kw)
def tick(at,p,seq):
 return dict(kind='price',series='underlying',symbol='NSE:TEST-EQ',timestamp=at,available_at=at+.1,close=p,sequence=seq,source_basis='BROKER_LIVE_PRICE')
def warm(e):
 for i in range(40):
  e.update(dict(kind='underlying',timestamp=BASE-2400+i*60,open=100,high=100.1,low=99.9,close=100))
  e.position=None
 e.entry_quotes_ready=True;e.entry_reset_at=BASE-1
 return e
class CompletedHybridTests(unittest.TestCase):
 def test_partial_brick_never_enters_but_completed_brick_enters_immediately(self):
  e=warm(DirectStrategy(config()))
  self.assertEqual(e.update_hybrid(tick(BASE+1,100.4,1)),[])
  actions=e.update_hybrid(tick(BASE+2,101.1,2))
  self.assertEqual(actions[0]['action'],'OPEN_LONG')
  self.assertEqual(actions[0]['confirmation']['confirmation_basis'],'COMPLETED_RENKO_BRICK')
  self.assertLess(actions[0]['timestamp'],BASE+60)
 def test_tick_probes_never_advance_committed_indicator_or_host_atr(self):
  e=warm(DirectStrategy(config()));before=copy.deepcopy({**e.under_ai.__dict__,'atrs':[a.__dict__ for a in e.under_ai.atrs]})
  for seq,p in enumerate((100.1,100.5,101.2,102.4),1):e.update_hybrid(tick(BASE+seq,p,seq))
  self.assertEqual({**e.under_ai.__dict__,'atrs':[a.__dict__ for a in e.under_ai.atrs]},before)
  expected=copy.deepcopy(e.under_ai);event=candle(BASE,100,102.3,h=102.4,l=100.1)
  expected.update(event);e.update_hybrid(event)
  self.assertEqual({**e.under_ai.__dict__,'atrs':[a.__dict__ for a in e.under_ai.atrs]},{**expected.__dict__,'atrs':[a.__dict__ for a in expected.atrs]})
 def test_smaller_completed_candle_exits_manual_position_but_forming_does_not(self):
  e=warm(DirectStrategy(config()));e.manual_entry('LONG',BASE-1)
  forming=candle(BASE,100,99.8);forming['closed']=False
  self.assertEqual(e.update_hybrid(forming),[])
  event=candle(BASE+60,100,99.8)
  # Reset availability watermark after rejected forming observation.
  a=e.update_hybrid(event)
  self.assertEqual(a[0]['action'],'CLOSE_LONG')
  self.assertEqual(a[0]['confirmation']['confirmation_basis'],'COMPLETED_SMALL_CANDLE_BODY')
 def test_large_closed_candle_is_not_a_smaller_confirmation(self):
  e=warm(DirectStrategy(config()));e.manual_entry('LONG',BASE-1)
  self.assertEqual(e.update_hybrid(candle(BASE,100,98)),[])
 def test_completed_brick_exits_manual_holding_without_waiting_for_candle(self):
  e=warm(DirectStrategy(config()));e.manual_entry('LONG',BASE-1)
  a=e.update_hybrid(tick(BASE+1,98.9,1))
  self.assertEqual(a[0]['action'],'CLOSE_LONG')
  self.assertEqual(a[0]['confirmation']['confirmation_basis'],'COMPLETED_RENKO_BRICK')
 def test_same_completed_brick_and_later_candle_cannot_submit_duplicate_entry(self):
  e=warm(DirectStrategy(config()));a=e.update_hybrid(tick(BASE+1,101.1,1))
  self.assertEqual(len(a),1)
  self.assertEqual(e.update_hybrid(tick(BASE+2,101.2,2)),[])
  self.assertEqual(e.update_hybrid(candle(BASE,100,101.2)),[])
 def test_new_host_waits_for_previous_broker_confirmation(self):
  e=warm(DirectStrategy(config()))
  self.assertEqual(e.update_hybrid(tick(BASE+61,102,1)),[])
  self.assertTrue(store(e)['underlying']['waiting'])
  e.update_hybrid(candle(BASE,100,100.2))
  a=e.update_hybrid(tick(BASE+62,102.1,2))
  self.assertEqual(a[0]['confirmation']['confirmation_basis'],'COMPLETED_RENKO_BRICK')
 def test_duplicate_and_regressed_quotes_do_not_rewind_bricks(self):
  e=warm(DirectStrategy(config()));ev=tick(BASE+1,100.2,1);e.update_hybrid(ev);level=e.under_renko.level
  for x in (ev,dict(ev,sequence=2,timestamp=BASE)):
   with self.assertRaises(ValueError):e.update_hybrid(x)
   self.assertEqual(e.under_renko.level,level)
 def test_option_underlying_mode_needs_no_premium_history_for_live_brick_entry(self):
  e=warm(Strategy(config()));e.reset_contract(dict(symbol='CALL',option_type='CE'),.5)
  a=e.update_hybrid(tick(BASE+1,101.1,1))
  self.assertEqual(a[0]['action'],'BUY')
  self.assertEqual(a[0]['confirmation']['confirmation_basis'],'COMPLETED_RENKO_BRICK')
 def test_ema_band_brick_exit_is_independent_of_supertrend_direction(self):
  e=warm(DirectStrategy(config(ema_band_exit=True,ema_band_period=2)))
  class Bull:
   def update(self,bar):return dict(direction=-1,flip=False,st=1,host_atr=1)
  e.under_ai=Bull();e.under_result=dict(direction=-1,flip=False,st=1)
  e.manual_entry('LONG',BASE-1)
  a=e.update_hybrid(tick(BASE+1,98.9,1))
  self.assertEqual(a[0]['reason'],'OPTIONAL_UNDERLYING_EMA_BAND')
  self.assertEqual(a[0]['confirmation']['confirmation_basis'],'COMPLETED_RENKO_BRICK')
 def test_sma_only_completed_brick_has_no_supertrend_dependency(self):
  e=warm(DirectStrategy(config(supertrend_enabled=False,sma_band_entry=True,sma_band_exit=True,sma_band_period=2,sma_retest_required=False)))
  with patch.object(e.under_ai,'update',side_effect=AssertionError('Supertrend called')):
   a=e.update_hybrid(tick(BASE+1,101.1,1))
   self.assertEqual(a[0]['action'],'OPEN_LONG')
   a=e.update_hybrid(tick(BASE+2,98.9,2))
   self.assertEqual(a[0]['action'],'CLOSE_LONG')
 def test_retest_on_still_requires_its_completed_followup_candle(self):
  e=warm(DirectStrategy(config(supertrend_enabled=False,sma_band_entry=True,sma_band_exit=True,sma_band_period=2,sma_retest_required=True)))
  self.assertEqual(e.update_hybrid(tick(BASE+1,101.1,1)),[])
 def test_timeframe_change_waits_for_new_frame_confirmation(self):
  e=warm(DirectStrategy(config()));e.update_hybrid(tick(BASE+1,100.1,1))
  e.config['timeframe']=5
  self.assertEqual(e.update_hybrid(tick(BASE+2,110,2)),[])
  self.assertTrue(store(e)['underlying']['waiting'])

 def test_api_can_capture_hybrid_without_switching_legacy_candle_requests(self):
  import ui_bridge
  from test_ui_bridge import PAYLOAD
  with patch.object(ui_bridge,'owner_broker',return_value='FYERS'),patch('native_reference.resolve_reference',return_value=None):
   self.assertEqual(ui_bridge.configuration(dict(PAYLOAD,ai_calculation_mode='HYBRID'),'owner')['calculation_mode'],'HYBRID')
   self.assertEqual(ui_bridge.configuration(dict(PAYLOAD,ai_calculation_mode='CANDLES'),'owner')['calculation_mode'],'CANDLES')
   with self.assertRaises(ValueError):ui_bridge.configuration(dict(PAYLOAD,ai_calculation_mode='RENKO'),'owner')

 def test_rejected_forming_candle_does_not_consume_its_completed_replacement(self):
  e=warm(DirectStrategy(config()));e.manual_entry('LONG',BASE-1)
  event=candle(BASE,100,99.8)
  self.assertEqual(e.update_hybrid(dict(event,closed=False)),[])
  self.assertEqual(e.update_hybrid(event)[0]['confirmation']['confirmation_basis'],'COMPLETED_SMALL_CANDLE_BODY')
