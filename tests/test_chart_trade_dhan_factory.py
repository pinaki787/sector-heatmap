import os
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from tests import test_chart_trade_dhan_submit as fixtures
from sector_heatmap.chart_trading import broker_active,get_service,ChartTradingService,close_services
from sector_heatmap.workspace_guard import WorkspaceGuard


class DhanChartFactoryTests(TestCase):
    conditional=fixtures.DhanChartSubmitTests.conditional

    def setUp(self):
        fixtures.DhanChartSubmitTests.setUp(self)
        self.server=SimpleNamespace()
        self.guard=SimpleNamespace(store=SimpleNamespace(folder=lambda account:Path(self.execution.folder)))
        self.ticks=[]
        self.reader=lambda service,symbol:self.ticks.append((service,symbol))
        self.env=patch.dict(os.environ,{"SECTOR_PULSE_ENABLE_DHAN_CHART_ORDERS":"0"})
        self.env.start();self.addCleanup(self.env.stop)
        self.monitor=patch.object(ChartTradingService,"start_monitor")
        self.monitor.start();self.addCleanup(self.monitor.stop)
        self.addCleanup(lambda:close_services(self.server))

    def service(self):
        return get_service(self.server,self.guard,self.account,None,dhan_execution=self.execution,
                           dhan_tick_reader=self.reader)

    def test_default_gate_blocks_dhan_without_native_reads(self):
        self.assertFalse(broker_active("DHAN"))
        with self.assertRaises(ValueError):self.service()
        self.assertEqual(self.client.calls,[])
        self.assertEqual(self.ticks,[])

    def test_explicit_gate_binds_selected_service_and_shared_tick_reader(self):
        os.environ["SECTOR_PULSE_ENABLE_DHAN_CHART_ORDERS"]="1"
        service=self.service()
        adapter=service.adapter_factory(self.account)
        self.assertTrue(adapter.live_enabled())
        adapter.warm_live_feed(SimpleNamespace(symbol="NSE_FNO:123"))
        self.assertEqual(self.ticks,[(self.execution,"NSE_FNO:123")])
        self.assertEqual(self.client.calls,[])
        self.assertIsNone(service.conditional.worker.thread)
        self.assertFalse(broker_active("MOTILAL_OSWAL"))
        os.environ["SECTOR_PULSE_ENABLE_DHAN_CHART_ORDERS"]="0"
        self.assertFalse(adapter.live_enabled())

    def test_unclaimed_restart_state_requires_review_without_starting_worker(self):
        _,review,_=self.conditional(claim=False)
        os.environ["SECTOR_PULSE_ENABLE_DHAN_CHART_ORDERS"]="1"
        service=self.service()
        self.assertEqual(service.previews.inspect("owner",review["preview_id"])["status"],"REVIEW_REQUIRED")
        self.assertIsNone(service.conditional.worker.thread)
        self.assertEqual(self.posts,[])

    def test_factory_rejects_another_execution_account(self):
        os.environ["SECTOR_PULSE_ENABLE_DHAN_CHART_ORDERS"]="1"
        self.execution.account=dict(self.account,id="other")
        with self.assertRaises(ValueError):self.service()
        self.assertEqual(self.client.calls,[])

    def test_worker_guard_requires_flag_exact_account_and_local_cancel_action(self):
        guard=WorkspaceGuard(self.guard.store,"account",1234,1235)
        payload=dict(account_id="account",broker="DHAN")
        path="/api/chart-workspace/trading/cancel-condition"
        with self.assertRaises(PermissionError):guard.validate_action(self.account,path,payload)
        os.environ["SECTOR_PULSE_ENABLE_DHAN_CHART_ORDERS"]="1"
        guard.validate_action(self.account,path,payload)
        with self.assertRaises(PermissionError):
            guard.validate_action(self.account,path,dict(payload,account_id="foreign"))
        with self.assertRaises(PermissionError):
            guard.validate_action(dict(self.account,broker="FYERS"),path,dict(payload,broker="FYERS"))
