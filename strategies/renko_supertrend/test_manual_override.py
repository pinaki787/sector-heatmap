"""Explicit override lifecycle tests; temporary state and fake brokers only."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from . import test_runner as fixtures
from .test_delta_integration import NativeFake, config
from .delta_runner import DeltaRunner
from pathlib import Path


class OverrideTests(unittest.TestCase):
    setUp=fixtures.RenkoLifecycleTests.setUp
    append=fixtures.RenkoLifecycleTests.append

    def arm(self,**changes):
        self.c.update(changes)
        self.r.activate(dict(self.c,configuration_revision=self.r.runtime_revision),background=False)

    def payload(self,direction='BULLISH',**changes):
        c=self.r.state['config'] or {}
        return dict(override_revision='explicit-entry-v1',run_id=self.r.state.get('run_id'),
                    underlying=c.get('underlying'),timeframe=c.get('timeframe'),mode=c.get('mode'),
                    broker=c.get('broker','FYERS'),direction=direction,request_id='override-test-0001',**changes)

    def test_both_directions_bypass_entry_filters_without_fake_signal(self):
        for direction in ['BULLISH','BEARISH']:
            with self.subTest(direction=direction):
                if self.r.state.get('position'):
                    self.r.state['position']=None;self.r.state['pending']=None
                if not self.r.state['running']:self.arm(use_adx=True,adx_threshold=100,rsi_slope_enabled=True,ema_proximity_enabled=True,ema_proximity_distance=.00001,ema_exit_enabled=False)
                p=self.payload(direction);p['request_id']='override-test-'+direction
                self.r.signal();before=deepcopy(self.r.state['last_signal'])
                self.assertFalse(before['signal_allowed'])
                result=self.r.override_entry(p)
                self.assertEqual(result['position']['direction'],direction)
                self.assertEqual(result['position']['entry_mode'],'MANUAL_OVERRIDE')
                self.assertEqual(result['position']['entry_indicator_snapshot']['reason'],'MANUAL_OVERRIDE_ENTRY')
                self.assertEqual(self.r.state['last_signal'],before)
                self.assertEqual(self.b.sent,[])

    def test_duplicate_consumed_after_exit_does_not_reenter(self):
        self.arm();p=self.payload();self.r.override_entry(p)
        used=self.r.state['trades_used'];orders=len(self.r.state['order_history'])
        self.r.state['position']=None
        self.r.override_entry(p)
        self.assertIsNone(self.r.state['position']);self.assertEqual(self.r.state['trades_used'],used)
        self.assertEqual(len(self.r.state['order_history']),orders)

    def test_current_bar_confirmed_exit_is_managed(self):
        self.arm();self.r.override_entry(self.payload())
        self.append(80);self.r.step()
        self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.r.state['order_history'][-1]['reason'],'EMA10_CONFIRMED_BREACH')
        self.assertEqual(self.b.sent,[])

    def test_identity_direction_and_runner_guards(self):
        self.arm();p=self.payload()
        for key,value in [('run_id','old-run'),('underlying','OTHER'),('mode','LIVE'),('broker','OTHER'),('timeframe','5 minutes'),('direction',''),('request_id','bad')]:
            q={**p,key:value}
            with self.subTest(key=key),self.assertRaises(ValueError):self.r.override_entry(q)
        for key,value in [('running',False),('accepting_entries',False),('position',{'symbol':'X'}),('pending',{'tag':'X'}),('squareoff_requested',True),('trades_used',self.r.state['config']['max_trades'])]:
            old=self.r.state.get(key);self.r.state[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.r.override_entry(p)
            self.r.state[key]=old
        self.assertEqual(self.b.sent,[]);self.assertFalse(self.r.state.get('order_history'))

    def test_freshness_risk_proximity_and_cutoff_are_not_execution_bypasses(self):
        self.arm();p=self.payload();cfg=self.r.state['config']
        live=self.b.live_price
        self.b.live_price=lambda c,now:(100,now-16)
        with self.assertRaisesRegex(ValueError,'Fresh'):self.r.override_entry(p)
        self.b.live_price=live
        for change,error in [({'max_premium':1},'premium'),({'daily_budget':1},'premium'),({'spot_stop':130},'stop')]:
            old=deepcopy(cfg);cfg.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.r.override_entry(p)
            cfg.clear();cfg.update(old)
        with patch.object(self.r,'sideways_entry_gate',return_value=False):
            with self.assertRaisesRegex(ValueError,'Sideways'):self.r.override_entry(p)
        cfg['session_deadline']='09:59'
        with self.assertRaisesRegex(ValueError,'session/cutoff'):self.r.override_entry(p)
        self.assertFalse(self.r.state.get('order_history'))

    def test_capital_spread_and_broker_validation_remain(self):
        self.arm();p=self.payload()
        self.r.state['config']['paper_capital_inr']=1
        with self.assertRaises(ValueError):self.r.override_entry(p)
        self.r.state['config']['paper_capital_inr']=100000
        self.b.quote=lambda symbol:dict(bid=1,ask=10)
        with self.assertRaisesRegex(ValueError,'spread'):self.r.override_entry(p)
        self.b.quote=lambda symbol:dict(bid=10,ask=10)
        self.b.validate_order=lambda order:(_ for _ in ()).throw(ValueError('invalid order'))
        with self.assertRaisesRegex(ValueError,'invalid order'):self.r.override_entry(p)
        self.assertEqual(self.r.state['override_requests'][-1]['status'],'BLOCKED_OR_UNKNOWN')
        self.r.override_entry(p);self.assertFalse(self.r.state.get('order_history'))

    def test_live_gate_and_preflight_held_without_real_broker(self):
        self.arm(mode='LIVE');p=self.payload();self.b.live_enabled=lambda:False
        with self.assertRaisesRegex(ValueError,'gate'):self.r.override_entry(p)
        self.b.live_enabled=lambda:True
        self.b.preflight=lambda *a:(_ for _ in ()).throw(ValueError('ownership or affordability'))
        with self.assertRaisesRegex(ValueError,'ownership'):self.r.override_entry(p)
        self.assertEqual(self.b.sent,[])

    def test_same_exit_bar_and_private_authorization(self):
        self.arm();self.r.state['last_exit_bar']=int(self.b.now//60)*60
        with self.assertRaisesRegex(ValueError,'same exit candle'):self.r.override_entry(self.payload())
        with self.assertRaisesRegex(ValueError,'authorization expired'):
            self.r.validate_entry_authorization(dict(entry_mode='MANUAL_OVERRIDE',override_request_id='forged',entry_event_at=self.b.now))

    def test_real_forming_path_bypasses_entry_ema_and_proximity_but_keeps_exits(self):
        self.b.forming=lambda *a:None
        self.arm(ema_exit_enabled=True,ema_proximity_enabled=True,ema_proximity_distance=.0001)
        self.r.override_entry(self.payload('BEARISH'))
        self.assertEqual(self.r.state['position']['direction'],'BEARISH')
        self.assertTrue(self.r.state['config']['ema_exit_enabled'])
        self.assertTrue(self.r.exit_is_later(dict(timestamp=self.r.state['position']['entry_signal_timestamp']),self.r.state['position']))

    def test_delta_native_quantity_continuous_and_strategy_exit(self):
        b=NativeFake();r=DeltaRunner(b,Path(self.tmp.name)/'delta.json',lambda:b.now);self.addCleanup(r.release)
        r.activate(dict(config(),carry_policy='CONTINUOUS',configuration_revision=r.runtime_revision),background=False)
        c=r.state['config'];p=dict(override_revision='explicit-entry-v1',run_id=r.state['run_id'],underlying='BTCUSD',broker='DELTA_INDIA',mode='PAPER',timeframe='1 minute',direction='BULLISH',request_id='delta-override-0001')
        r.override_entry(p)
        self.assertEqual(r.state['position']['quantity_multiplier'],.001)
        self.assertEqual(r.state['position']['entry_mode'],'MANUAL_OVERRIDE')
        b.now+=60;b.rows.append({**b.rows[-1],'timestamp':b.rows[-1]['timestamp']+60,'open':80,'high':80,'low':80,'close':80})
        r.step();self.assertIsNone(r.state['position']);self.assertEqual(b.sent,[])

    def test_simultaneous_requests_and_stale_preflight_cannot_double_enter(self):
        import threading
        self.arm();p=self.payload();gate=threading.Barrier(2);results=[]
        def call():
            gate.wait()
            try:self.r.override_entry(p);results.append('ok')
            except ValueError:results.append('blocked')
        ts=[threading.Thread(target=call) for _ in range(2)]
        for t in ts:t.start()
        for t in ts:t.join()
        self.assertEqual(results,['ok','ok']);self.assertEqual(len(self.r.state['order_history']),1)
        self.assertEqual(self.r.state['trades_used'],1);self.assertEqual(self.b.sent,[])

    def test_cutoff_or_stale_tick_during_submit_still_blocks(self):
        self.arm();p=self.payload();live=self.b.live_price;calls=[0]
        def price(c,now):
            calls[0]+=1
            return live(c,now) if calls[0]==1 else (100,now-16)
        self.b.live_price=price
        with self.assertRaisesRegex(ValueError,'Fresh'):self.r.override_entry(p)
        self.assertFalse(self.r.state.get('order_history'));self.assertEqual(self.b.sent,[])
