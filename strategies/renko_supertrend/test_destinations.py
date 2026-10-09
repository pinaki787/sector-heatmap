import tempfile
import unittest
from pathlib import Path
from . import destinations, preferences
from .signals import series
from .exit_indicators import reason

class DestinationTests(unittest.TestCase):
    def test_switch_combinations_are_isolated(self):
        for key in destinations.RULES:
            for strategy,indicator in ((True,False),(False,True),(True,True),(False,False)):
                cfg={key:strategy,key+'_indicator':indicator}
                self.assertEqual(destinations.chart(cfg)[key],indicator)
                self.assertEqual(cfg[key],strategy)
    def test_exit_strategy_and_chart_are_independent(self):
        sig={'close':90,'ema30':100}
        for strategy,indicator in ((True,False),(False,True),(True,True),(False,False)):
            cfg={'supertrend_exit_enabled':False,'ema_slow_exit_enabled':strategy,'ema_slow_exit_enabled_indicator':indicator}
            self.assertEqual(reason(cfg,sig,'BULLISH') is not None,strategy)
            self.assertEqual(reason(destinations.chart(cfg),sig,'BULLISH') is not None,indicator)
    def test_entry_replay_is_independent(self):
        bars=[dict(timestamp=1800000000+i*300,open=p,high=p+1,low=p-1,close=p,volume=1) for i,p in enumerate([100,102,104,106,108,110])]
        base=dict(supertrend_enabled=False,ema_fast_enabled=False,ema_slow_enabled=False,ema_widening_enabled=False,rsi_slope_enabled=False,supertrend_exit_enabled=False,session_deadline=None)
        for strategy,indicator in ((True,False),(False,True),(True,True),(False,False)):
            cfg={**base,'ema_fast_enabled':strategy,'ema_fast_enabled_indicator':indicator}
            self.assertEqual(any(r['entry_buy_signal'] for r in series(bars,cfg)),strategy)
            self.assertEqual(any(r['entry_buy_signal'] for r in series(bars,destinations.chart(cfg))),indicator)
    def test_preferences_and_legacy_identity(self):
        self.assertEqual(destinations.settings({'supertrend_enabled':True}),{})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            values={'supertrend-enabled':False,'supertrend-enabled-indicator':True,'ema-slow-exit-enabled':True,'ema-slow-exit-enabled-indicator':False}
            preferences.write(path,{'settings':values},123)
            self.assertEqual(preferences.read(path)['settings'],values)
            with self.assertRaises(ValueError):preferences.write(path,{'settings':{'supertrend-enabled-indicator':'true'}},124)
            self.assertEqual(preferences.read(path)['settings'],values)

    def test_historical_exit_markers_follow_chart_destination(self):
        bars=[dict(timestamp=1800000000+i*300,open=p,high=p+1,low=p-1,close=p,volume=1) for i,p in enumerate([100,120,140,80,60])]
        base=dict(supertrend_enabled=False,ema_fast_enabled=True,ema_slow_enabled=False,ema_widening_enabled=False,rsi_slope_enabled=False,supertrend_exit_enabled=False,ema_exit_enabled=False,session_deadline=None)
        for strategy,indicator in ((True,False),(False,True),(True,True),(False,False)):
            cfg={**base,'ema_slow_exit_enabled':strategy,'ema_slow_exit_enabled_indicator':indicator}
            def exits(config):return any((r.get('lifecycle_event') or '').endswith('EXIT') for r in series(bars,config))
            self.assertEqual(exits(cfg),strategy);self.assertEqual(exits(destinations.chart(cfg)),indicator)

    def test_supply_demand_chart_exit_uses_confirmed_prior_zone_only(self):
        from . import zone_target
        prices=[100,101]+[100]*14+[110,98,97,100,109]
        bars=[dict(timestamp=1800000000+i*300,open=p,high=p+1,low=p-1,close=p,volume=1) for i,p in enumerate(prices)]
        bars[16].update(high=112,low=109);bars[20].update(high=111,low=108)
        timeline=[];zone_target.zones(bars,timeline)
        self.assertIsNotNone(timeline[18]['supply'])
        cfg=dict(supertrend_enabled=False,ema_fast_enabled=True,ema_slow_enabled=False,ema_widening_enabled=False,rsi_slope_enabled=False,supertrend_exit_enabled=False,ema_exit_enabled=False,session_deadline=None,timeframe='5 minutes',_chart_zone_rows=bars)
        without=series(bars,{**cfg,'chart_zone_target_enabled':False})
        with_zone=series(bars,{**cfg,'chart_zone_target_enabled':True})
        self.assertFalse(any((r.get('lifecycle_reason') or '').startswith('SD_5M') for r in without))
        exits=[r for r in with_zone if (r.get('lifecycle_reason') or '').startswith('SD_5M')]
        self.assertEqual(len(exits),1);self.assertEqual(exits[0]['timestamp'],bars[20]['timestamp'])
        self.assertEqual(exits[0]['lifecycle_reason'],'SD_5M_ZONE_REJECTION')
        self.assertEqual(zone_target.assess(bars,{'direction':'BULLISH','opened_at':bars[2]['timestamp']},bars[-1]['timestamp']+300),zone_target.assess_known(bars[-1],bars[-2],timeline[-2],{'direction':'BULLISH','opened_at':bars[2]['timestamp']},bars[-1]['timestamp']+300))

    def test_optional_chart_entry_filters_and_future_htf_are_isolated(self):
        start=1800000000+31*300
        bars=[dict(timestamp=start+i*60,open=p,high=p+1,low=p-1,close=p,volume=1) for i,p in enumerate([100,102,104])]
        base=dict(supertrend_enabled=False,ema_fast_enabled=True,ema_slow_enabled=False,ema_widening_enabled=False,rsi_slope_enabled=False,supertrend_exit_enabled=False,session_deadline=None,timeframe='1 minute')
        for extra in ({'ema_proximity_enabled':True,'ema_proximity_mode':'POINTS','ema_proximity_distance':.001},{'market_structure_enabled':True}):
            self.assertTrue(any(r['entry_buy_signal'] for r in series(bars,{**base,**extra,'chart_entry_guards':False})))
            self.assertFalse(any(r['entry_buy_signal'] for r in series(bars,{**base,**extra,'chart_entry_guards':True})))
        def source(prices):return [dict(timestamp=1800000000+i*300,open=p,high=p+1,low=p-1,close=p,volume=1) for i,p in enumerate(prices)]
        cfg={**base,'chart_entry_guards':True,'higher_timeframe_enabled':True,'supertrend_timeframe':'5 minutes'}
        agrees=source([50+i for i in range(34)])
        self.assertTrue(any(r['entry_buy_signal'] for r in series(bars,{**cfg,'_chart_higher_rows':agrees})))
        future_only=source([200-i for i in range(31)]+[500,510,520])
        self.assertFalse(any(r['entry_buy_signal'] for r in series(bars,{**cfg,'_chart_higher_rows':future_only})))
        self.assertFalse(any(r['entry_buy_signal'] for r in series(bars,cfg)))
