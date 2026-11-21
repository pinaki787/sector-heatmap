import threading
import unittest
from copy import deepcopy
from dataclasses import replace
from sector_heatmap.chart_trade_delta import DeltaChartAdapter

class Delta:
    def __init__(self):
        self.lock=threading.RLock();self.cache={};self.corrupt=False
        self.runner={"running":False};self.live={};self.paper={}
        self.position=0;self.orders=[];self.placements=[];self.identity="key-hash"
        self.gate=True;self.available="1000";self.stamp=100;self.parent=None;self.history=[];self.fills=[]
        self.metadata=dict(id=27,symbol="BTCUSD",tick_size=".5",trading_status="operational",
                           product_specs={},settlement_time=None,settlement_currency="USD",contract_type="perpetual_futures")
    def verify_auth(self):pass
    def _identity(self):return self.identity
    def _gate(self):return self.gate
    def _live_ready(self):
        if not self.gate:raise PermissionError("Disabled")
    def _position(self,product_id):return self.position
    def product(self,symbol,**kwargs):return deepcopy(self.metadata)
    def _get(self,path):
        return {"result":dict(symbol="BTCUSD",close=100,timestamp=self.stamp*1000000,
                             quotes=dict(best_bid="99.5",best_ask="100"))}
    def _private(self,method,path,**kwargs):
        if method=="POST":
            body=deepcopy(kwargs["body"]);self.placements.append(body)
            return {"success":True,"result":dict(body,id=123)}
        if path=="/v2/wallet/balances":
            return {"success":True,"result":[dict(asset_symbol="USD",available_balance=self.available)]}
        if path.startswith("/v2/orders/client_order_id/"):return {"success":True,"result":deepcopy(self.parent)}
        if path=="/v2/orders/history":return {"success":True,"result":deepcopy(self.history)}
        if path=="/v2/fills":return {"success":True,"result":deepcopy(self.fills)}
        if path=="/v2/orders":return {"success":True,"result":deepcopy(self.orders)}
        raise AssertionError((method,path))

class DeltaChartAdapterTests(unittest.TestCase):
    def setUp(self):
        self.execution=Delta();self.now=100
        self.adapter=DeltaChartAdapter(dict(id="delta-a",broker="DELTA_INDIA",live_enabled=True),
                                      self.execution,clock=lambda:self.now)
        self.payload=dict(account_id="delta-a",broker="DELTA_INDIA",symbol="BTCUSD",side="BUY",
                          quantity=2,entry="99",stop_loss="95",target="110",entry_type="LIMIT",
                          limit_price="99",product="MARGIN")
    def test_preview_reads_only_and_explains_margin_basis(self):
        plan=self.adapter.prepare(self.payload)
        self.assertEqual(self.execution.placements,[])
        self.assertEqual(plan.native_account_hash,"key-hash")
        self.assertEqual(self.adapter.last_preflight["margin_status"],"BROKER_ENFORCED_ON_SUBMISSION")
        self.assertEqual(self.adapter.last_preflight["settlement_currency"],"USD")
    def test_confirmed_native_payload_has_entry_and_both_marked_exits(self):
        plan=self.adapter.prepare(self.payload)
        result=self.adapter.submit_bracket(plan,idempotency_key="owned-preview")
        self.assertEqual(result["entry_order_id"],"123")
        body=self.execution.placements[0]
        self.assertEqual((body["limit_price"],body["bracket_stop_loss_price"],body["bracket_take_profit_price"]),("99","95","110"))
        self.assertFalse(body["cancel_orders_accepted"])
    def test_new_position_pending_order_or_runner_blocks_before_native_submission(self):
        for field,value in (("position",1),("orders",[dict(product_id=27,state="open")]),
                            ("runner",dict(running=True)),("live",dict(runner_position={"id":"owned"}))):
            old=getattr(self.execution,field);setattr(self.execution,field,value)
            with self.assertRaises(ValueError):self.adapter.prepare(self.payload)
            setattr(self.execution,field,old)
        self.assertEqual(self.execution.placements,[])
    def test_exposure_after_review_is_caught_at_submit(self):
        plan=self.adapter.prepare(self.payload);self.execution.position=1
        with self.assertRaises(ValueError):self.adapter.submit_bracket(plan,idempotency_key="owned-preview")
        self.assertEqual(self.execution.placements,[])
    def test_changed_login_gate_contract_or_price_blocks_submission(self):
        for change in ("identity","gate","tick","stale"):
            plan=self.adapter.prepare(self.payload)
            if change=="identity":self.execution.identity="other"
            elif change=="gate":self.execution.gate=False
            elif change=="tick":self.execution.metadata["tick_size"]="1"
            else:self.execution.stamp=80
            with self.assertRaises((ValueError,PermissionError)):
                self.adapter.submit_bracket(plan,idempotency_key="owned-preview")
            self.assertEqual(self.execution.placements,[])
            self.execution=Delta();self.adapter.execution=self.execution
    def test_exact_settlement_wallet_required_no_currency_conversion(self):
        self.execution.metadata["settlement_currency"]="INR"
        with self.assertRaises(ValueError):self.adapter.prepare(self.payload)
        self.assertEqual(self.execution.placements,[])

    def parent(self,**changes):
        import hashlib
        token="CH"+hashlib.sha256(b"owned-preview").hexdigest()[:24]
        self.execution.parent=dict(id=123,client_order_id=token,product_symbol="BTCUSD",side="buy",
                                   size=2,unfilled_size=2,state="pending",average_fill_price=None,**changes)
    def test_native_parent_status_is_read_only_and_never_claims_exit_protection(self):
        plan=self.adapter.prepare(self.payload);self.parent()
        result=self.adapter.reconcile(plan,preview_id="owned-preview",entry_order_id="123")
        self.assertEqual(result["status"],"ENTRY_PENDING")
        self.execution.parent.update(unfilled_size=0,state="closed",average_fill_price="99")
        result=self.adapter.reconcile(plan,preview_id="owned-preview",entry_order_id="123")
        self.assertEqual(result["filled_quantity"],2)
        self.assertFalse(result["protection_confirmed"])
        self.assertEqual(self.execution.placements,[])
    def test_native_cancel_with_partial_fills_is_not_an_empty_cancel(self):
        plan=self.adapter.prepare(self.payload);self.parent()
        self.execution.parent.update(unfilled_size=1,state="cancelled",average_fill_price="99")
        result=self.adapter.reconcile(plan,preview_id="owned-preview")
        self.assertIn("PARTIALLY_FILLED",result["status"])
        self.assertEqual(result["filled_quantity"],1)
        self.assertEqual(result["pending_quantity"],0)
    def test_native_status_account_or_order_mismatch_cannot_be_adopted(self):
        plan=self.adapter.prepare(self.payload);self.parent()
        self.execution.parent["product_symbol"]="ETHUSD"
        with self.assertRaises(ValueError):self.adapter.reconcile(plan,preview_id="owned-preview")
        self.execution.identity="other"
        with self.assertRaises(PermissionError):self.adapter.reconcile(plan,preview_id="owned-preview")


    def test_complete_native_read_path_proves_position_brackets_without_orders(self):
        plan=self.adapter.prepare(self.payload);self.parent()
        self.execution.parent.update(product_id=27,created_at="1970-01-01T00:01:30Z",
                                     unfilled_size=0,state="closed",average_fill_price="99")
        stop=dict(id=124,product_id=27,side="sell",bracket_order=True,reduce_only=True,
                  meta_data=dict(parent_type="position",parent_id=400),order_type="market_order",stop_order_type="stop_loss_order",stop_trigger_method="last_traded_price",
                  stop_price="95",size=2,unfilled_size=2,state="pending")
        self.execution.orders=[stop,dict(stop,id=125,stop_order_type="take_profit_order",stop_price="110")]
        self.execution.fills=[dict(id=9,order_id=123,product_id=27,side="buy",size=2,created_at="1970-01-01T00:01:35Z")]
        self.execution.position=2
        result=self.adapter.reconcile(plan,preview_id="owned-preview",entry_order_id="123")
        self.assertEqual(result["status"],"POSITION_PROTECTED")
        self.assertTrue(result["protection_confirmed"])
        self.assertEqual(self.execution.placements,[])

    def test_repeated_history_cursor_cannot_be_treated_as_complete(self):
        original=self.execution._private
        self.execution._private=lambda method,path,**kwargs:{"success":True,"result":[],"meta":{"after":"same"}}
        with self.assertRaisesRegex(ValueError,"pagination repeated"):
            self.adapter._pages("/v2/fills",{})
        self.execution._private=original
        self.assertEqual(self.execution.placements,[])

if __name__=="__main__":unittest.main()
