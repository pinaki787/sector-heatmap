import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from ema_crossover.runner import Runner, configuration
from ema_crossover.signals import exit_on_close


class Broker:
    def __init__(self):
        self.enabled=True; self.sent=[]; self.cancelled=[]; self.book=[]; self.positions_qty=0; self.fail_send=False
        self.price=10; self.last_close=110; self.now=datetime(2026,10,1,10,0,5,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
    def live_enabled(self):return self.enabled
    def validate_config(self,c):return {'broker':'FAKE'}
    def start(self):pass
    def stop(self):pass
    def candles(self,c):
        return [dict(timestamp=self.now-5-(101-i)*300,open=p,high=p,low=p,close=p,volume=1) for i,p in enumerate([(101-(i%2) if self.last_close>=100 else 100+(i%2)) for i in range(100)]+[self.last_close])]
    def resolve(self,c,d):return {'symbol':'NSE:TESTCE','lot_size':10,'quantity_multiplier':1}
    def quote(self,s):return {'bid':self.price,'ask':self.price}
    def order(self,s,q,side,quote):return dict(symbol=s,qty=q,side=side,limitPrice=0,productType='MARGIN',type=2)
    def validate_order(self,o):pass
    def preflight(self,o,c):pass
    def place(self,o):
        self.sent.append(o)
        if self.fail_send:raise TimeoutError('uncertain')
        return {'s':'ok','id':'O'+str(len(self.sent))}
    def cancel(self,oid):self.cancelled.append(oid)
    def orders(self):return self.book
    def reconcile_position(self,s,q):
        if q!=self.positions_qty:raise ValueError('position mismatch')


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.b=Broker();self.r=Runner(self.b,Path(self.tmp.name)/'state.json',lambda:self.b.now)
        self.addCleanup(self.r.release)
        self.c=dict(strategy='RSI_BASED_EMA_V1',underlying='NSE:NIFTY50-INDEX',timeframe='5 minutes',rsi_length=14,sma_length=14,lots=1,mode='LIVE',max_premium=1000,daily_budget=2000,label='RSI based EMA')
    def start(self):
        p=self.r.preview(self.c);self.r.start({'preview_id':p['id'],'confirmation':p['confirmation']},background=False)
        self.r.state['started_at']=self.b.now-10;self.r.state['eligible_since']=self.b.now-10
    def fill(self,filled=10,status=2):
        p=self.r.state['pending'];self.b.book=[dict(p['order'],id=p['id'],status=status,filledQty=filled,tradedPrice=10)]
        self.b.positions_qty=filled
    def test_confirmation_gate_and_expiry(self):
        p=self.r.preview(self.c)
        with self.assertRaises(ValueError):self.r.start({'preview_id':p['id'],'confirmation':'yes'},False)
        self.b.now+=121
        with self.assertRaises(ValueError):self.r.start({'preview_id':p['id'],'confirmation':p['confirmation']},False)
        self.assertEqual(self.b.sent,[])
    def test_mcx_premium_and_loss_budget_use_multiplier(self):
        self.b.resolve=lambda c,d:dict(symbol='MCX:TESTCE',lot_size=1,quantity_multiplier=10)
        self.c['max_premium']=50
        self.start()
        with self.assertRaisesRegex(ValueError,'Full option premium'):
            self.r.step()
        self.assertEqual(self.b.sent,[])
        self.r.state['config']['max_premium']=None
        self.r.state['config']['daily_budget']=120
        self.b.now+=300
        self.r.state['losses']['2026-10-01']=30
        with self.assertRaisesRegex(ValueError,'Full option premium'):
            self.r.step()
        self.assertEqual(self.b.sent,[])

    def test_mcx_partial_exit_pnl_and_losses(self):
        self.b.resolve=lambda c,d:dict(symbol='MCX:TESTCE',lot_size=1,quantity_multiplier=10)
        self.c['lots']=2
        self.start();self.r.step();self.fill(2);self.r.step()
        self.assertEqual(self.b.sent[0]['qty'],2)
        self.assertEqual(self.r.state['position']['quantity_multiplier'],10)
        self.b.price=5
        self.assertEqual(self.r.snapshot()['pnl']['unrealized'],-100)
        self.b.now+=300;self.b.last_close=80;self.r.step()
        p=self.r.state['pending']
        self.b.book=[dict(p['order'],id=p['id'],status=1,filledQty=1,tradedPrice=5)]
        self.b.positions_qty=1;self.r.step()
        self.assertEqual(self.r.state['position']['quantity'],1)
        self.assertEqual(self.r.state['realized_pnl'],-50)
        self.assertEqual(sum(self.r.state['losses'].values()),50)

    def test_nifty_quantity_is_not_multiplied_twice(self):
        self.b.resolve=lambda c,d:dict(symbol='NSE:NIFTY26O0622450CE',lot_size=65,quantity_multiplier=1)
        self.start();self.r.step();self.fill(65);self.r.step()
        self.assertEqual(self.b.sent[0]['qty'],65)
        self.b.price=5
        self.assertEqual(self.r.snapshot()['pnl']['unrealized'],-325)
        self.b.now+=300;self.b.last_close=80;self.r.step()
        p=self.r.state['pending']
        self.b.book=[dict(p['order'],id=p['id'],status=2,filledQty=65,tradedPrice=5)]
        self.b.positions_qty=0;self.r.step()
        self.assertEqual(self.r.state['realized_pnl'],-325)
        self.assertEqual(sum(self.r.state['losses'].values()),325)
    def test_acceptance_not_fill_and_duplicate_block(self):
        self.start();self.r.step();self.assertIsNone(self.r.state['position']);self.assertEqual(len(self.b.sent),1)
        self.fill();self.r.step();self.assertEqual(self.r.state['position']['quantity'],10)
        self.r.step();self.assertEqual(len(self.b.sent),1)
    def test_unknown_submission_survives_restart(self):
        self.start();self.b.fail_send=True;self.r.step();self.assertEqual(self.r.state['status'],'ORDER_STATUS_UNKNOWN')
        self.r.release();recovered=Runner(self.b,self.r.path,lambda:self.b.now)
        self.assertEqual(recovered.state['status'],'RECOVERY_REQUIRED');self.assertIsNotNone(recovered.state['pending'])
        self.assertFalse(recovered.state['running'])
        with self.assertRaises(ValueError):self.r.step()
        self.assertEqual(len(self.b.sent),1)
    def test_partial_cancelled_fill_retains_actual_exposure(self):
        self.start();self.r.step();self.fill(5,1);self.r.step()
        self.assertEqual(self.r.state['position']['quantity'],5)
    def test_stop_cancels_pending_but_does_not_drop_it(self):
        self.start();self.r.step();self.fill(0,6);self.r.stop();self.r.step()
        self.assertEqual(self.b.cancelled,['O1']);self.assertIsNotNone(self.r.state['pending'])
        self.r.step();self.assertEqual(self.b.cancelled,['O1'])
    def test_failed_preflight_cross_is_not_replayed_after_recovery(self):
        self.start()
        resolve = self.b.resolve
        def unavailable(config, direction):
            raise ValueError('FYERS stream has no tick')
        self.b.resolve = unavailable
        with self.assertRaisesRegex(ValueError, 'no tick'):
            self.r.step()
        self.assertEqual(self.r.state['last_signal']['direction'], 'BULLISH')
        self.assertEqual(self.r.state['seen'], [])
        self.assertEqual(self.r.state.get('trades_used', 0), 0)
        self.assertEqual(self.b.sent, [])
        self.b.resolve = resolve
        self.r.step()
        self.assertEqual(len(self.b.sent),0)
        self.b.now+=300
        self.r.step()
        self.assertEqual(len(self.b.sent), 1)
        self.fill()
        self.r.step()
        self.r.step()
        self.assertEqual(len(self.b.sent), 1)

    def test_activation_ignores_old_completed_cross(self):
        p=self.r.preview(self.c);self.r.start({'preview_id':p['id'],'confirmation':p['confirmation']},False)
        self.r.step();self.assertEqual(len(self.b.sent),0)
        self.b.now+=300;self.r.step();self.assertEqual(len(self.b.sent),1)
    def test_full_premium_cap_and_daily_budget(self):
        self.c['max_premium']=50;self.start()
        with self.assertRaises(ValueError):self.r.step()
        self.assertEqual(self.b.sent,[])
    def test_external_position_change_blocks_sell(self):
        self.start();self.r.step();self.fill();self.r.step();self.b.positions_qty=0;self.b.price=5
        with self.assertRaises(ValueError):self.r.step()
        self.assertEqual(len(self.b.sent),1)
    def test_paper_never_submits(self):
        self.c['mode']='PAPER';self.start();self.r.step()
        self.assertEqual(self.b.sent,[]);self.assertEqual(self.r.state['position']['quantity'],10)
    def test_exit_retained_until_confirmed(self):
        self.start();self.r.step();self.fill();self.r.step();self.b.price=5;self.b.now+=300;self.b.last_close=80;self.r.step()
        self.assertEqual(self.r.state['position']['quantity'],10);self.assertEqual(self.b.sent[-1]['side'],-1)
        p=self.r.state['pending'];self.b.book=[dict(p['order'],id=p['id'],status=2,filledQty=10,tradedPrice=5)]
        self.b.positions_qty=0;self.r.step();self.assertIsNone(self.r.state['position'])
    def test_runtime_gate_disabled_never_places(self):
        self.b.enabled=False
        with self.assertRaises(ValueError):self.r.preview(self.c)
        self.assertEqual(self.b.sent,[])
    def test_intrabar_premium_drop_does_not_exit(self):
        self.start();self.r.step();self.fill();self.r.step();self.b.price=1;self.r.step()
        self.assertEqual(len(self.b.sent),1)
        self.assertIsNone(self.r.state['pending'])
    def test_no_timed_exit_without_ema10_close(self):
        self.start();self.r.step();self.fill();self.r.step();self.b.now+=6*3600;self.r.step()
        self.assertEqual(len(self.b.sent),1)
    def test_put_exit_uses_later_close_above_ema10(self):
        self.b.last_close=80;self.start();self.r.step();self.fill();self.r.step()
        self.assertEqual(self.r.state['position']['direction'],'BEARISH')
        self.b.now+=300;self.b.last_close=110;self.r.step()
        self.assertEqual(self.r.state['pending']['reason'],'RSI_CLOSE_EXIT')
    def test_stale_completed_bar_cannot_enter(self):
        data=self.b.candles(self.c);self.b.candles=lambda c:data
        self.b.now+=301;self.start();self.r.step();self.assertEqual(self.b.sent,[])
    def test_exit_candle_cannot_immediately_reenter(self):
        self.c['mode']='PAPER';self.start();self.r.step()
        self.b.now+=300;self.b.last_close=80;self.r.step();self.assertIsNone(self.r.state['position'])
        self.r.step();self.assertIsNone(self.r.state['position'])
        self.b.now+=300;self.r.step();self.assertEqual(self.r.state['position']['direction'],'BEARISH')

    def test_corrupt_saved_state_blocks_activation(self):
        self.r.path.write_text('{bad')
        other=Runner(self.b,self.r.path,lambda:self.b.now)
        with self.assertRaises(ValueError):other.preview(self.c)
        with self.assertRaises(ValueError):other.stop()
        self.assertEqual(self.r.path.read_text(),'{bad')

    def test_account_change_invalidates_preview(self):
        self.b.validate_config=lambda c: {'broker':'FAKE','account_identity':'A'}
        p=self.r.preview(self.c)
        self.b.validate_config=lambda c: {'broker':'FAKE','account_identity':'B'}
        with self.assertRaises(ValueError):self.r.start({'preview_id':p['id'],'confirmation':p['confirmation']},False)
        self.assertEqual(self.b.sent,[])
    def test_explicit_rejection_stops_without_retry(self):
        self.start()
        self.b.place=lambda order: {'s':'error','code':-300,'message':'Rejected'}
        self.r.step()
        self.assertFalse(self.r.state['running'])
        self.assertIsNone(self.r.state['pending'])
        self.assertEqual(self.r.state['status'],'ORDER_REJECTED')

    def test_second_process_cannot_start(self):
        self.start();other=Runner(self.b,self.r.path,lambda:self.b.now)
        p=other.preview(self.c)
        with self.assertRaises(ValueError):other.start({'preview_id':p['id'],'confirmation':p['confirmation']},False)


    def test_limit_keeps_exit_allowed(self):
      self.c.update(mode='PAPER',max_trades=1,sma_length=30);self.start();self.r.step()
      self.assertEqual(self.r.state['trades_used'],1)
      self.b.now+=300;self.b.last_close=80;self.r.step()
      self.assertIsNone(self.r.state['position']);self.r.step();self.assertFalse(self.r.state['running'])

    def test_uncertain_entry_consumes_slot_and_survives_restart(self):
      self.b.fail_send=True;self.start();self.r.step()
      self.assertEqual(self.r.state['trades_used'],1)
      from ema_crossover.runner import Runner
      saved=Runner(self.b,self.r.path,lambda:self.b.now)
      self.assertEqual(saved.state['trades_used'],1)

    def test_custom_exit_separate(self):
      c=dict(close=105,fast=110,slow=90,exit=100)
      self.assertFalse(exit_on_close(c,'BULLISH'));self.assertTrue(exit_on_close(c,'BEARISH'))

    def test_supported_timeframes_and_invalid_fields(self):
      for t in ['1 minute','2 minutes','3 minutes','5 minutes','10 minutes','15 minutes','30 minutes','1 hour']:
       self.assertEqual(configuration(dict(self.c,timeframe=t,sma_length=30,max_trades=4))['max_trades'],4)
      for k,v in [('rsi_length',0),('sma_length',1.5),('max_trades',0),('max_trades',2.5)]:
       with self.assertRaises(ValueError):configuration(dict(self.c,**{k:v}))

    def test_stop_squares_off_without_waiting_for_signal(self):
      self.c.update(mode='PAPER',max_premium=None,daily_budget=None);self.start();self.r.step()
      self.b.price=12
      self.assertEqual(self.r.snapshot()['pnl']['unrealized'],20)
      self.r.stop();self.r.step()
      self.assertIsNone(self.r.state['position'])
      self.assertEqual(self.r.snapshot()['pnl']['realized'],20)
      self.r.step();self.assertFalse(self.r.state['running'])

    def test_stop_after_partial_fill_exits_owned_quantity(self):
      self.start();self.r.step();self.r.stop();self.fill(5,1);self.r.step()
      self.assertEqual(self.r.state['position']['quantity'],5)
      self.r.step();self.assertEqual(self.b.sent[-1]['side'],-1)
      self.assertEqual(self.b.sent[-1]['qty'],5)

    def test_optional_money_limits_and_validation(self):
      c=configuration(dict(self.c,max_premium=None,daily_budget=None))
      self.assertIsNone(c['max_premium']);self.assertIsNone(c['daily_budget'])
      for key in ['max_premium','daily_budget']:
       for value in [0,-1,float('nan'),float('inf')]:
        with self.assertRaises(ValueError):configuration(dict(self.c,**{key:value}))

    def test_order_history_retains_fills_after_exit(self):
        self.c['mode']='PAPER';self.start();self.r.step()
        self.r.stop();self.r.step()
        rows=self.r.snapshot()['order_history']
        self.assertEqual([r['side'] for r in rows],['BUY','SELL'])
        self.assertTrue(all(r['filled']==10 and r['remaining']==0 and r['status']=='FILLED' for r in rows))
        self.assertIsNone(self.r.state['position'])
        saved=Runner(self.b,self.r.path,lambda:self.b.now)
        self.assertEqual(saved.state['order_history'],rows)

    def test_ema_filter_preserves_fill_lifecycle_and_completed_flip_exit(self):
        self.c.update(ma_type='EMA',ma_length=14)
        self.start();self.r.step();self.fill();self.r.step()
        self.assertEqual(self.r.state['config']['label'],'RSI based EMA')
        self.assertEqual(self.r.state['position']['direction'],'BULLISH')
        self.c['ma_type']='SMA'  # Editing the caller cannot change the frozen run.
        self.assertEqual(self.r.state['config']['ma_type'],'EMA')
        self.b.now+=300;self.b.last_close=80;self.r.step()
        self.assertEqual(self.r.state['pending']['reason'],'RSI_CLOSE_EXIT')
        self.assertEqual(self.b.sent[-1]['side'],-1)

if __name__=='__main__':unittest.main()
