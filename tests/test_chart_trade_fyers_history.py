import hashlib
import unittest
from dataclasses import replace
from sector_heatmap.chart_trade_plan import ChartTradePlan
from sector_heatmap.chart_trade_fyers_history import read_reports,reconcile_archived_entry
from sector_heatmap.chart_trade_fyers import FyersChartAdapter
from types import SimpleNamespace

class FyersHistoryTests(unittest.TestCase):
    def setUp(self):
        self.identity=hashlib.sha256(b"test").hexdigest()
        self.plan=ChartTradePlan("a","FYERS","NSE:TEST","BUY",65,"25","22","30",
                                "LIMIT","25","INTRADAY",".05",65,"AT_OR_BELOW",
                                native_account_hash=self.identity)
        self.order=dict(symbol="NSE:TEST",clientId="test",id_fyers="entry",exchOrdId="exchange",
                        exchange=11,segment=20,transaction_type="BUY",product_type="Intraday",
                        status="Executed",qty=65,tradedqty=65,limit_price=25)
        self.trade=dict(symbol="NSE:TEST",clientId="test",orderNumber="entry",tradeNumber="trade",
                        exchangeOrderNo="exchange",exchange=11,segment=20,side=1,
                        product_type="Intraday",traded_qty=65,trade_price=24.95)
        self.calls=[]
    def reader(self,name,params):
        self.calls.append((name,dict(params)))
        return dict(s="ok",data=[dict(self.order if name=="order-history" else self.trade)])
    def reports(self,reader=None,**kwargs):
        return read_reports(reader or self.reader,symbol=self.plan.symbol,identity_hash=self.identity,
                            started_at=1794888000,now=1794974400,**kwargs)
    def test_owned_fill_history_does_not_invent_linked_exits(self):
        result=reconcile_archived_entry(self.plan,self.reports(),"entry")
        self.assertEqual(result["filled_quantity"],65)
        self.assertEqual(result["status"],"ENTRY_FILLED_EXITS_UNVERIFIED")
        self.assertFalse(result["protection_confirmed"])
        self.assertFalse(result["retry_allowed"])
        self.assertIsNone(result["open_quantity"])
        self.assertIsNone(result["exited_quantity"])
        self.assertEqual(self.calls[0][1]["from_date"],"2026-11-17")
    def test_empty_reports_never_infer_fill(self):
        reports=self.reports(lambda *args:dict(s="ok",data=[]))
        self.assertEqual(reconcile_archived_entry(self.plan,reports,"entry")["status"],"BROKER_STATUS_UNAVAILABLE")
    def test_pagination_checks_all_pages_and_detects_repetition(self):
        def reader(name,params):
            if params["page_no"]=="1":
                return dict(s="ok",data=[dict(self.order if name=="order-history" else self.trade)])
            return dict(s="ok",data=[])
        self.assertEqual(len(self.reports(reader,page_size=1)["trade-history"]),1)
        with self.assertRaisesRegex(ValueError,"repeated"):
            self.reports(page_size=1)
        with self.assertRaisesRegex(ValueError,"pagination"):
            self.reports(reader,page_size=1,max_pages=1)
    def test_scope_identity_contract_and_report_failure_are_not_ignored(self):
        for row in (dict(self.order,clientId="other"),dict(self.order,symbol="NSE:OTHER"),
                    dict(self.order,id_fyers="")):
            with self.assertRaises(ValueError):
                self.reports(lambda *args:dict(s="ok",data=[row]))
        with self.assertRaises(ValueError):self.reports(lambda *args:dict(s="error",data=[]))
    def test_conflicting_duplicate_rows_fail(self):
        def reader(name,params):
            return dict(s="ok",data=[self.order,dict(self.order,tradedqty=64)])
        with self.assertRaisesRegex(ValueError,"Conflicting"):self.reports(reader)
    def test_historical_fills_require_matching_exchange_order_and_quantity(self):
        for changes in (dict(exchangeOrderNo="other"),dict(side=-1),
                        dict(traded_qty=64),dict(trade_price=0)):
            self.trade.update(changes)
            try:
                value=reconcile_archived_entry(self.plan,self.reports(),"entry")
                self.assertEqual(value["status"],"BROKER_STATUS_UNAVAILABLE")
                self.assertFalse(value["protection_confirmed"])
            except ValueError:pass
            self.setUp()
    def test_only_zero_fill_terminal_entry_releases_ownership(self):
        self.order.update(status="Rejected",tradedqty=0,exchOrdId="")
        reports=self.reports(lambda name,p:dict(s="ok",data=[self.order] if name=="order-history" else []))
        value=reconcile_archived_entry(self.plan,reports,"entry")
        self.assertEqual(value["status"],"REJECTED")
        self.assertEqual(value["filled_quantity"],0)
        self.order.update(status="Cancelled",tradedqty=20,exchOrdId="exchange")
        self.trade.update(traded_qty=20)
        value=reconcile_archived_entry(self.plan,self.reports(),"entry")
        self.assertEqual(value["status"],"ENTRY_FILLED_EXITS_UNVERIFIED")
        self.assertEqual(value["filled_quantity"],20)
    def test_historical_quantity_alias_conflict_is_rejected(self):
        self.order["tradedQty"]=64
        with self.assertRaisesRegex(ValueError,"ambiguous"):
            reconcile_archived_entry(self.plan,self.reports(),"entry")
    def test_adapter_fallback_is_read_only_and_rechecks_selected_identity(self):
        client=SimpleNamespace(get_profile=lambda:dict(s="ok",data=dict(fy_id="test")),
                               orderbook=lambda:dict(s="ok",orderBook=[]))
        adapter=FyersChartAdapter(dict(id="a",broker="FYERS"),None,
            client_factory=lambda:client,history_reader=self.reader,clock=lambda:1794974400)
        record=dict(preview_id="preview",expires_at=1794888120,result=dict(entry_order_id="entry"))
        value=adapter.reconcile_record(self.plan,record=record)
        self.assertEqual(value["status"],"ENTRY_FILLED_EXITS_UNVERIFIED")
        self.assertEqual(len(self.calls),2)
        old=self.reader
        def changed(name,params):
            value=old(name,params)
            if name=="trade-history":client.get_profile=lambda:dict(s="ok",data=dict(fy_id="other"))
            return value
        adapter.history_reader=changed
        with self.assertRaises(PermissionError):adapter.reconcile_record(self.plan,record=record)
    def test_current_conflicting_parent_prevents_historical_fallback(self):
        client=SimpleNamespace(get_profile=lambda:dict(s="ok",data=dict(fy_id="test")),
            orderbook=lambda:dict(s="ok",orderBook=[dict(id="entry",symbol="NSE:TEST",side=1,
                productType="INTRADAY",qty=65,filledQty=0,remainingQuantity=65,status=99,type=1,limitPrice=25,stopPrice=0)]))
        adapter=FyersChartAdapter(dict(id="a",broker="FYERS"),None,
            client_factory=lambda:client,history_reader=self.reader,clock=lambda:1794974400)
        value=adapter.reconcile_record(self.plan,record=dict(preview_id="preview",
            expires_at=1794888120,result=dict(entry_order_id="entry")))
        self.assertEqual(value["status"],"BROKER_STATUS_UNAVAILABLE")
        self.assertEqual(self.calls,[])
if __name__=="__main__":unittest.main()
