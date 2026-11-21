import json
import unittest
from unittest.mock import patch
from . import line_entry
from .signals import settings

class LineEntryTests(unittest.TestCase):
    def config(self):
        return dict(underlying='TEST',timeframe='5 minutes',strategy_basis='RENKO',line_entry_enabled=True,line_entry_definition=json.dumps(dict(symbol='TEST',timeframe='5 minutes',bullish=dict(kind='horizontal',price=110),bearish=dict(kind='horizontal',price=90))))
    def signal(self,at,close,direction='BULLISH',qualified=True,**extra):
        return dict(timestamp=at,close=close,direction=direction,cross_direction=direction,entry_qualified=qualified,has_completed_brick=True,**extra)
    def gate(self,c,s):return line_entry.observe({},c,s,'run')
    def test_off_preserves_state(self):
        state={};self.assertTrue(line_entry.observe(state,{},self.signal(1,111),'run')['allowed']);self.assertEqual(state,{})
    def test_bull_close_above_and_bear_close_below(self):
        c=self.config()
        self.assertTrue(self.gate(c,self.signal(1,111))['allowed'])
        self.assertTrue(self.gate(c,self.signal(2,112))['allowed'])
        self.assertTrue(self.gate(c,self.signal(3,89,'BEARISH'))['allowed'])
        self.assertFalse(self.gate(c,self.signal(4,100))['allowed'])
        self.assertFalse(self.gate(c,self.signal(5,100,'BEARISH'))['allowed'])
    def test_touch_and_wick_do_not_qualify(self):
        c=self.config()
        for close,direction in [(110,'BULLISH'),(90,'BEARISH'),(100,'BULLISH'),(100,'BEARISH')]:
            self.assertFalse(self.gate(c,self.signal(1,close,direction,high=150,low=50))['allowed'])
    def test_existing_strategy_remains_required(self):
        c=self.config();self.assertFalse(self.gate(c,self.signal(1,111,qualified=False))['allowed'])
        s=self.signal(1,111);s['cross_direction']=None;self.assertFalse(self.gate(c,s)['allowed'])
    def test_requires_actual_completed_renko_brick(self):
        c=self.config()
        for extra in [dict(provisional=True),dict(has_completed_brick=False),dict(has_completed_brick=None)]:
            s=self.signal(1,111);s.update(extra);self.assertFalse(self.gate(c,s)['allowed'])
        c['strategy_basis']='CANDLESTICK';self.assertFalse(self.gate(c,self.signal(1,111))['allowed'])
    def test_scope_and_separate_line_validation(self):
        c=self.config();c['underlying']='OTHER';self.assertFalse(self.gate(c,self.signal(1,111))['allowed'])
        c=self.config();d=json.loads(c['line_entry_definition']);d.pop('bearish');c['line_entry_definition']=json.dumps(d)
        with self.assertRaises(ValueError):settings(c)
        c['line_entry_enabled']=False;self.assertFalse(settings(c)['line_entry_enabled'])
    def test_trend_lines_extend_at_brick_event_time(self):
        c=self.config();d=json.loads(c['line_entry_definition']);d['bullish']=dict(kind='trend',points=[dict(time=1,value=100),dict(time=2,value=110)]);c['line_entry_definition']=json.dumps(d)
        self.assertFalse(self.gate(c,self.signal(3,119))['allowed'])
        self.assertTrue(self.gate(c,self.signal(3,121))['allowed'])
    def test_invalid_lines(self):
        for raw in ['{}','[]','bad']:
            with self.assertRaises(ValueError):line_entry.settings(dict(line_entry_enabled=True,line_entry_definition=raw))
        c=self.config();d=json.loads(c['line_entry_definition']);d['bullish']['price']=float('nan');c['line_entry_definition']=json.dumps(d)
        with self.assertRaises(ValueError):settings(c)
    def test_runner_gate_and_duplicate_protection(self):
        from .runner import Runner
        r=Runner.__new__(Runner);c=self.config();c.update(session_deadline='23:55',seven_day_session=True,max_trades=5)
        r.state=dict(config=c,run_id='test',eligible_since=0,seen=[])
        r.clock=lambda:1000;r.renko_loss_entry_gate=lambda *a,**k:True;r.sideways_entry_gate=lambda:True
        r.record_entry_assessment=lambda sig,eligible,code,reason:r.state.update(assessment=code)
        r.remember_execution_signal=lambda *a:None;r.save=lambda:None;r.signal_key=lambda sig:str(sig['timestamp'])
        with patch('strategies.renko_supertrend.runner.after_cutoff',return_value=False):
            self.assertFalse(r.fresh_cross(self.signal(700,100,market_event_at=999)))
            self.assertEqual(r.state['assessment'],'WAITING_RENKO_CLOSE_AND_STRATEGY')
            s=self.signal(701,111,market_event_at=1000);self.assertTrue(r.fresh_cross(s));self.assertTrue(s['line_entry_filter']['allowed']);self.assertFalse(r.fresh_cross(s))
    def test_configuration_requires_renko_and_matching_instrument(self):
        from .runner import configuration
        base=dict(strategy='RENKO_SUPERTREND_V1',underlying='NSE:NIFTY50-INDEX',timeframe='5 minutes',lots=1,mode='PAPER',exit_policy='OPPOSITE_CONFIRMED_SIGNAL')
        line={k:v for k,v in self.config().items() if k.startswith('line_')}
        with self.assertRaisesRegex(ValueError,'Renko brick strategy'):configuration({**base,**line})
        with self.assertRaisesRegex(ValueError,'different instrument'):configuration({**base,**line,'strategy_basis':'RENKO'})
