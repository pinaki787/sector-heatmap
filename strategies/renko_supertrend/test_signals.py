import copy
import json
import math
from pathlib import Path
import random
import unittest
from .signals import Engine, series, settings
from .source_reference import reference


def candle(i, close, high=None, low=None):
    return dict(timestamp=1791240000 + i*60, open=close, high=high if high is not None else close+1,
                low=low if low is not None else close-1, close=close, volume=1)


class SourceMathTests(unittest.TestCase):
    def test_source_text_arithmetic_parity_over_sequential_regimes(self):
        rng=random.Random(61006);price=1000;rows=[]
        for i in range(430):
            width=2 if i<100 else 70 if i<190 else .08 if i<300 else 15
            price=max(200,price+rng.uniform(-width,width));rows.append(candle(i,price,price+width,price-width))
        names=dict(hostAtr='host_atr',regimeAtr='regime_atr',lowAtr='low_atr',volatilityRatio='volatility_ratio',
                   effectiveFactor='effective_factor',autoBox='auto_box',box='box',rc='synthetic_close',ro='synthetic_open',
                   syntheticAtr='synthetic_atr',upper='upper',lower='lower',st='supertrend',direction='pine_direction')
        for config in ({},dict(brick_mode='Manual',manual_brick=12.8),dict(atr_length=25),dict(factor=.1)):
            cfg=settings(config);expected=reference(rows,cfg);actual=series(rows,cfg)
            for i,(a,e) in enumerate(zip(actual,expected)):
                for pine,python in names.items():
                    if e[pine] is None:self.assertIsNone(a[python],(i,pine))
                    else:self.assertAlmostEqual(a[python],e[pine],places=10,msg=str((i,pine,config)))
                self.assertEqual((a['buy_signal'],a['sell_signal']),(e['buy'],e['sell']),(i,config))
    def test_hand_calculated_manual_sequence_and_reversals(self):
        rows = series([candle(i, p) for i, p in enumerate([100,120,121,80,100])],
                      dict(atr_length=1, factor=.1, brick_mode='Manual', manual_brick=10))
        self.assertEqual([r['synthetic_close'] for r in rows], [100,120,120,80,100])
        self.assertEqual([r['synthetic_open'] for r in rows], [100,100,100,120,80])
        self.assertEqual([r['synthetic_atr'] for r in rows], [0,20,20,40,20])
        self.assertEqual([r['supertrend'] for r in rows], [100,108,108,104,88])
        self.assertEqual([r['cross_direction'] for r in rows], [None,'BULLISH',None,'BEARISH','BULLISH'])

    def test_host_atr_sma_seed_and_no_extra_warmup(self):
        rows = series([candle(i,100,101,99) for i in range(16)])
        self.assertEqual([r['host_atr'] for r in rows[:5]], [None,None,None,None,2])
        self.assertIsNone(rows[3]['box'])
        self.assertEqual(rows[4]['box'],2)
        self.assertIsNone(rows[13]['regime_atr'])
        self.assertEqual(rows[14]['regime_atr'],2)
        self.assertEqual(rows[0]['supertrend'],100)
        self.assertEqual(rows[0]['pine_direction'],1)

    def test_synthetic_state_updates_on_host_without_new_brick(self):
        rows=series([candle(i,p) for i,p in enumerate([100,120,121,121])],
                    dict(atr_length=5,brick_mode='Manual',manual_brick=10))
        self.assertEqual(rows[2]['steps'],0)
        self.assertEqual(rows[2]['synthetic_tr'],20)
        self.assertAlmostEqual(rows[1]['synthetic_atr'],4)
        self.assertAlmostEqual(rows[2]['synthetic_atr'],7.2)
        self.assertAlmostEqual(rows[3]['synthetic_atr'],9.76)

    def test_long_atr_warmup_retains_pine_na_ratio(self):
        rows=series([candle(i,100) for i in range(32)],dict(atr_length=30))
        self.assertEqual(rows[13]['volatility_ratio'],1)
        self.assertIsNone(rows[14]['volatility_ratio'])
        self.assertIsNone(rows[28]['box'])
        self.assertIsNotNone(rows[29]['box'])

    def test_volatility_regimes_and_tick_floor(self):
        rows=series([candle(i,100,100+(1 if i<40 else 30),99 if i<40 else 70) for i in range(60)] +
                    [candle(i,100,100.01,99.99) for i in range(60,140)])
        high=next(r for r in rows if r['volatility_ratio'] is not None and r['volatility_ratio']>1.2)
        low=next(r for r in rows if r['volatility_ratio'] is not None and r['volatility_ratio']<.8)
        self.assertEqual(high['effective_factor'],4)
        self.assertAlmostEqual(high['box'],high['host_atr']*1.5)
        self.assertEqual(low['effective_factor'],2.5)
        self.assertAlmostEqual(low['box'],max(.05,low['low_atr']*.7))
        self.assertEqual(rows[-1]['box'],.05)

    def test_adx_is_chart_based_strict_gate_and_no_replayed_reversal(self):
        cfg=dict(atr_length=1,factor=.1,brick_mode='Manual',manual_brick=10,use_adx=True,adx_length=1,adx_smoothing=1,adx_threshold=100)
        rows=series([candle(0,100),candle(1,120),candle(2,121)],cfg)
        self.assertEqual(rows[1]['adx'],100)
        self.assertEqual(rows[1]['pine_direction'],-1)
        self.assertFalse(rows[1]['buy_signal'])
        engine=Engine({**cfg,'adx_threshold':20})
        engine.update(candle(0,100))
        engine.config['adx_threshold']=100
        engine.update(candle(1,120))
        engine.config['adx_threshold']=20
        later=engine.update(candle(2,121))
        self.assertTrue(later['signal_allowed'])
        self.assertFalse(later['buy_signal'])

    def test_adx_warmup_is_di_then_smoothing(self):
        rows=series([candle(i,100+i) for i in range(32)],dict(use_adx=True))
        self.assertTrue(all(r['adx'] is None for r in rows[:27]))
        self.assertEqual(rows[27]['adx'],100)

    def test_serialized_resume_matches_single_pass_at_every_field(self):
        rng=random.Random(82026);price=1000;rows=[]
        for i in range(900):
            price=max(100,price+rng.uniform(-30,30));rows.append(candle(i,price,price+rng.uniform(1,45),price-rng.uniform(1,45)))
        for cfg in ({},dict(brick_mode='Manual',manual_brick=12.8,use_adx=True),dict(atr_length=25,adx_length=3,adx_smoothing=7)):
            engine=Engine(cfg);first=[engine.update(c) for c in rows[:377]]
            resumed=Engine(cfg,state=json.loads(json.dumps(engine.state)))
            actual=first+[resumed.update(c) for c in rows[377:]]
            self.assertEqual(actual,series(rows,cfg))

    def test_forming_duplicates_and_nonchronological_state_fail_closed(self):
        a=candle(0,100);b=candle(1,110)
        self.assertEqual(series([a,b,{**candle(2,200),'is_forming':True}]),series([a,b]))
        self.assertEqual(series([b,a,a]),series([a,b]))
        with self.assertRaisesRegex(ValueError,'Conflicting'):series([a,{**a,'volume':2}])
        e=Engine();e.update(a)
        with self.assertRaisesRegex(ValueError,'exactly once'):e.update(a)

    def test_defaults_and_input_validation_match_source_ranges(self):
        self.assertEqual(settings({}),dict(atr_length=5,factor=3.0,brick_mode='Auto',manual_brick=12.8,use_adx=False,adx_threshold=20.0,adx_length=14,adx_smoothing=14,widening_window=2,rsi_slope_enabled=True,retest_enabled=False,retest_engulfing=True,retest_harami=True,retest_star=True))
        for cfg in (dict(atr_length=True),dict(manual_brick=0),dict(factor=float('nan')),dict(adx_threshold=101),dict(use_adx='false')):
            with self.assertRaises(ValueError):settings(cfg)
        self.assertEqual(settings(dict(adx_threshold=0))['adx_threshold'],0)


if __name__=='__main__':unittest.main()
