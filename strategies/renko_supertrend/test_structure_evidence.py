import unittest
from copy import deepcopy
from .signals import Engine
from .market_structure import check
from .test_brick_basis import BASE, candles

class StructureEvidenceTests(unittest.TestCase):
    def test_each_brick_uses_host_swings_at_close_and_preserves_decisions(self):
        rows=candles([100,130,110,140,105,135,115,145,110,140,120,150,115,145,125,155])
        on=Engine({**BASE,'market_structure_enabled':True})
        off=Engine({**BASE,'market_structure_enabled':False})
        retained=[]
        for i,candle in enumerate(rows):
            result=on.update(candle); baseline=off.update(candle)
            for brick,other in zip(result['brick_events'],baseline['brick_events']):
                evidence=brick['market_structure']
                self.assertEqual(evidence,check(rows[:i+1],brick['direction'],60,candle['timestamp']+60))
                self.assertTrue(all(p['confirmed_at']<=evidence['assessed_at'] for p in evidence['highs']+evidence['lows']))
                retained.append((deepcopy(brick),brick))
                self.assertEqual({k:v for k,v in brick.items() if k!='market_structure'}, {k:v for k,v in other.items() if k!='market_structure'})
        self.assertTrue(retained)
        for original,brick in retained:self.assertEqual(original,brick)

    def test_candlestick_saves_structure_without_entry(self):
        engine=Engine({**BASE,'strategy_basis':'CANDLESTICK','chart_entry_guards':True,'market_structure_enabled':True,'ema_slow_enabled':True})
        rows=candles([100,100,100,100,100,100,100])
        for i,candle in enumerate(rows):
            result=engine.update(candle)
            self.assertIn('market_structure',result)
            self.assertEqual(result['market_structure'],check(rows[:i+1],result['market_structure']['direction'],60,candle['timestamp']+60))
            self.assertEqual(result['market_structure']['state'],'INSUFFICIENT_CONFIRMED_SWINGS')
            self.assertFalse(result['market_structure']['allowed'])

    def test_snapshot_keeps_chart_available_when_paper_valuation_is_incomplete(self):
        from unittest.mock import patch
        from .test_runner import RenkoLifecycleTests
        fixture=RenkoLifecycleTests()
        fixture.setUp()
        try:
            fixture.r.state['config']={**fixture.c,'mode':'PAPER'}
            with patch.object(fixture.r,'paper_funds',side_effect=TypeError('incomplete retained entry price')):
                snapshot=fixture.r.snapshot()
            self.assertFalse(snapshot['paper_capital']['available'])
            self.assertIn('incomplete',snapshot['paper_capital']['error'])
        finally:
            fixture.doCleanups()

    def test_explicit_chart_reference_window_does_not_expand_durable_anchor(self):
        from unittest.mock import patch
        from .session_auto import candle_source
        rows=candles([100,110,120])
        config={'history_start':rows[1]['timestamp']}
        wrapped=candle_source(lambda adapter,config:rows)
        with patch('strategies.renko_supertrend.session_auto.selected',return_value=True), patch('strategies.renko_supertrend.session_auto.prepare') as prepare:
            self.assertIs(wrapped(None,config),rows)
            self.assertEqual(prepare.call_args.args[2],rows[1:])
            wrapped(None,{})
            self.assertEqual(prepare.call_args.args[2],rows)
