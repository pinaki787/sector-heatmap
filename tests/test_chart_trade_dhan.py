import tempfile
import unittest
from datetime import datetime
from sector_heatmap.dhan_execution import IST
from types import SimpleNamespace
from sector_heatmap.chart_trade_dhan import DhanChartAdapter
from sector_heatmap.chart_trade_admission import ChartOrderNotSent


class Client:
    client_id = "client"
    def __init__(self):
        self.calls=[];self.positions=[];self.orders=[]
        self.margin_hook=lambda:None
        self.profile=dict(dhanClientId="client",dataPlan="Active",activeSegment="Derivative")
        self.quote=dict(last_price=25,depth={"buy":[{"price":24.95}],"sell":[{"price":25}]})
    def request(self, method, path, payload=None):
        self.calls.append((method,path,payload))
        if path == "/profile":return self.profile
        if path == "/ip/getIP":return {"primaryIP":"203.0.113.10"}
        if path == "/positions":return self.positions
        if path == "/orders":return self.orders
        if path == "/marketfeed/quote":return {"status":"success","data":{"NSE_FNO":{"123":self.quote}}}
        if path == "/fundlimit":return {"dhanClientId":"client","availabelBalance":100000}
        if path == "/margincalculator":
            self.margin_hook()
            return {"totalMargin":500,"availableBalance":100000}
        raise AssertionError("Unexpected broker call: "+method+" "+path)


class DhanChartPreviewTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.client=Client()
        self.account=dict(id="account",broker="DHAN",account_ref="client",live_enabled=True)
        self.contract=dict(security_id="123",exchange_segment="NSE_FNO",symbol="DESCRIPTIVE",
                           tick_size="0.05",lot_size=65,expiry="2026-12-31",option_type="CE")
        self.master=SimpleNamespace(resolve=lambda payload,now:dict(self.contract))
        self.execution=SimpleNamespace(account=self.account,folder=self.folder.name,master=self.master,
                                       _client=lambda:self.client,egress=lambda:"203.0.113.10")
        self.sessions=[]
        self.adapter=DhanChartAdapter(self.account,self.execution,clock=lambda:1794978000,
                                      session_validator=lambda contract,now:self.sessions.append((contract,now)))
        self.payload=dict(account_id="account",broker="DHAN",symbol="NSE_FNO:123",side="BUY",
                          quantity=65,entry="24.50",stop_loss="22",target="30",
                          entry_type="LIMIT",product="INTRADAY")

    def test_read_only_preview_keeps_opaque_chart_security_and_native_ids(self):
        plan=self.adapter.prepare(self.payload)
        self.assertEqual(plan.symbol,"NSE_FNO:123")
        self.assertEqual(plan.entry,"24.50")
        self.assertTrue(plan.native_account_hash)
        state=self.adapter.last_preflight
        self.assertEqual(state["required_margin"],"1592.50")
        self.assertEqual(state["quote"]["timestamp_basis"],"DHAN_REST_SNAPSHOT")
        self.assertEqual(len(self.sessions),2)
        margin=[call[2] for call in self.client.calls if call[1]=="/margincalculator"][0]
        self.assertEqual(margin["securityId"],"123")
        self.assertNotIn("correlationId",margin)
        self.assertEqual(sum(call[1]=="/marketfeed/quote" for call in self.client.calls),2)
        self.assertTrue(all(method=="GET" or path in {"/marketfeed/quote","/margincalculator"}
                            for method,path,_ in self.client.calls))
        self.assertFalse(self.adapter.live_enabled())
        with self.assertRaises(ChartOrderNotSent):
            self.adapter.submit_bracket(plan,idempotency_key="review")

    def test_new_exposure_during_margin_invalidates_preview(self):
        self.client.margin_hook=lambda:self.client.positions.append(dict(
            dhanClientId="client",exchangeSegment="NSE_FNO",securityId="123",netQty=65))
        with self.assertRaisesRegex(ValueError,"already has"):
            self.adapter.prepare(self.payload)
        self.assertIsNone(self.adapter.last_preflight)

    def test_wrong_account_or_master_never_produces_preview(self):
        with self.assertRaises(PermissionError):
            self.adapter.prepare(dict(self.payload,account_id="another"))
        self.contract["security_id"]="456"
        with self.assertRaisesRegex(ValueError,"different contract"):
            self.adapter.prepare(self.payload)

    def test_missing_session_validator_or_expiry_does_not_guess(self):
        self.adapter.session_validator=None
        with self.assertRaisesRegex(ValueError,"session and expiry"):
            self.adapter.prepare(self.payload)
        self.adapter.session_validator=lambda *args:None
        self.contract["expiry"]=""
        with self.assertRaisesRegex(ValueError,"expiry"):
            self.adapter.prepare(self.payload)

    def test_stop_preview_uses_read_only_cap_margin_without_untriggered_placement(self):
        plan=self.adapter.prepare(dict(self.payload,entry="25.50",limit_price="25.55",entry_type="STOP_LIMIT"))
        self.assertEqual(plan.entry_type,"STOP_LIMIT")
        self.assertEqual(plan.entry,"25.50")
        margin=[body for _,path,body in self.client.calls if path=="/margincalculator"][0]
        self.assertEqual(margin["price"],25.55)
        with self.assertRaises(ChartOrderNotSent):self.adapter.submit_bracket(plan,idempotency_key="untriggered")
        self.assertFalse(any(path=="/super/orders" for _,path,_ in self.client.calls))

    def test_default_nse_derivative_preview_uses_broker_instrument_family(self):
        self.contract["instrument_name"]="OPTIDX"
        self.adapter=DhanChartAdapter(self.account,self.execution,
            clock=lambda:datetime(2026,11,18,10,tzinfo=IST).timestamp())
        self.assertEqual(self.adapter.prepare(self.payload).symbol,"NSE_FNO:123")
        self.contract["instrument_name"]=""
        with self.assertRaisesRegex(ValueError,"classification"):
            self.adapter.prepare(self.payload)

    def test_stock_option_master_near_expiry_blocks_next_month_substitution(self):
        self.contract.update(instrument_name="OPTSTK",expiry="2026-12-29")
        rows=[dict(SEM_EXM_EXCH_ID="NSE",SEM_SEGMENT="D",SEM_INSTRUMENT_NAME="OPTSTK",
                   SEM_SMST_SECURITY_ID=security,SEM_TRADING_SYMBOL="TEST-"+suffix+"-100-CE",
                   SEM_EXPIRY_DATE=expiry+" 00:00:00",SEM_OPTION_TYPE="CE")
              for security,suffix,expiry in (("123","DEC","2026-12-29"),("456","NOV","2026-11-19"))]
        self.master.load=lambda now:rows
        self.adapter=DhanChartAdapter(self.account,self.execution,
            clock=lambda:datetime(2026,11,18,10,tzinfo=IST).timestamp())
        with self.assertRaisesRegex(ValueError,"Equity only"):
            self.adapter.prepare(self.payload)
        self.assertEqual(self.client.calls,[])

    def test_crossed_depth_or_wrong_subscription_blocks_preview(self):
        self.client.quote["depth"]["buy"][0]["price"]=26
        with self.assertRaisesRegex(ValueError,"crossed"):
            self.adapter.prepare(self.payload)
        self.client.profile["dataPlan"]="Inactive"
        with self.assertRaisesRegex(ValueError,"subscription"):
            self.adapter.prepare(self.payload)


if __name__ == "__main__":unittest.main()
