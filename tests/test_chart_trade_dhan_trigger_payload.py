from dataclasses import replace
import unittest
from sector_heatmap.chart_trade_native import (
    native_bracket_order,dhan_super_margin_payload,dhan_triggered_bracket_order)
from sector_heatmap.chart_trade_plan import build_plan
from tests import test_chart_trade_dhan_trigger as fixtures


class DhanTriggeredPayloadTests(unittest.TestCase):
    def setUp(self):
        fixtures.DhanTriggerTests.setUp(self)
        self.plan=replace(self.plan,tick_size='0.05')
    event=fixtures.DhanTriggerTests.event

    def request(self,*,claim=None,tick=None,now=101.2):
        proof=dict(fingerprint=self.plan.fingerprint(),claim_token="b"*32,claimed_at=101.2,
                   stream_id="a"*32,connection_revision=1,sequence=2,provider_at=101,received_at=101.1)
        if claim:proof.update(claim)
        return dhan_triggered_bracket_order(self.plan,
            dict(symbol=self.plan.symbol,security_id="123",exchange_segment="NSE_FNO"),
            client_order_id="review",broker_client_id="client",claim=proof,tick=tick or self.event(),now=now)

    def test_explicit_claim_uses_separate_cap_and_preserves_original_review(self):
        fingerprint=self.plan.fingerprint()
        result=self.request()
        self.assertEqual(result["body"]["orderType"],"LIMIT")
        self.assertEqual(result["body"]["price"],25.1)
        self.assertEqual((result["body"]["stopLossPrice"],result["body"]["targetPrice"]),(22,30))
        self.assertEqual(result["managed_trigger"],"25")
        self.assertEqual(result["reviewed_fingerprint"],fingerprint)
        self.assertEqual(self.plan.entry_type,"STOP_LIMIT")
        self.assertEqual(self.plan.entry,"25")
        with self.assertRaises(ValueError):
            native_bracket_order(self.plan,dict(symbol=self.plan.symbol,security_id="123",exchange_segment="NSE_FNO"),
                                 client_order_id="review",broker_client_id="client")

    def test_calculator_payload_has_cap_but_no_placement_identifier_or_route(self):
        result=dhan_super_margin_payload(self.plan,
            dict(symbol=self.plan.symbol,security_id="123",exchange_segment="NSE_FNO"),broker_client_id="client")
        self.assertEqual(result["price"],25.1)
        self.assertNotIn("correlationId",result)
        self.assertNotIn("method",result)
        self.assertNotIn("path",result)
        self.assertNotIn("orderType",result)

    def test_wrong_claim_stream_or_reversed_price_cannot_create_request(self):
        for claim,tick in (({"fingerprint":"wrong"},None),({"claim_token":"wrong"},None),
                           (None,self.event(stream_id="c"*32)),(None,self.event(24.95)),
                           (None,self.event(account_id="foreign"))):
            with self.subTest(claim=claim),self.assertRaises(ValueError):
                self.request(claim=claim,tick=tick)

    def test_stale_claim_and_stale_tick_are_rejected(self):
        with self.assertRaises(ValueError):self.request(now=132)
        with self.assertRaises(ValueError):self.request(now=104)
        with self.assertRaises(ValueError):self.request(claim={"claimed_at":102},now=101.2)

    def test_gap_beyond_cap_does_not_chase(self):
        self.assertEqual(self.request(tick=self.event(26))["body"]["price"],25.1)

    def test_triggered_plan_refresh_keeps_original_fingerprint_and_needs_dhan_cross(self):
        account=dict(id="account",broker="DHAN",native_identity="identity")
        contract=dict(symbol=self.plan.symbol,tradable=True,tick_size=".05",lot_size=65,
                      linked_exit_capability="NATIVE_OCO",products=["INTRADAY"])
        payload=self.plan.terms()
        quote=dict(account_id="account",symbol=self.plan.symbol,last_price=25.05,received_at=101,provider_at=101)
        refreshed=build_plan(payload,account=account,contract=contract,quote=quote,now=101.2,
                             triggered_dhan_entry=True)
        self.assertEqual(refreshed.fingerprint(),self.plan.fingerprint())
        with self.assertRaises(ValueError):
            build_plan(payload,account=account,contract=contract,quote=quote,now=101.2)
        quote["last_price"]=24.95
        with self.assertRaises(ValueError):
            build_plan(payload,account=account,contract=contract,quote=quote,now=101.2,triggered_dhan_entry=True)
