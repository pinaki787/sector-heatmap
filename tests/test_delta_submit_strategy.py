import unittest
from unittest.mock import patch
from sector_heatmap.delta_india import DeltaIndia
from tests import test_delta_india as fixture

class SubmitStrategyTests(unittest.TestCase):
 def setUp(self):
  fixture.LiveTests.setUp(self);self.req.now=99910
 def ticket(self,mode='LIVE',side='buy',ma='SMA'):
  return dict(self.payload,mode=mode,side=('LONG' if side=='buy' else 'SHORT') if mode=='PAPER' else side,ma_type=ma,order_type='market_order',time_in_force='ioc',reduce_only=False)
 def analysis(self,cross='BULLISH',stamp=None):
  calls=[]
  def chart(*args,**kw):
   calls.append(args)
   return {'last_completed':None if cross is None else {'timestamp':self.req.now-310 if stamp is None else stamp,'cross_direction':cross,'rsi_ma':50}}
  self.b.chart=chart;return calls
 def entry(self,t):
  if t['mode']=='PAPER':
   p=self.b.preview(t);return self.b.record_paper({'mode':'PAPER','preview_id':p['id']})
  return self.b.submit(t)
 def test_paper_entry_timeframe_survives_exit_and_reload(self):
  for resolution in ('1m','5m','1h'):
   self.setUp();self.analysis('BULLISH')
   self.entry(self.ticket('PAPER')|dict(resolution=resolution))
   self.assertEqual(self.b.paper['position']['entry_timeframe'],resolution)
   self.b.close_paper(dict(mode='PAPER'))
   restarted=DeltaIndia(self.b.path,requester=self.req,clock=lambda:self.req.now)
   self.assertEqual(restarted.paper['trades'][0]['entry_timeframe'],resolution)
 def test_paper_live_sma_ema_long_short_snapshot_opposite_exit_no_reentry(self):
  for mode in ('PAPER','LIVE'):
   for side in ('buy','sell'):
    for ma in ('SMA','EMA'):
     with self.subTest(mode=mode,side=side,ma=ma):
      self.setUp();t=self.ticket(mode,side,ma);calls=self.analysis('BULLISH' if side=='buy' else 'BEARISH');self.entry(t)
      self.assertTrue(self.b.runner['running']);self.assertTrue(self.b.runner['config']['one_shot']);self.assertFalse(self.b.runner['config']['trailing_enabled']);self.assertEqual(self.b.runner['config']['ma_type'],ma)
      self.req.now+=300;self.analysis('BEARISH' if side=='buy' else 'BULLISH');self.b.runner_tick();self.assertFalse(self.b.runner['running']);self.assertIsNone(self.b.live['runner_position']);self.assertIsNone(self.b.paper['position']);posts=self.req.posts;self.req.now+=300;self.b.runner_tick();self.assertEqual(self.req.posts,posts)
      if mode=='LIVE':self.assertEqual(posts,2);self.assertEqual(self.req.position,0)
      else:self.assertEqual(posts,0);self.assertEqual(self.b.paper['trades'][0]['status'],'CLOSED')
 def test_touch_entry_accepted_but_opposite_touch_does_not_exit(self):
  for mode in ('PAPER','LIVE'):
   for side in ('buy','sell'):
    self.setUp();wanted='BULLISH' if side=='buy' else 'BEARISH'
    self.b.chart=lambda *a,**k: {'last_completed':dict(timestamp=self.req.now-310,cross_direction=None,entry_direction=wanted,entry_reason='CANDLE_EXTREME_EMA_TOUCH',rsi_ma=50)}
    self.entry(self.ticket(mode,side,'EMA'));self.assertTrue(self.b.runner['running'])
    self.req.now+=300;opposite='BEARISH' if side=='buy' else 'BULLISH'
    self.b.chart=lambda *a,**k: {'last_completed':dict(timestamp=self.req.now-310,cross_direction=None,entry_direction=opposite,entry_reason='CANDLE_EXTREME_EMA_TOUCH',rsi_ma=50)}
    posts=self.req.posts;self.b.runner_tick();self.assertTrue(self.b.runner['running']);self.assertEqual(self.req.posts,posts)
    self.req.now+=300;self.analysis(opposite);self.b.runner_tick();self.assertFalse(self.b.runner['running'])
 def test_manual_entry_without_missing_wrong_or_stale_signal_keeps_exit_monitor(self):
  for mode in ('LIVE','PAPER'):
   for cross,stamp in [(None,None),('BEARISH',None),('BULLISH',99000)]:
    self.setUp();self.analysis(cross,stamp);self.entry(self.ticket(mode));self.assertTrue(self.b.runner['running']);self.assertTrue(self.b.runner['config']['one_shot'])
    position=self.b.live['runner_position'] if mode=='LIVE' else self.b.paper['position'];self.assertEqual(position['entry_reason'],'MANUAL_DISCRETIONARY')
   for change in [dict(ma_type='INVALID'),dict(rsi_length=True),dict(ma_length=0),dict(resolution='invalid')]:
    self.setUp();self.analysis()
    with self.assertRaises(ValueError):self.entry(self.ticket(mode)|change|dict(runner=True,_runner_origin=True))
    self.assertEqual(self.req.posts,0)
 def test_paper_fill_does_not_revalidate_entry_signal(self):
  self.analysis(None);p=self.b.preview(self.ticket('PAPER'));self.analysis('BEARISH');self.b.record_paper({'mode':'PAPER','preview_id':p['id']})
  self.assertEqual(len(self.b.paper['trades']),1);self.assertTrue(self.b.runner['running'])
 def test_duplicate_consumed_signal_settings_change_and_stop_restart(self):
  self.analysis();t=self.ticket();self.b.submit(t);self.b.submit(t);self.assertEqual(self.req.posts,1);self.b.stop_runner()
  b=DeltaIndia(self.b.path,credentials=self.creds,requester=self.req,clock=lambda:self.req.now);self.assertFalse(b.runner['running']);self.assertIn('restart',b.runner['message']);self.assertEqual(b.live['runner_position']['contracts'],3)
  self.analysis()
  with self.assertRaisesRegex(ValueError,'flat exact'):self.b.submit(t|dict(request_id='changed-ma-request',ma_type='EMA'))
  b.close_runner({'mode':'LIVE'});self.assertEqual(self.req.position,0);self.assertEqual(self.req.posts,2)
 def test_partial_entry_exit_latches_residual_and_never_duplicates_pending(self):
  self.analysis();self.req.unfilled=2;self.req.state='cancelled';self.b.submit(self.ticket());self.assertEqual(self.b.live['runner_position']['contracts'],1)
  self.req.now+=300;self.analysis('BEARISH');self.req.unfilled=1;self.b.runner_tick();self.assertEqual(self.b.live['runner_position']['contracts'],1);self.assertTrue(self.b.live['runner_position']['submit_exit_latched']);self.assertEqual(self.req.posts,2)
  self.req.unfilled=0;self.b.runner_tick();self.assertEqual(self.req.posts,3);self.assertEqual(self.req.position,0);self.assertFalse(self.b.runner['running']);self.b.runner_tick();self.assertEqual(self.req.posts,3)
 def test_gtc_partial_entry_cancels_unfilled_before_owned_exit(self):
  self.analysis();self.req.unfilled=2;self.req.state='open';self.b.submit(self.ticket()|dict(order_type='limit_order',time_in_force='gtc'));self.assertIsNone(self.b.live['runner_position'])
  self.req.now+=300;self.analysis('BEARISH');self.req.unfilled=0;self.req.state='closed';self.b.runner_tick();self.assertEqual(self.req.deletes,1);self.assertEqual(self.req.position,0);self.assertFalse(self.b.runner['running'])
 def test_unknown_exit_reconciliation_and_external_position_never_adopted(self):
  self.analysis();self.b.submit(self.ticket());self.req.now+=300;self.analysis('BEARISH');self.req.unknown=True;self.b.runner_tick();self.assertEqual(self.req.posts,2);self.b.runner_tick();self.assertEqual(self.req.posts,2);self.assertFalse(self.b.runner['running'])
  self.setUp();self.req.position=2;self.analysis()
  with self.assertRaisesRegex(ValueError,'flat exact'):self.b.submit(self.ticket())
  self.assertEqual(self.req.posts,0)
 def test_explicit_paper_live_reduce_only_no_entry_cross_and_no_new_monitor(self):
  self.req.position=3;self.analysis(None);self.b.submit(self.ticket()|dict(side='sell',reduce_only=True));self.assertEqual(self.req.position,0);self.assertFalse(self.b.runner['running'])
  self.setUp();self.analysis();self.entry(self.ticket('PAPER'));self.analysis(None);p=self.b.preview(self.ticket('PAPER','sell')|dict(contracts=1,reduce_only=True));self.b.record_paper({'mode':'PAPER','preview_id':p['id']});self.assertEqual(self.b.paper['position']['contracts'],2);self.assertEqual(self.req.posts,0)
  with self.assertRaisesRegex(ValueError,'reduce-only'):self.b.preview(self.ticket('PAPER')|dict(reduce_only=True))
 def test_explicit_manual_reduction_updates_managed_owned_remainder(self):
  self.analysis();self.b.submit(self.ticket());self.analysis(None);self.b.submit(self.ticket()|dict(request_id='explicit-reduce-one',side='sell',contracts=1,reduce_only=True));self.assertEqual(self.b.live['runner_position']['contracts'],2);self.assertEqual(self.req.position,2)
 def test_exit_keeps_entry_settings_and_stale_cross_does_not_close(self):
  self.analysis();self.b.submit(self.ticket(ma='EMA')|dict(rsi_length=9,ma_length=7));calls=self.analysis('BEARISH',stamp=99000);self.b.runner_tick();self.assertEqual(self.req.posts,1);self.assertEqual(calls[0],('BTCUSD','5m',9,7,'EMA'));self.assertTrue(self.b.runner['running'])

 def test_missing_configuration_cannot_bypass_gate_and_paper_reduce_checks_identity(self):
  self.analysis()
  with self.assertRaisesRegex(ValueError,'settings missing'):self.b.submit(dict(mode='LIVE',request_id='bypass-client-test',symbol='BTCUSD',side='buy',contracts=3,limit_price='101',runner=True,reduce_only=False))
  self.assertEqual(self.req.posts,0)
  self.entry(self.ticket('PAPER'));p=self.b.preview(self.ticket('PAPER','sell')|dict(contracts=1,reduce_only=True));self.b.paper['position']['lifecycle_id']='different'
  with self.assertRaisesRegex(ValueError,'position changed'):self.b.record_paper(dict(mode='PAPER',preview_id=p['id']))
 def test_monitor_disconnection_stops_truthfully_without_exit_or_reentry(self):
  self.analysis();self.b.submit(self.ticket());event=self.b.stop_event
  self.b.chart=lambda *a,**k:(_ for _ in ()).throw(ValueError('History disconnected; protection unavailable'))
  class Once:
   def __init__(self):self.calls=0;self.stopped=False
   def wait(self,n):self.calls+=1;return self.calls>1
   def is_set(self):return self.stopped
   def set(self):self.stopped=True
  event=Once();self.b.stop_event=event;self.b._run(event);self.assertFalse(self.b.runner['running']);self.assertIn('disconnected',self.b.runner['message']);self.assertEqual(self.req.posts,1);self.assertEqual(self.b.live['runner_position']['contracts'],3)

 def test_new_runner_between_paper_preview_and_record_blocks_lifecycle_takeover(self):
  self.analysis();p=self.b.preview(self.ticket('PAPER'));self.b.runner['running']=True
  with self.assertRaisesRegex(ValueError,'became active'):self.b.record_paper(dict(mode='PAPER',preview_id=p['id']))
  self.assertFalse(self.b.paper['trades']);self.assertEqual(self.req.posts,0)
