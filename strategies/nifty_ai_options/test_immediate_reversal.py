import unittest
from types import SimpleNamespace
from direct import DirectStrategy,complete_reversal
class ImmediateReversalTests(unittest.TestCase):
    def setup_position(self,side='SHORT'):
        engine=DirectStrategy(dict(underlying='BTCUSD',market='CRYPTO',timeframe=5,reference_value=46))
        for i,price in enumerate([100,98,96,94,92]):engine.update(dict(kind='underlying',timestamp=100+i*300,close=price));engine.position=None
        action=engine.manual_entry(side,1500)
        executor=SimpleNamespace(state=dict(position=dict(action['position'],quantity=2),pending=None));return engine,executor
    def test_confirmed_short_close_and_long_entry_share_same_signal_observation(self):
        engine,executor=self.setup_position();orders=[]
        def submit(action):
            orders.append(action);executor.state['position']=None if action['action'].startswith('CLOSE_') else dict(action['position'],quantity=2)
            return dict(confirmed=True)
        for i,price in enumerate([94,96,98,100,102,104,106,108,110]):
            actions=engine.update(dict(kind='underlying',timestamp=1800+i*300,close=price))
            for action in actions:
                submit(action);complete_reversal(engine,executor,action,submit)
            if len(orders)==2:break
        self.assertEqual([a['action'] for a in orders],['CLOSE_SHORT','OPEN_LONG'])
        self.assertEqual(orders[0]['timestamp'],orders[1]['timestamp']);self.assertEqual(executor.state['position']['side'],'LONG')
    def test_partial_pending_or_retained_exit_never_opens_reverse(self):
        for state in [dict(position={'symbol':'BTCUSD'},pending=None),dict(position=None,pending={'id':'unknown'})]:
            engine,executor=self.setup_position();engine.position=None;engine.pending_direction=('LONG',2000);executor.state=state;sent=[]
            complete_reversal(engine,executor,dict(action='CLOSE_SHORT',reason='AI_RENKO_SUPERTREND_UNDERLYING',timestamp=2000),sent.append)
            self.assertEqual(sent,[])
    def test_optional_sma_exit_does_not_force_an_unqualified_reverse(self):
        engine,executor=self.setup_position();engine.position=None;engine.pending_direction=('LONG',2000);executor.state['position']=None;sent=[]
        complete_reversal(engine,executor,dict(action='CLOSE_SHORT',reason='OPTIONAL_UNDERLYING_1M_SMA30',timestamp=2000),sent.append);self.assertEqual(sent,[])
    def test_cash_delivery_does_not_reverse_into_a_short(self):
        engine=DirectStrategy(dict(underlying='NSE:RELIANCE-EQ',market='NSE',timeframe=5,reference_value=12,product='CNC'));engine.pending_direction=('SHORT',2000);executor=SimpleNamespace(state=dict(position=None,pending=None));sent=[]
        complete_reversal(engine,executor,dict(action='CLOSE_LONG',reason='AI_RENKO_SUPERTREND_UNDERLYING',timestamp=2000),sent.append);self.assertEqual(sent,[])
