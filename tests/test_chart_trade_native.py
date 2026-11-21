import unittest
from sector_heatmap.chart_trade_plan import ChartTradePlan
from sector_heatmap.chart_trade_native import native_bracket_order
from dataclasses import replace


class NativeChartOrderTests(unittest.TestCase):
    def setUp(self):
        self.plan=ChartTradePlan("account","FYERS","NSE:TEST","BUY",65,"25","22","30",
                                "LIMIT","25","INTRADAY","0.05",65,"AT_OR_BELOW")
        self.contract={"symbol":"NSE:TEST"}

    def order(self,plan=None,contract=None,**kwargs):
        return native_bracket_order(plan or self.plan,contract or self.contract,
                                    client_order_id="CHART-review-1",**kwargs)

    def test_fyers_preserves_absolute_levels_and_uses_sync_tpsl(self):
        result=self.order()
        body=result["body"]
        self.assertEqual(result["sdk_method"],"place_order")
        self.assertEqual((body["limitPrice"],body["stopLoss"],body["takeProfit"]),(25,22,30))
        self.assertNotIn("legType",body)
        self.assertEqual(body["type"],1)
        self.assertEqual(body["productType"],"INTRADAY")
        self.assertTrue(body["orderTag"].isalnum())
        self.assertLessEqual(len(body["orderTag"]),30)

    def test_fyers_stop_limit_keeps_trigger_separate_from_price_cap(self):
        body=self.order(replace(self.plan,entry_type="STOP_LIMIT",limit_price="25.05"))["body"]
        self.assertEqual((body["type"],body["stopPrice"],body["limitPrice"]),(4,25,25.05))
        self.assertEqual((body["stopLoss"],body["takeProfit"]),(22,30))

    def test_dhan_super_order_keeps_exact_security_and_exit_prices(self):
        plan=replace(self.plan,broker="DHAN")
        body=self.order(plan,dict(self.contract,security_id="123",exchange_segment="NSE_FNO"),
                        broker_client_id="selected-client")["body"]
        self.assertEqual(body["dhanClientId"],"selected-client")
        self.assertEqual(body["securityId"],"123")
        self.assertEqual((body["price"],body["stopLossPrice"],body["targetPrice"]),(25,22,30))
        self.assertEqual(body["trailingJump"],0)

    def test_dhan_breakout_never_falls_back_to_immediate_limit(self):
        with self.assertRaisesRegex(ValueError,"no limit or market substitution"):
            self.order(replace(self.plan,broker="DHAN",entry_type="STOP_LIMIT"),
                       dict(self.contract,security_id="123",exchange_segment="NSE_FNO"),
                       broker_client_id="selected-client")

    def test_delta_places_pending_entry_with_native_brackets_in_same_request(self):
        plan=replace(self.plan,broker="DELTA_INDIA",symbol="BTCUSD",entry_type="STOP_LIMIT",
                     limit_price="25.05",product="MARGIN")
        body=self.order(plan,{"symbol":"BTCUSD","product_id":27})["body"]
        self.assertEqual(body["time_in_force"],"gtc")
        self.assertEqual(body["product_id"],27)
        self.assertNotIn("product_symbol",body)
        self.assertEqual(body["stop_price"],"25")
        self.assertEqual(body["bracket_stop_loss_price"],"22")
        self.assertEqual(body["bracket_take_profit_price"],"30")
        self.assertEqual(body["bracket_stop_trigger_method"],"last_traded_price")
        self.assertFalse(body["cancel_orders_accepted"])
        self.assertFalse(body["reduce_only"])
        self.assertEqual(body["client_order_id"],self.order(plan,{"symbol":"BTCUSD","product_id":27})["body"]["client_order_id"])

    def test_no_unknown_broker_or_wrong_contract_can_fall_through_to_fyers(self):
        with self.assertRaises(ValueError):self.order(contract={"symbol":"ANOTHER"})
        with self.assertRaises(ValueError):self.order(replace(self.plan,broker="MOTILAL_OSWAL"))


    def test_delta_never_silently_changes_exit_trigger_price_source(self):
        plan=replace(self.plan,broker="DELTA_INDIA",symbol="BTCUSD",product="MARGIN",exit_trigger_method="mark_price")
        body=self.order(plan,{"symbol":"BTCUSD","product_id":27})["body"]
        self.assertEqual(body["bracket_stop_trigger_method"],"mark_price")


    def test_numeric_broker_payload_never_silently_rounds_an_exact_price(self):
        with self.assertRaisesRegex(ValueError,"preserve this exact"):
            self.order(replace(self.plan,entry="25.000000000000000001",limit_price="25.000000000000000001"))
        plan=replace(self.plan,broker="DELTA_INDIA",symbol="BTCUSD",product="MARGIN",
                     entry="25.000000000000000001",limit_price="25.000000000000000001")
        body=self.order(plan,{"symbol":"BTCUSD","product_id":27})["body"]
        self.assertEqual(body["limit_price"],"25.000000000000000001")


if __name__=="__main__":unittest.main()

