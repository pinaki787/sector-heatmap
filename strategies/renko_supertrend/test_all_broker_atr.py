import unittest,tempfile
from pathlib import Path
from copy import deepcopy
from . import ema_proximity as ema
from .runner import Runner
from .delta_runner import DeltaRunner
from .test_runner import FakeBroker,RenkoLifecycleTests

class AllBrokerAtrTests(unittest.TestCase):
    def test_new_start_defaults_leave_input_and_explicit_baseline_unchanged(self):
        p={'mode':'PAPER','underlying':'NSE:NIFTY50-INDEX'};before=deepcopy(p)
        out=ema.new_entry_defaults(p)
        self.assertTrue(out['ema_momentum_enabled']);self.assertEqual(out['ema_proximity_distance'],.5)
        self.assertFalse(out['intrabar_entries']);self.assertEqual(p,before)
        self.assertFalse(ema.new_entry_defaults({'ema_momentum_enabled':False})['ema_momentum_enabled'])
        # Old captured config checks do not reinterpret missing flags.
        self.assertFalse(ema.settings({})['ema_momentum_enabled'])
    def test_saved_profile_one_time_migration_and_explicit_later_choice(self):
        old={'mode':'LIVE','symbol':'MCX:CRUDEOILM26NOVFUT','ema-proximity-mode':'POINTS','ema-proximity-distance':'20','intrabar-entries':True}
        new=ema.migrate_preferences(old)
        self.assertEqual(new['mode'],'LIVE');self.assertEqual(new['symbol'],old['symbol'])
        self.assertEqual(new['ema-proximity-mode'],'ATR');self.assertEqual(new['ema-proximity-distance'],'0.5')
        self.assertFalse(new['intrabar-entries']);self.assertTrue(new['ema-momentum-enabled'])
        new['ema-momentum-enabled']=False
        self.assertEqual(ema.migrate_preferences(new),new)
        self.assertEqual(old['ema-proximity-mode'],'POINTS')
    def test_real_preview_routes_all_markets_without_arming(self):
        for broker,symbol,runner_type in [('FYERS','NSE:NIFTY50-INDEX',Runner),('DHAN','NSE:SUNTV-EQ',Runner),('MOTILAL_OSWAL','MCX:CRUDEOILM26NOVFUT',Runner),('DELTA_INDIA','BTCUSD',DeltaRunner)]:
            with self.subTest(broker=broker),tempfile.TemporaryDirectory() as d:
                adapter=FakeBroker();runner=runner_type(adapter,Path(d)/'state.json',lambda:adapter.now)
                try:
                    payload=dict(strategy='RENKO_SUPERTREND_V1',exit_policy='OPPOSITE_CONFIRMED_SIGNAL',underlying=symbol,timeframe='5 minutes',mode='PAPER',lots=1,broker=broker)
                    if broker=='DELTA_INDIA':payload.update(price_source='PERPETUAL_LAST_TRADE',order_terms='MARKETABLE_LIMIT_IOC',carry_policy='CONTINUOUS')
                    result=runner.preview(payload)
                    self.assertTrue(result['config']['ema_momentum_enabled']);self.assertEqual(result['config']['ema_proximity_mode'],'ATR')
                    self.assertEqual(result['config']['ema_proximity_distance'],.5)
                    self.assertFalse(runner.state['running']);self.assertEqual(adapter.sent,[])
                finally:runner.release()

    def test_family_master_still_disables_the_entry_filter(self):
        from .runner import configuration
        c=configuration(ema.new_entry_defaults(dict(strategy='RENKO_SUPERTREND_V1',exit_policy='OPPOSITE_CONFIRMED_SIGNAL',underlying='NSE:NIFTY50-INDEX',timeframe='5 minutes',mode='PAPER',lots=1,ema_family_enabled=False)))
        self.assertFalse(c['ema_momentum_enabled']);self.assertFalse(c['ema_proximity_enabled'])

    def test_chart_destinations_carry_policy_without_changing_execution(self):
        from . import destinations,chart_destinations
        c={'ema_momentum_enabled':True,'ema_momentum_enabled_indicator':False}
        self.assertFalse(destinations.chart(c)['ema_momentum_enabled']);self.assertTrue(c['ema_momentum_enabled'])
        query={'chart_entry_guards':['true'],'ema_proximity_enabled':['true'],'ema_momentum_enabled':['true'],'ema_proximity_mode':['ATR'],'ema_proximity_distance':['0.5']}
        self.assertTrue(chart_destinations.query_settings(query)['ema_momentum_enabled'])
        query['ema_proximity_enabled']=['false']
        self.assertFalse(chart_destinations.query_settings(query)['ema_momentum_enabled'])
