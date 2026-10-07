"""Market cutoff and expiry behavior; fake paper broker only."""
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo
from .delta_contracts import configuration
from .delta_runner import DeltaRunner
from .runner import after_cutoff, master_session_policy
from .signals import project_lifecycle
from .test_delta_integration import NativeFake, config


def at(day,h,m=0):
    return datetime(2026,10,day,h,m,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()


class MarketCutoffTests(unittest.TestCase):
    def test_continuous_config_and_midnight_do_not_close_or_stop_entries(self):
        c=configuration(dict(config(),carry_policy='CONTINUOUS',session_deadline='23:30'))
        self.assertIsNone(c['session_deadline'])
        with tempfile.TemporaryDirectory() as d:
            b=NativeFake();r=DeltaRunner(b,Path(d)/'s.json',lambda:b.now)
            self.addCleanup(r.release)
            r.state.update(config=c,running=True,accepting_entries=True,position=dict(symbol='C-BTC',opened_at=at(6,23),expiry_epoch=at(8,17,30)))
            for now in [at(6,23,31),at(7,0),at(7,17,30)]:
                b.now=now;r.deadline()
                self.assertFalse(after_cutoff(now,c));self.assertTrue(r.state['accepting_entries'])
                self.assertFalse(r.state['position'].get('exit_requested',False))
            self.assertEqual(r.session_bounds(c),(0,1440))
            b.now=at(8,17,29);r.deadline()
            self.assertEqual(r.state['position']['exit_reason'],'CONTRACT_EXPIRY')
    def test_saved_daily_policy_still_closes_at_selected_time(self):
        with tempfile.TemporaryDirectory() as d:
            b=NativeFake();r=DeltaRunner(b,Path(d)/'s.json',lambda:b.now)
            self.addCleanup(r.release)
            r.state.update(config=configuration(config()),running=True,accepting_entries=True,position=dict(symbol='C-BTC',opened_at=at(6,20),expiry_epoch=at(8,17,30)))
            b.now=at(6,23,30);r.deadline()
            self.assertFalse(r.state['accepting_entries'])
            self.assertEqual(r.state['position']['exit_reason'],'TIMED_SQUARE_OFF_2330')
    def test_projection_continuous_crosses_midnight_but_signal_exit_remains(self):
        state={};project_lifecycle(state,at(6,23,55),'BULLISH',None,300,110,100,None)
        result=project_lifecycle(state,at(7,0),None,None,300,110,100,None)
        self.assertIsNotNone(result['projected_position'])
        result=project_lifecycle(state,at(7,0,5),None,None,300,90,100,None)
        self.assertEqual(result['lifecycle_reason'],'EMA10_CONFIRMED_BREACH')
    def test_market_specific_master_ends(self):
        for exchange,segment,symbol,end,expected in [('10','10','NSE:X-EQ','1530','15:10'),('12','10','BSE:X-A','1530','15:10'),('11','20','MCX:X','2330','23:30'),('11','20','MCX:X','2355','23:55'),('11','20','MCX:X','1700','17:00')]:
            row=['']*17;row[10]=exchange;row[11]=segment;row[9]=symbol;row[6]='0900-'+end
            self.assertEqual(master_session_policy(row)['session_deadline'],expected)


class CommodityCarryTests(unittest.TestCase):
    def test_carry_ignores_session_cutoff_and_midnight_but_keeps_exact_expiry(self):
        from .runner import Runner, configuration as cfg, commodity_expiry_exit_at
        from .test_runner import FakeBroker
        c=cfg(dict(config('MCX:CRUDEOIL26OCTFUT'),commodity_holding='CARRY_FORWARD'))
        c.update(session_open='09:00',session_deadline='23:30',master_regular_session='0900-2330')
        with tempfile.TemporaryDirectory() as d:
            b=FakeBroker();r=Runner(b,Path(d)/'s.json',lambda:b.now);self.addCleanup(r.release)
            p=dict(symbol='MCX:OPTIONCE',opened_at=at(6,20),expiry_epoch=at(9,0),quantity=20,entry_side=1)
            r.state.update(config=c,running=True,accepting_entries=True,position=p)
            for now in [at(6,23,30),at(7,0),at(7,10)]:
                b.now=now;r.deadline();self.assertFalse(p.get('exit_requested',False));self.assertFalse(after_cutoff(now,c))
            b.now=at(7,0);r.step();self.assertEqual(r.state['status'],'CARRY_FORWARD_WAITING');self.assertIs(r.state['position'],p)
            cutoff=commodity_expiry_exit_at(at(9,0),'0900-2330');self.assertEqual(cutoff,at(8,23))
            b.now=cutoff;r.deadline();self.assertEqual(p['exit_reason'],'MCX_PRE_EXPIRY_EXIT')
    def test_missing_expiry_fails_closed_and_intraday_still_squares_off(self):
        from .runner import Runner, configuration as cfg
        from .test_runner import FakeBroker
        with tempfile.TemporaryDirectory() as d:
            b=FakeBroker();r=Runner(b,Path(d)/'s.json',lambda:b.now);self.addCleanup(r.release)
            c=cfg(dict(config('MCX:CRUDEOIL26OCTFUT'),commodity_holding='CARRY_FORWARD'))
            r.state.update(config=c,running=True,accepting_entries=True,position=dict(symbol='MCX:OPTIONCE'))
            r.deadline();self.assertFalse(r.state['accepting_entries']);self.assertEqual(r.state['position']['exit_reason'],'MCX_EXPIRY_UNVERIFIED')
            c.update(commodity_holding='INTRADAY',session_deadline='23:30');r.state['position']={};b.now=at(6,23,30)
            r.state['position']=dict(symbol='MCX:OPTIONCE');r.deadline();self.assertEqual(r.state['position']['exit_reason'],'TIMED_SQUARE_OFF_2330')
    def test_cash_cnc_is_not_a_commodity_product(self):
        from .runner import configuration as cfg
        with self.assertRaises(ValueError):cfg(dict(config('MCX:CRUDEOIL26OCTFUT'),commodity_holding='CNC'))
