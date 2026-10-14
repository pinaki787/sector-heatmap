import unittest
from types import SimpleNamespace
from unittest.mock import patch
from strategies.renko_supertrend.delta_runner import DeltaRunner, FUTURES_ROUTE
from strategies.renko_supertrend.runner import Runner

class DeltaJobNetTests(unittest.TestCase):
    def snapshot(self, trades, position=None, pending=None, route="DELTA_LONG_OPTION"):
        runner=object.__new__(DeltaRunner)
        runner.state={"run_id":"current"}
        runner.adapter=SimpleNamespace(delta=SimpleNamespace())
        result=dict(config={"execution_route":route},trade_history=trades,
                    position=position,pending_order=pending,sideways_status={})
        with patch.object(Runner,"snapshot",return_value=result):
            return runner.snapshot()["cost_pnl"]
    def trade(self,net=4.25,remaining=0):
        return dict(run_id="current",entry_filled=1,remaining_quantity=remaining,
                    costs=dict(realized_net=net))
    def test_closed_options_report_known_net(self):
        self.assertEqual(self.snapshot([self.trade()])["total_net"],4.25)
    def test_missing_costs_stay_unknown(self):
        self.assertIsNone(self.snapshot([self.trade(None)])["total_net"])
    def test_open_or_pending_exposure_stays_unknown(self):
        for kwargs in ({"position":{"quantity":1}},{"pending":{"id":"pending"}}):
            self.assertIsNone(self.snapshot([self.trade()],**kwargs)["total_net"])
        self.assertIsNone(self.snapshot([self.trade(0,1)])["total_net"])
    def test_perpetual_funding_stays_unknown(self):
        self.assertIsNone(self.snapshot([self.trade()],route=FUTURES_ROUTE)["total_net"])
    def test_prior_runs_are_not_included(self):
        old=self.trade(100);old["run_id"]="previous"
        self.assertEqual(self.snapshot([old,self.trade()])["total_net"],4.25)
