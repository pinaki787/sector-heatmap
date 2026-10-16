from pathlib import Path
import unittest
from unittest.mock import patch
from tests import test_dhan_strategy_broker as fixtures
from strategies.renko_engine.runner import DhanRunner,configuration
from strategies.renko_engine.rules import STRATEGY

class NativeEngineExecutionTests(unittest.TestCase):
    setUp=fixtures.Tests.setUp
    def test_live_engine_uses_native_dhan_intent_and_confirms_fill(self):
        runner=DhanRunner(self.broker,Path(self.temp.name)/'native-engine.json',clock=lambda:self.now)
        payload=dict(strategy=STRATEGY,broker='DHAN',underlying='NSE:NIFTY',lots='1',timeframe='1 minute',mode='LIVE',
            engine_settings={'anchorTime':'2026-10-12T09:15','endTime':'2026-10-13T15:15'})
        config=configuration(payload,'DHAN')
        runner.state.update(config=config,running=True,accepting_entries=True,trades_used=0,
            last_signal=dict(timestamp=self.now-60,close=100,cross_direction='BULLISH'))
        runner.state['renko_engine']={'anchor':{},'last':{'host_atr':1}}
        position=dict(symbol='NSE_FNO:1',direction='BULLISH',entry_side=1,lot_size=25,quantity=25,
            quantity_multiplier=1,tick_size=.05,entry_price=None,opened_at=None,entry_signal_timestamp=self.now-60)
        with patch('strategies.renko_supertrend.runner.ema_exit_observation',return_value=dict(entry_qualified=True,entry_direction='BULLISH',ema10=100)):
            runner.submit(self.order,position,'RENKO_ENGINE_ENTRY')
        pending=runner.state['pending']
        self.assertIsNotNone(pending)
        sent=[body for method,path,body in self.client.calls if method=='POST' and path=='/orders']
        self.assertEqual(len(sent),1)
        self.assertEqual(sent[0]['securityId'],'1')
        self.assertEqual(sent[0]['orderType'],'LIMIT')
        self.assertEqual(sent[0]['validity'],'IOC')
        self.client.orders=[dict(orderId='123',dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',
            transactionType='BUY',productType='MARGIN',quantity=25,filledQty=25,averageTradedPrice=10,orderStatus='TRADED',correlationId=pending['tag'])]
        self.client.positions=[dict(dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',netQty=25,costPrice=10,productType='MARGIN')]
        runner.reconcile()
        self.assertEqual(runner.state['position']['quantity'],25)
        self.assertEqual(runner.state['order_history'][-1]['broker'],'DHAN')
