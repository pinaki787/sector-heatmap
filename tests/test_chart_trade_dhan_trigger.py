from dataclasses import replace
from decimal import Decimal
import json
import struct
import unittest
from sector_heatmap.chart_trade_plan import ChartTradePlan
from sector_heatmap.chart_trade_dhan_trigger import DhanTriggerState, arm_trigger, evaluate_trigger, wire_tick_price


def wire(value):return str(struct.unpack("<f",struct.pack("<f",float(value)))[0])


class DhanTriggerTests(unittest.TestCase):
    def setUp(self):
        self.plan=ChartTradePlan("account","DHAN","NSE_FNO:123","BUY",65,"25","22","30",
            "STOP_LIMIT","25.10","INTRADAY",".05",65,"AT_OR_ABOVE",native_account_hash="identity")
        self.tick=dict(account_id="account",broker="DHAN",symbol="NSE_FNO:123",
            native_account_hash="identity",source="BROKER_WEBSOCKET",stream_id="a"*32,
            connection_revision=1,sequence=1,price=wire(24.95),provider_at=100,received_at=100.2)
        self.state=arm_trigger(self.plan,self.tick,now=100.3,expires_at=200)

    def event(self,price=25,**values):
        event=dict(self.tick,price=wire(price),provider_at=101,received_at=101.1,sequence=2);event.update(values);return event

    def test_fresh_trigger_keeps_exact_reviewed_limit_and_runs_once(self):
        result=evaluate_trigger(self.state,self.plan,self.event(),now=101.2)
        self.assertEqual(result.status,"TRIGGERED")
        self.assertEqual(Decimal(result.trigger_price),25)
        self.assertEqual(self.plan.limit_price,"25.10")
        self.assertIs(evaluate_trigger(result,self.plan,self.event(26),now=102),result)

    def test_sell_trigger_has_correct_direction(self):
        plan=replace(self.plan,side="SELL",entry="25",limit_price="24.90",stop_loss="30",target="22",
                     price_trigger="AT_OR_BELOW")
        state=arm_trigger(plan,dict(self.tick,price=wire(25.05)),now=100.3,expires_at=200)
        self.assertEqual(evaluate_trigger(state,plan,self.event(24.95),now=101.2).status,"TRIGGERED")

    def test_old_prearm_tick_and_repeated_sequence_cannot_trigger(self):
        event=dict(self.tick,price=wire(25),sequence=2,received_at=100.4)
        result=evaluate_trigger(self.state,self.plan,event,now=100.5)
        self.assertEqual(result.status,"WAITING_FOR_TRIGGER")
        self.assertEqual(evaluate_trigger(result,self.plan,event,now=100.6),result)
        self.assertEqual(evaluate_trigger(result,self.plan,self.event(sequence=3),now=101.2).status,"TRIGGERED")

    def test_reconnect_or_restart_requires_review_even_when_price_crosses(self):
        for event in (self.event(connection_revision=2),self.event(stream_id="b"*32)):
            self.assertEqual(evaluate_trigger(self.state,self.plan,event,now=101.2).status,"REVIEW_REQUIRED")

    def test_stale_missing_wrong_source_and_wrong_account_are_not_triggers(self):
        for event in (None,dict(self.tick),self.event(source="HISTORICAL_OHLC"),
                      self.event(account_id="foreign"),self.event(symbol="NSE_FNO:456")):
            self.assertEqual(evaluate_trigger(self.state,self.plan,event,now=104).status,"REVIEW_REQUIRED")
        self.assertEqual(evaluate_trigger(self.state,self.plan,None,now=101).status,"WAITING_FOR_TRIGGER")

    def test_fresh_recovery_after_an_unobserved_gap_cannot_fire(self):
        event=self.event(26,provider_at=110,received_at=110.1,sequence=20)
        self.assertEqual(evaluate_trigger(self.state,self.plan,event,now=110.2).status,"REVIEW_REQUIRED")

    def test_expiry_or_changed_order_is_terminal_without_execution(self):
        result=evaluate_trigger(self.state,self.plan,self.event(26),now=200)
        self.assertEqual(result.status,"EXPIRED")
        changed=replace(self.plan,target="31")
        self.assertEqual(evaluate_trigger(self.state,changed,self.event(),now=101.2).status,"REVIEW_REQUIRED")

    def test_wire_precision_resolves_only_one_exact_tick(self):
        self.assertEqual(wire_tick_price(wire(25.05),".05"),Decimal("25.05"))
        self.assertEqual(wire_tick_price(wire("0.00000001"),"0.00000001"),Decimal("0.00000001"))
        for value,tick in (("25.05",".05"),(wire(300000),".0001"),(wire(25.025),".05")):
            with self.assertRaises(ValueError):wire_tick_price(value,tick)

    def test_state_roundtrips_for_durable_storage_and_disarms_on_clock_regression(self):
        restored=DhanTriggerState(**json.loads(json.dumps(self.state.terms())))
        self.assertEqual(restored,self.state)
        self.assertEqual(evaluate_trigger(restored,self.plan,self.event(),now=100).status,"REVIEW_REQUIRED")

    def test_already_crossed_baseline_requires_a_new_review(self):
        with self.assertRaisesRegex(ValueError,"Review a new"):
            arm_trigger(self.plan,self.event(25),now=101.2,expires_at=200)

    def test_gap_beyond_cap_still_retains_the_reviewed_pending_limit(self):
        result=evaluate_trigger(self.state,self.plan,self.event(26),now=101.2)
        self.assertEqual(result.status,"TRIGGERED")
        self.assertEqual(self.plan.limit_price,"25.10")
        self.assertEqual(Decimal(result.trigger_price),Decimal("26"))


if __name__=="__main__":unittest.main()
