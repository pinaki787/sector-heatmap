from pathlib import Path
import unittest
from tests import test_dhan_strategy_broker as fixtures
from sector_heatmap.dhan_indicator_runners import BandRunner,KamaRunner,configuration,KAMA_KEYS
from sector_heatmap.web import ema_band_strategy_signal,ema_band_exit_signal
from sector_heatmap.kama_strategy import kama_v6_signal

class SignalTests(unittest.TestCase):
    setUp=fixtures.Tests.setUp

    def candles(self):
        return [dict(timestamp=self.now-(80-i)*60,open=100+i*.1,high=100.2+i*.1,low=99.8+i*.1,close=100.1+i*.1,volume=10,is_forming=False) for i in range(80)]

    def payload(self,strategy):
        return dict(broker='DHAN',strategy=strategy,execution_route='OPTIONS',underlying='NSE:NIFTY',
                    lots='1',mode='PAPER',timeframe='1 minute')

    def test_ema_band_uses_existing_entry_and_exit_math(self):
        runner=BandRunner(self.broker,Path(self.temp.name)/'band.json',clock=lambda:self.now)
        c=configuration(self.payload('EMA_BAND_V1'));runner.state['config']=c
        rows=self.candles();self.broker.candles=lambda config:rows
        actual=runner.signal()
        expected=ema_band_strategy_signal(rows,c['ema_length'],c['entry_session'],c['slope_lookback'],c['minimum_slope_atr'])
        self.assertEqual(actual['cross_direction'],expected['direction'])
        self.assertEqual(actual['exit_signal'],ema_band_exit_signal(rows,c['ema_length'])['exit'])

    def test_kama_uses_existing_completed_candle_math(self):
        runner=KamaRunner(self.broker,Path(self.temp.name)/'kama.json',clock=lambda:self.now)
        c=configuration(self.payload('KAMA_V6'));runner.state['config']=c
        rows=self.candles();self.broker.candles=lambda config:rows+[dict(rows[-1],timestamp=self.now,is_forming=True)]
        actual=runner.signal()
        expected=kama_v6_signal(rows,**{k:c[k] for k in KAMA_KEYS}) # defaults equal saved configuration
        self.assertEqual(actual['action'],expected['action'])
        self.assertEqual(actual['kama'],expected['kama'])
        self.assertEqual(actual['timestamp'],rows[-1]['timestamp'])

    def test_exit_completed_bar_does_not_require_new_entry_signal(self):
        runner=BandRunner(self.broker,Path(self.temp.name)/'band.json',clock=lambda:self.now)
        runner.state.update(config=configuration(self.payload('EMA_BAND_V1')),eligible_since=self.now-120,position=dict(direction='BULLISH'))
        sig=dict(timestamp=self.now-60,cross_direction=None,exit_signal=True)
        self.assertTrue(runner.fresh_cross(sig));self.assertFalse(runner.fresh_cross(sig))
        self.assertTrue(runner.exit_signal(sig,'BULLISH'))

    def test_old_signal_not_replayed_and_empty_direction_cannot_enter(self):
        runner=BandRunner(self.broker,Path(self.temp.name)/'band.json',clock=lambda:self.now)
        runner.state.update(config=configuration(self.payload('EMA_BAND_V1')),eligible_since=self.now)
        self.assertFalse(runner.fresh_cross(dict(timestamp=self.now-60,cross_direction='BULLISH')))
        runner.state['eligible_since']=self.now-120;runner.state['last_processed_bar']=None
        self.assertFalse(runner.fresh_cross(dict(timestamp=self.now-60,cross_direction=None)))

    def test_non_option_route_rejected(self):
        for strategy in ('EMA_BAND_V1','KAMA_V6'):
            with self.assertRaises(ValueError):configuration(dict(self.payload(strategy),execution_route='CASH_EQUITY'))

    def test_service_starts_from_instance_owned_preview_without_resubmitted_instrument(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from sector_heatmap.dhan_strategy_service import Service
        service=Service.__new__(Service)
        service.execution=SimpleNamespace(account={'id':'owned'})
        service.strategy='band';service.instrument='NSE:NIFTY'
        service.runner=SimpleNamespace(strategy_id='EMA_BAND_V1',preview=Mock(),start=Mock(return_value={'running':False}),stop=Mock())
        handler=SimpleNamespace(headers={'Host':'localhost','Origin':'http://localhost'},send_json=Mock())
        service.post_action(handler,'start',{'preview_id':'owned-preview','confirmation':'START PAPER','account_id':'owned','broker':'DHAN'})
        service.runner.start.assert_called_once()
        with self.assertRaises(ValueError):
            service.post_action(handler,'preview',{'strategy':'EMA_BAND_V1','underlying':'NSE:OTHER'})
        with self.assertRaises(PermissionError):
            service.post_action(handler,'start',{'account_id':'other'})

    def test_preview_does_not_place_broker_orders(self):
        for cls,strategy in ((BandRunner,'EMA_BAND_V1'),(KamaRunner,'KAMA_V6')):
            runner=cls(self.broker,Path(self.temp.name)/(strategy+'.json'),clock=lambda:self.now)
            value=runner.preview(self.payload(strategy))
            self.assertEqual(value['config']['strategy'],strategy)
            self.assertEqual(value['context']['broker'],'DHAN')
        self.assertFalse(any(method=='POST' and path=='/orders' for method,path,_ in self.client.calls))


class LifecycleTests(SignalTests):
    def test_paper_entry_and_percentage_exit_use_dhan_without_broker_order(self):
        runner=BandRunner(self.broker,Path(self.temp.name)/'paper-cycle.json',clock=lambda:self.now)
        payload=dict(self.payload('EMA_BAND_V1'),stop_loss_pct=.1)
        preview=runner.preview(payload)
        runner.start({'preview_id':preview['id'],'confirmation':preview['confirmation']},background=False)
        self.now+=61
        runner.state['last_signal']=dict(timestamp=self.now-60,close=100,cross_direction='BULLISH',exit_signal=False)
        runner.signal=lambda:runner.state['last_signal']
        runner.step()
        self.assertIsNotNone(runner.state['position'])
        runner.step()
        self.assertIsNone(runner.state['position'])
        self.assertTrue(any(row['reason']=='PREMIUM_STOP' and row['filled']==25 for row in runner.state['order_history']))
        self.assertFalse(any(method=='POST' and path=='/orders' for method,path,_ in self.client.calls))
        runner.stop()

    def test_kama_live_activation_is_account_gated_without_order(self):
        runner=KamaRunner(self.broker,Path(self.temp.name)/'kama-live-preview.json',clock=lambda:self.now)
        payload=dict(self.payload('KAMA_V6'),mode='LIVE',invalidation=90,idea_risk_limit=500)
        preview=runner.preview(payload)
        state=runner.start({'preview_id':preview['id'],'confirmation':preview['confirmation']},background=False)
        self.assertTrue(state['running'])
        self.assertEqual(state['config']['broker'],'DHAN')
        self.assertEqual(state['config']['max_premium'],500)
        self.assertFalse(any(method=='POST' and path=='/orders' for method,path,_ in self.client.calls))
        runner.stop()

class ProtectionTests(unittest.TestCase):
    def test_kama_live_retains_invalidation_and_full_premium_cap(self):
        payload=dict(strategy='KAMA_V6',broker='DHAN',execution_route='OPTIONS',underlying='NSE:NIFTY',
                     mode='LIVE',lots=1,invalidation=22000,idea_risk_limit=2000)
        value=configuration(payload)
        self.assertEqual(value['invalidation'],22000)
        self.assertEqual(value['max_premium'],2000)
        self.assertEqual(value['mode'],'LIVE')

    def test_invalid_protection_rejected(self):
        payload=dict(strategy='EMA_BAND_V1',broker='DHAN',execution_route='OPTIONS',underlying='NSE:NIFTY',lots=1)
        for key,value in [('stop_loss_pct',100),('target_profit_pct',-1),('invalidation','NaN')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                configuration(dict(payload,**{key:value}))

    def test_underlying_invalidation_has_directional_exit(self):
        runner=KamaRunner.__new__(KamaRunner)
        runner.state={'config':{'invalidation':100,'strategy':'KAMA_V6'}}
        self.assertEqual(runner.exit_reason_for({'close':99,'exit_signal':False},{'direction':'BULLISH'}),'UNDERLYING_INVALIDATION')
        self.assertIsNone(runner.exit_reason_for({'close':101,'exit_signal':False},{'direction':'BULLISH'}))
        self.assertEqual(runner.exit_reason_for({'close':101,'exit_signal':False},{'direction':'BEARISH'}),'UNDERLYING_INVALIDATION')

if __name__=='__main__':unittest.main()
