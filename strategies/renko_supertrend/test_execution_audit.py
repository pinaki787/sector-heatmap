import unittest
from .execution_audit import entry_orders

class AssessmentFillTests(unittest.TestCase):
    def setUp(self):
        self.event=dict(run_id='R',timestamp=120,event_at=120,provisional=True,direction='BULLISH',status='NOT ELIGIBLE')
        self.order=dict(run_id='R',side='BUY',entry_mode='INTRABAR',entry_event_at=122,option_type='CE',filled=40)
    def test_later_tick_fill_belongs_to_first_candidate_same_candle(self):
        self.assertEqual(entry_orders(self.event,[self.order],60),[self.order])
        self.assertEqual(self.event['status'],'NOT ELIGIBLE')  # Original audit stays immutable.
    def test_other_run_direction_candle_and_confirmed_mode_do_not_match(self):
        for change in [dict(run_id='OTHER'),dict(option_type='PE'),dict(entry_event_at=180),dict(side='SELL'),dict(entry_mode='CONFIRMED')]:
            self.assertEqual(entry_orders(self.event,[{**self.order,**change}],60),[])
    def test_confirmed_event_requires_exact_close_timestamp(self):
        event={**self.event,'provisional':False,'event_at':180}
        self.assertEqual(entry_orders(event,[self.order],60),[])
        order={**self.order,'entry_event_at':180,'entry_mode':'CONFIRMED'}
        self.assertEqual(entry_orders(event,[order],60),[order])

class ActualSnapshotTests(unittest.TestCase):
    from .test_runner import RenkoLifecycleTests as _Fixtures
    setUp=_Fixtures.setUp
    start=_Fixtures.start
    def test_first_ineligible_assessment_does_not_hide_later_fill(self):
        self.start();self.r.step()
        row=self.r.state['order_history'][0]
        event=self.r.state['execution_signals'][0]
        row.update(run_id='R',entry_mode='INTRABAR',entry_event_at=122,option_type='CE')
        event.update(run_id='R',timestamp=120,event_at=120,provisional=True,status='NOT ELIGIBLE',eligible=False,direction='BULLISH')
        self.r.state['run_id']='R'
        result=self.r.snapshot()['execution_signals'][0]
        self.assertEqual(result['status'],'FILLED')
        self.assertEqual(result['first_assessment']['status'],'NOT ELIGIBLE')
        self.assertEqual(result['entry_event_at'],122)
        self.assertEqual(event['status'],'NOT ELIGIBLE')
