"""Real indicator decisions through execution with an isolated fake broker only."""
import tempfile,unittest
from unittest.mock import Mock,patch
from contextlib import nullcontext
from pathlib import Path
from direct import DirectStrategy
from delta_execution import DeltaExecution
from test_delta_execution import PRODUCT
class SignalExecutionLifecycleTests(unittest.TestCase):
    def test_confirmed_indicator_flip_opens_and_opposing_flip_reduces_owned_position(self):
        strategy=DirectStrategy(dict(underlying='BTCUSD',market='CRYPTO',timeframe=5,reference_value=46))
        with tempfile.TemporaryDirectory() as directory:
            delta=Mock();delta.product.return_value=PRODUCT;delta._position.side_effect=[2,0]
            delta._get.side_effect=lambda *a,**kw:dict(result=dict(symbol='BTCUSD',last_updated_at=int(delta.clock()*1000000),buy=[dict(price=str(price-.5),size=100)],sell=[dict(price=str(price+.5),size=100)]))
            native=Mock();native.active_orders.return_value=[];native.reconcile.side_effect=[dict(status=2,filledQty=2,id='open',tradedPrice=102),dict(status=2,filledQty=2,id='close',tradedPrice=104)]
            executor=DeltaExecution(delta,'a'*32,directory,contracts=2,native=native,live=True)
            self.addCleanup(executor.close)
            emitted=[]
            with patch('sector_heatmap.chart_trade_admission.entry_lock',return_value=nullcontext()),patch('sector_heatmap.chart_trade_admission.mark_entry_attempt'),patch('sector_heatmap.chart_trade_ownership.assert_no_chart_entry_conflict'):
                for i,price in enumerate([100,102,104,106,108,110,108,106,104,102,100,98,96,94]):
                    stamp=100+i*300;delta.clock.return_value=stamp
                    for action in strategy.update(dict(kind='underlying',timestamp=stamp,close=price)):
                        emitted.append(action['action'])
                        executor.submit(action,dict(symbol='BTCUSD',bid=price-.5,ask=price+.5,exchange_at=stamp,received_at=stamp))
                    if len(emitted)==2:break
            self.assertEqual(emitted,['OPEN_LONG','CLOSE_LONG'])
            self.assertEqual([call.args[2] for call in native.submit.call_args_list],[1,-1])
            self.assertEqual([call.kwargs['reduce_only'] for call in native.submit.call_args_list],[False,True])
            self.assertIsNone(executor.state['position']);self.assertIsNone(executor.state['pending'])

    def test_fyers_option_premium_confirmation_and_premium_flip_reach_fake_live_orders(self):
        from core import Strategy
        from execution import Execution
        from test_execution import API,META,POSITION,NOW
        engine=Strategy(dict(underlying='NSE:NIFTY50-INDEX',market='NSE',timeframe=5,reference_value=12))
        engine.reset_contract(dict(symbol=POSITION['symbol'],option_type='CE',expiry=META['expiry_epoch']),.23)
        with tempfile.TemporaryDirectory() as directory:
            api=API();executor=Execution(api,'account',directory,live=True,lots=1,product='MARGIN',master=lambda symbol:META,account_folder=Path(directory))
            self.addCleanup(executor.close);emitted=[]
            pairs=list(zip([100,102,104,106,108,110,110,110,110,110,110,110,110,110],[40,41,42,43,44,45,44,43,42,41,40,39,38,37]))
            with patch('sector_heatmap.chart_trade_admission.entry_lock',return_value=nullcontext()),patch('sector_heatmap.chart_trade_admission.mark_entry_attempt'),patch('sector_heatmap.chart_trade_ownership.assert_no_chart_entry_conflict'):
                for i,(underlying,premium) in enumerate(pairs):
                    stamp=NOW+i*300
                    actions=engine.update(dict(kind='underlying',timestamp=stamp,close=underlying))
                    actions+=engine.update(dict(kind='premium',symbol=POSITION['symbol'],timestamp=stamp,close=premium))
                    gate=engine.selected_gate_entry()
                    if gate:actions.append(gate)
                    for action in actions:
                        self.assertNotEqual(action['action'],'SELECT')
                        emitted.append(action);executor.submit(action,dict(timestamp=stamp,ltp=premium),now=stamp)
                        api.exposure=65 if executor.state['position'] else 0
                    if len(emitted)==2:break
            self.assertEqual([a['action'] for a in emitted],['BUY','SELL'])
            self.assertEqual(emitted[-1]['reason'],'AI_RENKO_SUPERTREND_PREMIUM')
            self.assertEqual([p['side'] for p in api.sent],[1,-1])
            self.assertIsNone(executor.state['position']);self.assertIsNone(executor.state['pending'])
