import unittest
from types import SimpleNamespace
from dataclasses import replace
from sector_heatmap.chart_trade_fyers import FyersChartAdapter

class Client:
    def __init__(self):self.placements=[];self.position_rows=[];self.order_rows=[]
    def get_profile(self):return {"s":"ok","data":{"fy_id":"test"}}
    def positions(self):return {"s":"ok","netPositions":self.position_rows}
    def orderbook(self):return {"s":"ok","orderBook":self.order_rows}
    def funds(self):return {"s":"ok","fund_limit":[{"id":10,"equityAmount":100000,"commodityAmount":0}]}
    def place_order(self,body):
        self.placements.append(body)
        return {"s":"ok","id":"native-parent"}

class Master:
    def lookup(self,symbols):
        return {symbol:{"symbol":symbol,"tick_size":0.05,"lot_size":65,"expiry_epoch":10000} for symbol in symbols}

class FyersChartTests(unittest.TestCase):
    def setUp(self):
        self.client=Client();self.now=100
        self.quote={"ltp":25,"bid":24.95,"ask":25,"provider_timestamp":100}
        self.margin={"s":"ok","data":{"margin_total":1500,"margin_avail":100000}}
        self.execution=SimpleNamespace(master=Master(),cm_master=Master(),_live_submission_enabled=lambda:True)
        self.account={"id":"account","broker":"FYERS","live_enabled":True}
        self.adapter=FyersChartAdapter(self.account,self.execution,client_factory=lambda:self.client,
            quote_reader=lambda *args:dict(self.quote),margin_reader=lambda *args:dict(self.margin),
            clock=lambda:self.now)
        self.payload={"account_id":"account","broker":"FYERS","symbol":"NSE:TEST","side":"BUY","quantity":65,
                      "entry":"24.50","stop_loss":"22","target":"30","entry_type":"LIMIT","product":"INTRADAY"}

    def test_preview_is_read_only_and_submission_preserves_marked_levels(self):
        plan=self.adapter.prepare(self.payload)
        self.assertEqual(self.client.placements,[])
        result=self.adapter.submit_bracket(plan,idempotency_key="chart-one")
        self.assertEqual(result["entry_order_id"],"native-parent")
        self.assertEqual(self.client.placements[0]["stopLoss"],22)
        self.assertEqual(self.client.placements[0]["takeProfit"],30)
        self.assertNotIn("legType",self.client.placements[0])
        self.assertIs(self.client.placements[0]["isSliceOrder"],False)

    def test_existing_positions_or_pending_orders_block_new_chart_entry(self):
        for field,row in (("position_rows",{"symbol":"NSE:TEST","netQty":65}),
                          ("order_rows",{"symbol":"NSE:TEST","status":6})):
            setattr(self.client,field,[row])
            with self.assertRaises(ValueError):self.adapter.prepare(self.payload)
            setattr(self.client,field,[])
        self.assertEqual(self.client.placements,[])

    def test_stale_price_margin_shortfall_and_disabled_gate_cannot_place(self):
        self.quote["provider_timestamp"]=80
        with self.assertRaises(ValueError):self.adapter.prepare(self.payload)
        self.quote["provider_timestamp"]=100
        self.margin["data"]["margin_avail"]=100
        with self.assertRaises(ValueError):self.adapter.prepare(self.payload)
        self.margin["data"]["margin_avail"]=100000
        plan=self.adapter.prepare(self.payload)
        self.execution._live_submission_enabled=lambda:False
        with self.assertRaisesRegex(ValueError,"pre-submission"):self.adapter.submit_bracket(plan,idempotency_key="chart-one")
        self.assertEqual(self.client.placements,[])

    def test_changed_terms_cannot_reuse_an_old_fresh_preflight(self):
        plan=self.adapter.prepare(self.payload)
        with self.assertRaises(ValueError):
            self.adapter.submit_bracket(replace(plan,target="31"),idempotency_key="chart-one")
        self.assertEqual(self.client.placements,[])

    def test_exposure_appearing_during_margin_read_blocks_submission(self):
        def margin(*args):
            self.client.position_rows=[{"symbol":"NSE:TEST","netQty":65}]
            return self.margin
        self.adapter.margin_reader=margin
        with self.assertRaisesRegex(ValueError,"acquired a position"):self.adapter.prepare(self.payload)
        self.assertEqual(self.client.placements,[])


    def test_status_read_checks_native_identity_and_never_places(self):
        plan=self.adapter.prepare(self.payload)
        self.client.order_rows=[dict(id="native-parent",symbol=plan.symbol,side=1,productType=plan.product,
            qty=plan.quantity,filledQty=0,remainingQuantity=plan.quantity,status=6,stopLoss=22,takeProfit=30,
            type=1,limitPrice=float(plan.limit_price),stopPrice=0)]
        result=self.adapter.reconcile(plan,preview_id="chart-one",entry_order_id="native-parent")
        self.assertEqual(result["status"],"ENTRY_PENDING")
        self.assertEqual(self.client.placements,[])
        self.client.get_profile=lambda:{"s":"ok","data":{"fy_id":"another-login"}}
        with self.assertRaises(PermissionError):
            self.adapter.reconcile(plan,preview_id="chart-one",entry_order_id="native-parent")
        self.assertEqual(self.client.placements,[])

if __name__=="__main__":unittest.main()

