import copy
import unittest
import hashlib
from dataclasses import replace
from types import SimpleNamespace
from sector_heatmap.chart_trade_dhan import DhanChartAdapter
from sector_heatmap.chart_trade_plan import ChartTradePlan
from sector_heatmap.chart_trade_native import native_bracket_order
from sector_heatmap.chart_trade_dhan_exits import reconcile_dhan_exits


class DhanChartExitTests(unittest.TestCase):
    def setUp(self):
        self.plan=ChartTradePlan("account","DHAN","NSE_FNO:123","BUY",65,"25","22","30",
                                "LIMIT","25","INTRADAY","0.05",65,"AT_OR_BELOW")
        self.contract=dict(symbol=self.plan.symbol,security_id="123",exchange_segment="NSE_FNO")
        ticket=native_bracket_order(self.plan,self.contract,client_order_id="preview",broker_client_id="client")["body"]
        self.parent=dict(ticket,orderId="owned",legName="ENTRY_LEG",orderStatus="CLOSED",
                         filledQty=65,remainingQuantity=0,averageTradedPrice=25,createTime="2026-11-18 10:00:00")
        identity=dict(dhanClientId="client",exchangeSegment="NSE_FNO",securityId="123",productType="INTRADAY",orderId="owned")
        self.orders=[dict(identity,legName=role,transactionType=side,orderStatus=status,
                          exchangeOrderId=exchange_id,quantity=65,filledQty=filled,remainingQuantity=0)
            for role,side,status,exchange_id,filled in (
                ("ENTRY_LEG","BUY","TRADED","entry-exchange",65),
                ("STOP_LOSS_LEG","SELL","CANCELLED","",0),
                ("TARGET_LEG","SELL","TRADED","target-exchange",65))]
        self.trades=[dict(identity,transactionType=side,exchangeOrderId=exchange_id,
                         exchangeTradeId=trade_id,tradedQuantity=65,tradedPrice=price,
                         exchangeTime="2026-11-18 "+clock)
            for side,exchange_id,trade_id,price,clock in (
                ("BUY","entry-exchange","entry-trade",25,"10:00:01"),
                ("SELL","target-exchange","exit-trade",30,"10:10:00"))]
        self.positions=[dict(identity,netQty=0)]

    def read(self):
        return reconcile_dhan_exits(self.plan,self.contract,self.parent,client_id="client",
            preview_id="preview",orders=self.orders,trades=self.trades,positions=self.positions)

    def test_closed_requires_actual_owned_exit_fills_flat_position_and_terminal_sibling(self):
        result=self.read()
        self.assertEqual(result["status"],"CLOSED")
        self.assertEqual(result["exited_quantity"],65)
        self.assertEqual(result["open_quantity"],0)
        self.assertFalse(result["retry_allowed"])

    def test_closed_super_and_flat_position_alone_do_not_prove_exit(self):
        self.trades.pop()
        self.assertEqual(self.read()["status"],"BROKER_STATUS_UNAVAILABLE")
        self.orders.pop()
        self.assertNotEqual(self.read()["status"],"CLOSED")

    def test_active_sibling_or_entry_remainder_keeps_ownership(self):
        self.orders[1].update(orderStatus="PENDING",remainingQuantity=65)
        self.assertEqual(self.read()["status"],"EXIT_CANCELLATION_PENDING")
        self.orders[1].update(orderStatus="CANCELLED",remainingQuantity=0)
        self.orders[0].update(orderStatus="PENDING")
        self.assertEqual(self.read()["status"],"ENTRY_REMAINDER_PENDING")

    def test_trade_duplicates_are_deduplicated_and_conflicts_rejected(self):
        self.trades.append(copy.deepcopy(self.trades[1]))
        self.assertEqual(self.read()["status"],"CLOSED")
        self.trades[-1]["tradedPrice"]=31
        self.assertEqual(self.read()["status"],"BROKER_STATUS_UNAVAILABLE")

    def test_unrelated_fills_after_entry_and_nonflat_position_block_closure(self):
        self.trades.append(dict(self.trades[1],orderId="unrelated",exchangeTradeId="foreign"))
        self.assertEqual(self.read()["status"],"POSITION_OWNERSHIP_CONFLICT")
        self.trades[-1]["exchangeTime"]="2026-11-18 09:30:00"
        self.assertEqual(self.read()["status"],"CLOSED")
        self.positions[0]["netQty"]=1
        self.assertEqual(self.read()["status"],"POSITION_OWNERSHIP_CONFLICT")

    def test_wrong_account_contract_role_exchange_id_and_parent_are_unverified(self):
        original=copy.deepcopy(self.orders)
        for field,value in (("dhanClientId","foreign"),("legName","UNKNOWN"),
                            ("exchangeOrderId","entry-exchange"),("filledQty",True)):
            self.orders=copy.deepcopy(original);self.orders[2][field]=value
            self.assertNotEqual(self.read()["status"],"CLOSED")
        self.orders=original
        self.parent["correlationId"]="foreign"
        self.assertEqual(self.read()["status"],"BROKER_STATUS_UNAVAILABLE")

    def test_partial_exit_matches_position_but_is_not_closed_or_protected(self):
        self.trades[1]["tradedQuantity"]=30
        self.orders[2].update(orderStatus="PART_TRADED",filledQty=30,remainingQuantity=35)
        self.positions[0]["netQty"]=35
        result=self.read()
        self.assertEqual(result["open_quantity"],35)
        self.assertEqual(result["status"],"ENTRY_FILLED_EXITS_UNVERIFIED")
        self.assertFalse(result["protection_confirmed"])

    def adapter(self, *, changed=False, slow=False, identity="client"):
        clock=[100.0];calls=[];super_reads=[0]
        def request(method,path,payload=None):
            self.assertEqual(method,"GET")
            calls.append(path);clock[0]+=1.1 if slow else 0.1
            if path=="/profile":return {"dhanClientId":identity}
            if path=="/super/orders":
                super_reads[0]+=1
                row=copy.deepcopy(self.parent)
                if changed and super_reads[0]>1:row["filledQty"]=0
                return [row]
            return copy.deepcopy({"/orders":self.orders,"/trades":self.trades,"/positions":self.positions}[path])
        account=dict(id="account",broker="DHAN",account_ref="client")
        client=SimpleNamespace(client_id="client",request=request)
        adapter=DhanChartAdapter(account,SimpleNamespace(account=account,_client=lambda:client),clock=lambda:clock[0])
        plan=replace(self.plan,native_account_hash=hashlib.sha256(b"client").hexdigest())
        return adapter,plan,calls

    def test_adapter_reconciliation_reads_only_and_checks_current_parent(self):
        adapter,plan,calls=self.adapter()
        result=adapter.reconcile(plan,preview_id="preview",entry_order_id="owned")
        self.assertEqual(result["status"],"CLOSED")
        self.assertEqual(calls,["/profile","/super/orders","/orders","/trades","/positions","/super/orders"])
        adapter,plan,_=self.adapter(changed=True)
        with self.assertRaisesRegex(ValueError,"changed"):
            adapter.reconcile(plan,preview_id="preview",entry_order_id="owned")

    def test_adapter_rejects_changed_login_and_aged_snapshot(self):
        adapter,plan,calls=self.adapter(identity="foreign")
        with self.assertRaises(PermissionError):adapter.reconcile(plan,preview_id="preview",entry_order_id="owned")
        self.assertEqual(calls,["/profile"])
        adapter,plan,_=self.adapter(slow=True)
        with self.assertRaisesRegex(ValueError,"aged"):
            adapter.reconcile(plan,preview_id="preview",entry_order_id="owned")

    def test_duplicate_positions_and_contradictory_exchange_status_cannot_close(self):
        self.positions.append(dict(self.positions[0]))
        self.assertEqual(self.read()["status"],"BROKER_STATUS_UNAVAILABLE")
        self.positions.pop()
        self.orders[2]["orderStatus"]="REJECTED"
        self.assertEqual(self.read()["status"],"BROKER_STATUS_UNAVAILABLE")

    def test_missing_malformed_trade_time_and_overfill_fail(self):
        del self.trades[1]["exchangeTime"]
        self.assertEqual(self.read()["status"],"BROKER_STATUS_UNAVAILABLE")
        self.trades[1]["exchangeTime"]="2026-11-18 10:10:00"
        self.orders[2].update(quantity=66,filledQty=66)
        self.trades[1]["tradedQuantity"]=66
        self.assertEqual(self.read()["status"],"BROKER_STATUS_UNAVAILABLE")


if __name__=="__main__":unittest.main()
